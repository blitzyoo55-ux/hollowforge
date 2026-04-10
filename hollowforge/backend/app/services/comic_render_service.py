"""Comic panel render queueing and asset selection helpers."""

from __future__ import annotations

import asyncio
import json
import hashlib
import re
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
from PIL import Image

from app.config import settings
from app.db import get_db
from app.models import (
    AnimationJobCallbackPayload,
    ComicPanelRenderAssetResponse,
    ComicPanelRenderQueueResponse,
    ComicRenderJobResponse,
    ComicRenderExecutionMode,
    ComicScenePanelResponse,
    GenerationCreate,
    LoraInput,
    comic_render_job_response_from_row,
)
from app.services.comic_render_dispatch_service import (
    ComicRenderDispatchError,
    dispatch_comic_render_job,
)
from app.services.comic_render_profiles import (
    filter_anchor_fragments,
    filter_profile_loras,
    select_scene_cues,
    resolve_comic_panel_render_profile,
)
from app.services.ai_quality_service import analyze_image
from app.services.adetailer_service import detect_faces
from app.services.character_canon_v2_registry import get_character_canon_v2
from app.services.character_series_binding_registry import get_character_series_binding
from app.services.comic_render_v2_resolver import resolve_comic_render_v2_contract
from app.services.generation_service import GenerationService
from app.services.story_planner_catalog import load_story_planner_catalog
from app.services.workflow_registry import infer_workflow_lane

_RENDER_ASSET_SELECT_COLUMNS = """
    a.id,
    a.scene_panel_id,
    a.generation_id,
    a.asset_role,
    COALESCE(a.storage_path, g.upscaled_image_path, g.image_path) AS storage_path,
    a.prompt_snapshot,
    a.quality_score,
    a.bubble_safe_zones,
    a.crop_metadata,
    a.render_notes,
    a.is_selected,
    a.created_at,
    a.updated_at
"""

_REFERENCE_GUIDED_IPADAPTER_WEIGHT = 0.92
_REFERENCE_GUIDED_IPADAPTER_START_AT = 0.0
_REFERENCE_GUIDED_IPADAPTER_END_AT = 1.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_json_list(value: str | None) -> list[Any]:
    if value is None:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON stored in comic panel render asset") from exc
    if not isinstance(parsed, list):
        raise ValueError("Invalid JSON stored in comic panel render asset")
    return parsed


def _parse_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        if not value.strip():
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("Comic render job request_json must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Comic render job request_json must be a JSON object")
        return parsed
    raise ValueError("Comic render job request_json must be a JSON object")


def _merge_request_json_payload(
    existing_raw: Any,
    incoming: dict[str, Any] | None,
) -> str | None:
    if incoming is None:
        return cast(str | None, existing_raw)

    merged = _parse_json_object(existing_raw)
    for key, value in incoming.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            nested = dict(cast(dict[str, Any], merged[key]))
            nested.update(value)
            merged[key] = nested
            continue
        merged[key] = value
    return json.dumps(merged, ensure_ascii=False)


def _panel_response(row: dict[str, Any]) -> ComicScenePanelResponse:
    return ComicScenePanelResponse.model_validate(row)


def _render_asset_response(row: dict[str, Any]) -> ComicPanelRenderAssetResponse:
    payload = dict(row)
    payload["prompt_snapshot"] = json.loads(payload["prompt_snapshot"]) if payload.get("prompt_snapshot") else None
    payload["bubble_safe_zones"] = _decode_json_list(payload.get("bubble_safe_zones"))
    crop_metadata = payload.get("crop_metadata")
    payload["crop_metadata"] = json.loads(crop_metadata) if crop_metadata else None
    return ComicPanelRenderAssetResponse.model_validate(payload)


def _profile_signature(profile: Any) -> str:
    signature_payload = {
        "profile_id": profile.profile_id,
        "lora_mode": profile.lora_mode,
        "width": profile.width,
        "height": profile.height,
        "negative_prompt_append": profile.negative_prompt_append,
        "quality_selector_hints": list(getattr(profile, "quality_selector_hints", ())),
        "anchor_filter_mode": profile.anchor_filter_mode,
    }
    digest = hashlib.sha1(
        json.dumps(signature_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return digest[:12]


def _render_request_source_id(
    panel_id: str,
    candidate_count: int,
    execution_mode: ComicRenderExecutionMode,
    profile_signature: str,
) -> str:
    return (
        f"comic-panel-render:{panel_id}:{candidate_count}:{execution_mode}:{profile_signature}"
    )


def _build_queue_response(
    *,
    panel: ComicScenePanelResponse,
    requested_count: int,
    queued_generation_count: int,
    render_assets: list[ComicPanelRenderAssetResponse],
    execution_mode: ComicRenderExecutionMode,
    materialized_asset_count: int | None = None,
    pending_render_job_count: int = 0,
    remote_job_count: int = 0,
) -> ComicPanelRenderQueueResponse:
    return ComicPanelRenderQueueResponse(
        panel=panel,
        execution_mode=execution_mode,
        requested_count=requested_count,
        queued_generation_count=queued_generation_count,
        materialized_asset_count=(
            len(render_assets)
            if materialized_asset_count is None
            else materialized_asset_count
        ),
        pending_render_job_count=pending_render_job_count,
        remote_job_count=remote_job_count,
        render_assets=render_assets,
    )


def _count_materialized_assets(
    render_assets: list[ComicPanelRenderAssetResponse],
) -> int:
    return sum(1 for asset in render_assets if asset.storage_path)


def _is_pending_remote_render_job(job: dict[str, Any]) -> bool:
    return job.get("status") in {"queued", "submitted", "processing"}


def _has_queued_remote_render_job(jobs: list[dict[str, Any]]) -> bool:
    return any(job.get("status") == "queued" for job in jobs)


def _normalize_story_planner_location_label(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _resolve_story_planner_location_metadata(
    location_label: str,
) -> dict[str, Any] | None:
    label = location_label.strip()
    if not label:
        return None

    normalized_label = _normalize_story_planner_location_label(label)
    catalog = load_story_planner_catalog()
    for location in catalog.locations:
        if normalized_label in {
            _normalize_story_planner_location_label(location.id),
            _normalize_story_planner_location_label(location.name),
        }:
            return location.model_dump()
    return None


def _resolve_reference_guided_still_request_metadata(
    *,
    panel_context: dict[str, Any],
) -> dict[str, Any]:
    resolver_execution_summary = panel_context.get("resolver_execution_summary")
    if not isinstance(resolver_execution_summary, dict):
        return {}
    if resolver_execution_summary.get("reference_guided") is not True:
        return {}

    still_backend_family = str(
        resolver_execution_summary.get("still_backend_family") or ""
    ).strip()
    if not still_backend_family:
        raise ValueError(
            "Reference-guided comic render request missing still_backend_family"
        )

    raw_reference_images = panel_context.get("reference_images")
    if not isinstance(raw_reference_images, list) or not raw_reference_images:
        raise ValueError(
            "Reference-guided comic render request missing reference_images"
        )

    reference_images = [
        str(image).strip()
        for image in raw_reference_images
        if str(image).strip()
    ]
    if not reference_images:
        raise ValueError(
            "Reference-guided comic render request missing reference_images"
        )

    return {
        "backend_family": still_backend_family,
        "reference_images": reference_images,
        "ipadapter_weight": _REFERENCE_GUIDED_IPADAPTER_WEIGHT,
        "ipadapter_start_at": _REFERENCE_GUIDED_IPADAPTER_START_AT,
        "ipadapter_end_at": _REFERENCE_GUIDED_IPADAPTER_END_AT,
    }


async def _load_panel_render_context(panel_id: str) -> dict[str, Any]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT
                p.*,
                s.episode_id AS episode_id,
                s.location_label AS location_label,
                s.continuity_notes AS scene_continuity_notes,
                e.character_id AS character_id,
                e.character_version_id AS character_version_id,
                e.render_lane AS render_lane,
                e.series_style_id AS series_style_id,
                e.character_series_binding_id AS character_series_binding_id,
                c.canonical_prompt_anchor AS canonical_prompt_anchor,
                cv.prompt_prefix AS prompt_prefix,
                cv.negative_prompt AS negative_prompt,
                cv.checkpoint AS checkpoint,
                cv.workflow_lane AS workflow_lane,
                cv.loras AS loras,
                cv.steps AS steps,
                cv.cfg AS cfg,
                cv.width AS width,
                cv.height AS height,
                cv.sampler AS sampler,
                cv.scheduler AS scheduler,
                cv.clip_skip AS clip_skip
            FROM comic_scene_panels p
            JOIN comic_episode_scenes s ON s.id = p.episode_scene_id
            JOIN comic_episodes e ON e.id = s.episode_id
            JOIN characters c ON c.id = e.character_id
            JOIN character_versions cv ON cv.id = e.character_version_id
            WHERE p.id = ?
            """,
            (panel_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        raise ValueError(f"Comic panel not found: {panel_id}")
    return cast(dict[str, Any], row)


async def _insert_render_asset(
    db,
    *,
    panel_id: str,
    generation_id: str,
    prompt_snapshot: dict[str, Any],
) -> None:
    asset_id = str(uuid.uuid4())
    now = _now_iso()
    await db.execute(
        """
        INSERT INTO comic_panel_render_assets (
            id,
            scene_panel_id,
            generation_id,
            asset_role,
            storage_path,
            prompt_snapshot,
            quality_score,
            bubble_safe_zones,
            crop_metadata,
            render_notes,
            is_selected,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset_id,
            panel_id,
            generation_id,
            "candidate",
            None,
            json.dumps(prompt_snapshot, ensure_ascii=False),
            None,
            "[]",
            None,
            None,
            0,
            now,
            now,
        ),
    )


async def _load_render_asset(
    *,
    panel_id: str,
    asset_id: str,
) -> dict[str, Any] | None:
    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT {_RENDER_ASSET_SELECT_COLUMNS}
            FROM comic_panel_render_assets a
            LEFT JOIN generations g ON g.id = a.generation_id
            WHERE a.id = ? AND a.scene_panel_id = ?
            """,
            (asset_id, panel_id),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return cast(dict[str, Any], row)


async def _load_render_assets_for_source(
    *,
    panel_id: str,
    source_id: str,
) -> list[ComicPanelRenderAssetResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT {_RENDER_ASSET_SELECT_COLUMNS}
            FROM comic_panel_render_assets a
            JOIN generations g ON g.id = a.generation_id
            WHERE a.scene_panel_id = ?
              AND g.source_id = ?
            ORDER BY g.seed ASC, a.created_at ASC, a.id ASC
            """,
            (panel_id, source_id),
        )
        rows = await cursor.fetchall()
    return [_render_asset_response(cast(dict[str, Any], row)) for row in rows]


async def _load_generation_count_for_source(source_id: str) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) AS generation_count
            FROM generations
            WHERE source_id = ?
            """,
            (source_id,),
        )
        row = await cursor.fetchone()
    return int(row["generation_count"]) if row is not None else 0


async def _load_generation_created_at_for_source(source_id: str) -> str | None:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT MAX(created_at) AS created_at
            FROM generations
            WHERE source_id = ?
            """,
            (source_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return cast(str | None, row["created_at"])


async def _load_render_jobs_for_source(source_id: str) -> list[dict[str, Any]]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT *
            FROM comic_render_jobs
            WHERE source_id = ?
            ORDER BY request_index ASC, created_at ASC, id ASC
            """,
            (source_id,),
        )
        rows = await cursor.fetchall()
    return [cast(dict[str, Any], row) for row in rows]


async def _load_render_job_by_id(job_id: str) -> dict[str, Any] | None:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT *
            FROM comic_render_jobs
            WHERE id = ?
            """,
            (job_id,),
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return cast(dict[str, Any], row)


async def _load_reusable_render_assets_for_request(
    *,
    panel_id: str,
    candidate_count: int,
    execution_mode: ComicRenderExecutionMode,
    profile: Any,
    panel_updated_at: str,
) -> tuple[str | None, list[ComicPanelRenderAssetResponse]]:
    current_source_id = _render_request_source_id(
        panel_id,
        candidate_count,
        execution_mode,
        _profile_signature(profile),
    )
    current_generation_count = await _load_generation_count_for_source(current_source_id)
    if current_generation_count > 0:
        current_rows = await _load_render_assets_for_source(
            panel_id=panel_id,
            source_id=current_source_id,
        )
        if len(current_rows) == candidate_count:
            return current_source_id, current_rows
        return None, []

    async def _load_fresh_legacy_assets(
        source_id: str,
    ) -> tuple[str | None, list[ComicPanelRenderAssetResponse]]:
        legacy_rows = await _load_render_assets_for_source(
            panel_id=panel_id,
            source_id=source_id,
        )
        if len(legacy_rows) != candidate_count:
            return None, []
        batch_created_at = await _load_generation_created_at_for_source(source_id)
        if batch_created_at is not None and batch_created_at < panel_updated_at:
            return None, []
        return source_id, legacy_rows

    pre_profile_source_id = (
        f"comic-panel-render:{panel_id}:{candidate_count}:{execution_mode}"
    )
    reused_source_id, reused_assets = await _load_fresh_legacy_assets(
        pre_profile_source_id
    )
    if reused_source_id is not None:
        return reused_source_id, reused_assets

    if execution_mode == "local_preview":
        legacy_source_id = f"comic-panel-render:{panel_id}:{candidate_count}"
        return await _load_fresh_legacy_assets(legacy_source_id)
    return None, []


def _clean_prompt_fragment(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().rstrip(" .,!?:;")
    return cleaned or None


_POSITIVE_VISUAL_PROMPT_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bwide establishing shot\b", flags=re.IGNORECASE), "wide room view"),
    (re.compile(r"\bwide shot\b", flags=re.IGNORECASE), "wide room view"),
    (re.compile(r"\bmedium shot\b", flags=re.IGNORECASE), "mid view"),
    (re.compile(r"\bclose[- ]up shot\b", flags=re.IGNORECASE), "tight close view"),
    (re.compile(r"\bintimate close camera\b", flags=re.IGNORECASE), "intimate close viewpoint"),
    (re.compile(r"\bslightly low camera\b", flags=re.IGNORECASE), "slightly low viewpoint"),
    (re.compile(r"\blow camera\b", flags=re.IGNORECASE), "low viewpoint"),
    (re.compile(r"\bhigh camera\b", flags=re.IGNORECASE), "high viewpoint"),
    (re.compile(r"\boverhead camera\b", flags=re.IGNORECASE), "overhead viewpoint"),
    (re.compile(r"\bclose camera\b", flags=re.IGNORECASE), "close viewpoint"),
    (re.compile(r"\bcamera\b", flags=re.IGNORECASE), "viewpoint"),
)


def _normalize_positive_visual_prompt_fragment(value: Any) -> str | None:
    cleaned = _clean_prompt_fragment(value)
    if cleaned is None:
        return None
    normalized = cleaned
    for pattern, replacement in _POSITIVE_VISUAL_PROMPT_REPLACEMENTS:
        normalized = pattern.sub(replacement, normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized or None


def _build_labeled_sentence(
    label: str,
    fragments: list[str | None],
    *,
    separator: str = ", ",
) -> str | None:
    cleaned_fragments = [fragment for fragment in fragments if fragment]
    if not cleaned_fragments:
        return None
    return f"{label}: {separator.join(cleaned_fragments)}."


def _build_quality_focus_sentence(profile: Any) -> str | None:
    hints = [
        str(hint).strip()
        for hint in getattr(profile, "quality_selector_hints", ())
        if str(hint).strip()
    ]
    if not hints:
        return None
    return _build_labeled_sentence("Quality focus", hints)


def _build_panel_story_prompt_sentences(
    context: dict[str, Any],
    *,
    profile: Any,
    style_and_subject: str | None = None,
    include_quality_focus: bool = True,
) -> list[str]:
    location_label = str(context.get("location_label") or "").strip()
    scene_continuity_notes = str(context.get("scene_continuity_notes") or "").strip()
    panel_type = str(context.get("panel_type") or "").strip()
    continuity_lock = str(context.get("continuity_lock") or "").strip()
    panel_type_lower = panel_type.lower()

    cleaned_continuity_lock = _clean_prompt_fragment(continuity_lock)
    continuity_fragments: list[str | None] = [
        _clean_prompt_fragment(scene_continuity_notes)
    ]
    if cleaned_continuity_lock:
        primary_continuity = continuity_fragments[0]
        if primary_continuity is None or cleaned_continuity_lock not in primary_continuity:
            continuity_fragments.append(cleaned_continuity_lock)

    composition_priority_hint = {
        "establish": (
            "single adult subject only, no second person, no mirror duplicate, "
            "environment-first framing, subject smaller in frame, room and props "
            "clearly readable"
        ),
        "beat": (
            "single adult subject only, no second person, subject and prop both "
            "readable in frame"
        ),
        "insert": (
            "single pair of adult hands only, no second person, object-led framing, "
            "hands and invitation prioritized over a full-face portrait"
        ),
        "closeup": (
            "single adult subject only, no second person, emotional reaction framing "
            "with face and hands dominating the panel"
        ),
    }.get(panel_type_lower)

    setting_sentence = _build_labeled_sentence(
        "Setting",
        [f"inside {location_label}" if location_label else None],
    )
    action_sentence = _build_labeled_sentence(
        "Action",
        [_clean_prompt_fragment(context.get("action_intent"))],
    )
    emotion_sentence = _build_labeled_sentence(
        "Emotion",
        [_clean_prompt_fragment(context.get("expression_intent"))],
    )
    subject_prominence_sentence = _build_labeled_sentence(
        "Subject prominence",
        (
            [
                "single lead only",
                "keep the lead secondary to the room",
                "favor the environment over a glamour portrait",
            ]
            if profile.subject_prominence_mode == "reduced"
            else ["single lead only"]
        ),
    )
    quality_focus_sentence = (
        _build_quality_focus_sentence(profile) if include_quality_focus else None
    )
    composition_sentence = _build_labeled_sentence(
        "Composition",
        [
            f"{panel_type_lower} manga panel" if panel_type_lower else None,
            composition_priority_hint,
            _normalize_positive_visual_prompt_fragment(context.get("camera_intent")),
            _normalize_positive_visual_prompt_fragment(context.get("framing")),
        ],
    )
    continuity_sentence = _build_labeled_sentence(
        "Continuity",
        continuity_fragments,
        separator=". ",
    )

    if panel_type_lower == "establish":
        location = _resolve_story_planner_location_metadata(location_label)
        scene_cues = select_scene_cues(
            location,
            scene_cue_mode=profile.scene_cue_mode,
        )
        scene_cues_sentence = _build_labeled_sentence(
            "Scene cues",
            scene_cues,
        )
        prompt_sentences = [
            setting_sentence,
            scene_cues_sentence,
            composition_sentence,
            quality_focus_sentence,
            subject_prominence_sentence,
            action_sentence,
            f"{style_and_subject}." if style_and_subject else None,
            continuity_sentence,
        ]
    elif panel_type_lower == "insert":
        prompt_sentences = [
            setting_sentence,
            action_sentence,
            composition_sentence,
            quality_focus_sentence,
            f"{style_and_subject}." if style_and_subject else None,
            emotion_sentence,
            continuity_sentence,
        ]
    else:
        prompt_sentences = [
            f"{style_and_subject}." if style_and_subject else None,
            setting_sentence,
            action_sentence,
            emotion_sentence,
            composition_sentence,
            quality_focus_sentence,
            continuity_sentence,
        ]

    return [sentence for sentence in prompt_sentences if sentence]


def _build_prompt(context: dict[str, Any]) -> str:
    profile = resolve_comic_panel_render_profile(context)

    style_subject_fragments: list[str] = []
    for raw_value in (
        _clean_prompt_fragment(context.get("prompt_prefix")),
        _clean_prompt_fragment(context.get("canonical_prompt_anchor")),
    ):
        if raw_value is None:
            continue
        style_subject_fragments.extend(
            fragment.strip()
            for fragment in raw_value.split(",")
            if fragment.strip()
        )

    style_subject_fragments = filter_anchor_fragments(
        style_subject_fragments,
        anchor_filter_mode=profile.anchor_filter_mode,
    )
    if profile.subject_prominence_mode == "reduced":
        reduced_subject_markers = (
            "tasteful adult allure",
            "high-response beauty editorial",
            "beauty editorial",
            "strong eye contact",
            "luminous skin",
            "refined facial features",
            "refined facial structure",
            "high-fashion poise",
            "elegant proportions",
            "glamour shoot",
            "glamour pose",
            "fashion shoot",
            "fashion editorial",
            "close portrait",
            "airbrushed skin",
            "copy-paste framing",
            "copy-paste composition",
            "beauty key visual",
            "single-subject glamour poster",
            "pinup composition",
            "subject filling frame",
            "allure",
            "beauty",
            "editorial",
            "glamour",
            "portrait",
        )

        def _is_reduced_subject_fragment(fragment: str) -> bool:
            normalized_fragment = fragment.lower()
            return any(marker in normalized_fragment for marker in reduced_subject_markers)

        style_subject_fragments = [
            fragment
            for fragment in style_subject_fragments
            if not _is_reduced_subject_fragment(fragment)
        ]
    style_and_subject = ", ".join(style_subject_fragments)
    cleaned = _build_panel_story_prompt_sentences(
        context,
        profile=profile,
        style_and_subject=style_and_subject,
        include_quality_focus=True,
    )
    if not cleaned:
        raise ValueError("Comic panel render prompt has no content")
    return " ".join(cleaned)


def merge_negative_prompt(
    base_negative_prompt: str | None,
    negative_prompt_append: str,
) -> str | None:
    base = base_negative_prompt.strip() if isinstance(base_negative_prompt, str) else ""
    append = negative_prompt_append.strip()
    if base and append:
        return f"{base}, {append}"
    if base:
        return base
    if append:
        return append
    return None


_QUALITY_HINT_MARKERS: dict[str, tuple[str, ...]] = {
    "room readability": ("room readability", "room and props readable"),
    "reduced subject occupancy": (
        "reduced subject occupancy",
        "subject smaller in frame",
        "subject kept secondary to the room",
    ),
    "environment depth": ("environment depth", "room depth"),
    "expression readability": ("expression readability", "expression reads clearly"),
    "natural body pose": ("natural body pose", "natural pose", "believable pose"),
    "clear hand acting": ("clear hand acting", "clear hand pose", "hands read clearly"),
    "prop readability": ("prop readability", "prop reads clearly"),
    "action readability": ("action readability", "action reads clearly"),
    "hand-prop contact": ("hand-prop contact", "hand touching prop", "thumb contact"),
    "emotion clarity": ("emotion clarity", "emotion reads clearly"),
    "alive eyes": ("alive eyes", "eyes feel alive"),
    "artifact suppression": ("artifact suppression", "artifact free", "artifact control"),
}

_QUALITY_PENALTY_MARKERS: dict[str, tuple[str, ...]] = {
    "waxy skin": ("waxy skin", "waxy face", "plastic skin", "airbrushed skin"),
    "dead eyes": ("dead eyes", "lifeless eyes", "empty stare"),
    "malformed hands": (
        "malformed hands",
        "bad hands",
        "poorly drawn hands",
        "extra fingers",
        "fused fingers",
    ),
    "floating props": ("floating props", "floating prop", "detached prop", "prop floating"),
    "empty establish room": (
        "empty establish room",
        "empty room",
        "minimal room detail",
        "empty background",
    ),
    "portrait pull on non-closeup role": (
        "portrait pull",
        "single-subject glamour poster",
        "beauty key visual",
        "pinup composition",
        "close portrait",
        "fashion editorial",
        "beauty editorial",
        "glamour poster",
    ),
    "text artifact overlay": (
        "unreadable text",
        "random text",
        "gibberish text",
        "logo",
        "watermark",
        "subtitle overlay",
        "caption box",
        "speech bubble outline",
    ),
    "camera frame overlay": (
        "camera frame",
        "viewfinder",
        "screenshot border",
        "interface overlay",
        "recording overlay",
        "ui overlay",
    ),
}

_QUALITY_PENALTY_WEIGHTS: dict[str, float] = {
    "waxy skin": 0.18,
    "dead eyes": 0.14,
    "malformed hands": 0.20,
    "floating props": 0.18,
    "empty establish room": 0.22,
    "portrait pull on non-closeup role": 0.20,
    "text artifact overlay": 0.30,
    "camera frame overlay": 0.24,
}

_IDENTITY_POSITIVE_WEIGHTS: dict[str, float] = {
    "single subject": 0.06,
    "single face": 0.14,
    "camila hair color match": 0.18,
    "camila hair length match": 0.12,
    "camila hair texture match": 0.08,
    "camila skin tone match": 0.08,
    "camila visual hair reference match": 0.24,
    "camila visual skin reference match": 0.20,
}

_IDENTITY_NEGATIVE_WEIGHTS: dict[str, float] = {
    "no readable face": 0.22,
    "multiple faces": 0.24,
    "camila hair color drift": 0.26,
    "camila hair length drift": 0.18,
    "camila skin tone drift": 0.16,
    "face integrity issue": 0.20,
    "camila visual hair drift": 0.34,
    "camila visual skin drift": 0.50,
    "camila wardrobe drift": 0.40,
    "camila youth drift": 0.44,
    "camila reference descriptor missing": 0.32,
    "identity analysis unavailable": 0.80,
}

_CAMILA_HAIR_COLOR_MATCH_TAGS = {"brown_hair"}
_CAMILA_HAIR_COLOR_DRIFT_TAGS = {
    "black_hair",
    "blonde_hair",
    "white_hair",
    "grey_hair",
    "red_hair",
    "blue_hair",
    "green_hair",
    "pink_hair",
    "purple_hair",
}
_CAMILA_HAIR_LENGTH_MATCH_TAGS = {"long_hair", "very_long_hair"}
_CAMILA_HAIR_LENGTH_DRIFT_TAGS = {"short_hair", "bob_cut"}
_CAMILA_HAIR_TEXTURE_MATCH_TAGS = {"wavy_hair", "curly_hair"}
_CAMILA_SKIN_TONE_MATCH_TAGS = {"tan", "tanned_skin", "dark_skin"}
_CAMILA_SKIN_TONE_DRIFT_TAGS = {"pale_skin"}
_FACE_INTEGRITY_BAD_TAGS = {"bad_face", "poorly_drawn_face", "duplicate_faces"}
_CAMILA_V2_CANON_ID = "camila_v2"
_IDENTITY_GATE_FINAL_SCORE_CAP = 0.24
_ROLE_IDENTITY_THRESHOLDS: dict[str, float] = {
    "establish": 0.42,
    "beat": 0.56,
    "insert": 0.32,
    "closeup": 0.62,
}
_ROLE_SELECTION_THRESHOLDS: dict[str, float] = {
    "establish": 0.38,
    "beat": 0.48,
    "insert": 0.30,
    "closeup": 0.54,
}


def _normalize_quality_signal_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().lower()
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _normalize_quality_assessment_payload(
    assessment_payload: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    if not isinstance(assessment_payload, dict):
        return [], []

    positive = _normalize_quality_signal_list(
        assessment_payload.get("positive_signals", assessment_payload.get("strengths"))
    )
    negative = _normalize_quality_signal_list(
        assessment_payload.get("negative_signals", assessment_payload.get("issues"))
    )
    return positive, negative


def _normalize_identity_signal_list(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip().lower()
        if cleaned:
            normalized.append(cleaned)
    return normalized


def _normalize_identity_assessment_payload(
    assessment_payload: dict[str, Any] | None,
) -> tuple[list[str], list[str]]:
    if not isinstance(assessment_payload, dict):
        return [], []

    positive = _normalize_identity_signal_list(
        assessment_payload.get("identity_positive_signals")
    )
    negative = _normalize_identity_signal_list(
        assessment_payload.get("identity_negative_signals")
    )
    return positive, negative


def _extract_quality_assessment_payload(request_json: dict[str, Any]) -> dict[str, Any] | None:
    if not request_json:
        return None

    for key in (
        "quality_assessment",
        "assessment",
        "candidate_assessment",
        "vision_assessment",
    ):
        value = request_json.get(key)
        if isinstance(value, dict):
            return value

    for nested_key in ("comic", "worker", "result", "output"):
        nested = request_json.get(nested_key)
        if isinstance(nested, dict):
            nested_payload = _extract_quality_assessment_payload(nested)
            if nested_payload is not None:
                return nested_payload
    return None


def _extract_identity_assessment_payload(request_json: dict[str, Any]) -> dict[str, Any] | None:
    assessment_payload = _extract_quality_assessment_payload(request_json)
    if not isinstance(assessment_payload, dict):
        return None
    if (
        "identity_positive_signals" in assessment_payload
        or "identity_negative_signals" in assessment_payload
    ):
        return assessment_payload
    return None


def _resolve_role_threshold(panel_type: str | None, *, thresholds: dict[str, float]) -> float:
    normalized = str(panel_type or "").strip().lower()
    return thresholds.get(normalized, thresholds["beat"])


def _assess_panel_candidate_identity(
    *,
    panel_type: str | None,
    assessment_payload: dict[str, Any] | None,
) -> tuple[float, list[str]]:
    positive_signals, negative_signals = _normalize_identity_assessment_payload(
        assessment_payload
    )
    score = 0.5
    notes: list[str] = []

    for signal in positive_signals:
        weight = _IDENTITY_POSITIVE_WEIGHTS.get(signal)
        if weight is None:
            continue
        score += weight
        notes.append(f"identity reward: {signal}")

    for signal in negative_signals:
        weight = _IDENTITY_NEGATIVE_WEIGHTS.get(signal)
        if weight is None:
            continue
        score -= weight
        notes.append(f"identity penalty: {signal}")

    threshold = _resolve_role_threshold(
        panel_type,
        thresholds=_ROLE_IDENTITY_THRESHOLDS,
    )
    notes.append(f"identity score: {round(max(0.0, min(1.0, score)), 4)}")
    notes.append(f"identity threshold: {threshold}")
    return round(max(0.0, min(1.0, score)), 4), notes


def _blend_candidate_selection_score(
    *,
    panel_type: str | None,
    quality_score: float | None,
    quality_notes: list[str],
    identity_score: float | None,
    identity_notes: list[str],
) -> tuple[float | None, list[str]]:
    if identity_score is None and quality_score is None:
        return None, []

    notes = [*identity_notes, *quality_notes]
    if identity_score is None:
        return quality_score, notes

    threshold = _resolve_role_threshold(
        panel_type,
        thresholds=_ROLE_IDENTITY_THRESHOLDS,
    )
    if identity_score < threshold:
        notes.append("identity gate: failed")
        gated_score = min(
            _IDENTITY_GATE_FINAL_SCORE_CAP,
            round(max(0.0, identity_score) * 0.5, 4),
        )
        return gated_score, notes

    notes.append("identity gate: passed")
    effective_quality = quality_score if quality_score is not None else 0.5
    blended = round((identity_score * 0.6) + (effective_quality * 0.4), 4)
    return blended, notes


def select_best_render_asset_for_selection(
    render_assets: list[dict[str, Any]],
    *,
    panel_type: str | None,
) -> dict[str, Any] | None:
    threshold = _resolve_role_threshold(
        panel_type,
        thresholds=_ROLE_SELECTION_THRESHOLDS,
    )
    candidates = [
        asset
        for asset in render_assets
        if str(asset.get("storage_path") or "").strip()
    ]
    if not candidates:
        return None

    ranked = sorted(
        candidates,
        key=lambda asset: (
            -float(asset.get("quality_score") or 0.0),
            str(asset.get("id") or ""),
        ),
    )
    for asset in ranked:
        score = asset.get("quality_score")
        if isinstance(score, (int, float)) and float(score) >= threshold:
            return asset
    return None


def _resolve_primary_face_box(
    face_boxes: list[tuple[int, int, int, int]],
) -> tuple[int, int, int, int] | None:
    if not face_boxes:
        return None
    return max(face_boxes, key=lambda box: int(box[2]) * int(box[3]))


def _crop_region_metrics(
    image: Image.Image,
    *,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> tuple[float, float] | None:
    clamped_left = max(0, min(int(left), image.width))
    clamped_top = max(0, min(int(top), image.height))
    clamped_right = max(clamped_left + 1, min(int(right), image.width))
    clamped_bottom = max(clamped_top + 1, min(int(bottom), image.height))
    if clamped_right <= clamped_left or clamped_bottom <= clamped_top:
        return None

    crop = image.crop((clamped_left, clamped_top, clamped_right, clamped_bottom)).convert("RGB")
    arr = np.asarray(crop, dtype=np.float32)
    if arr.size == 0:
        return None
    rgb_mean = arr.mean(axis=(0, 1))
    brightness = float(rgb_mean.mean() / 255.0)
    warmth = float((rgb_mean[0] - rgb_mean[2]) / 255.0)
    return brightness, warmth


def _derive_camila_v2_visual_reference_signals(
    *,
    image_path: Path,
    face_boxes: list[tuple[int, int, int, int]],
) -> tuple[list[str], list[str]]:
    primary_face = _resolve_primary_face_box(face_boxes)
    if primary_face is None:
        return [], ["camila reference descriptor missing"]

    canon = get_character_canon_v2(_CAMILA_V2_CANON_ID)
    x, y, w, h = primary_face
    with Image.open(image_path) as image:
        hair_metrics = _crop_region_metrics(
            image,
            left=x + int(w * 0.08),
            top=y - int(h * 0.45),
            right=x + int(w * 0.92),
            bottom=y + int(h * 0.12),
        )
        skin_metrics = _crop_region_metrics(
            image,
            left=x + int(w * 0.22),
            top=y + int(h * 0.40),
            right=x + int(w * 0.78),
            bottom=y + int(h * 0.82),
        )

    positive: list[str] = []
    negative: list[str] = []

    if hair_metrics is None:
        negative.append("camila reference descriptor missing")
    else:
        hair_brightness, hair_warmth = hair_metrics
        hair_brightness_min, hair_brightness_max = canon.reference_hair_brightness_range
        hair_warmth_min, hair_warmth_max = canon.reference_hair_warmth_range
        if (
            hair_brightness_min <= hair_brightness <= hair_brightness_max
            and hair_warmth_min <= hair_warmth <= hair_warmth_max
        ):
            positive.append("camila visual hair reference match")
        else:
            negative.append("camila visual hair drift")

    if skin_metrics is None:
        if "camila reference descriptor missing" not in negative:
            negative.append("camila reference descriptor missing")
    else:
        skin_brightness, skin_warmth = skin_metrics
        skin_brightness_min, skin_brightness_max = canon.reference_skin_brightness_range
        skin_warmth_min, skin_warmth_max = canon.reference_skin_warmth_range
        if (
            skin_brightness_min <= skin_brightness <= skin_brightness_max
            and skin_warmth_min <= skin_warmth <= skin_warmth_max
        ):
            positive.append("camila visual skin reference match")
        else:
            negative.append("camila visual skin drift")

    return positive, negative


async def _derive_camila_v2_identity_assessment_from_output(
    *,
    local_output_path: Path,
) -> dict[str, Any] | None:
    analysis = await analyze_image(str(local_output_path))
    wd14 = analysis.get("wd14") if isinstance(analysis, dict) else None
    all_tags = wd14.get("all_tags") if isinstance(wd14, dict) else {}
    bad_tags = wd14.get("bad_tags") if isinstance(wd14, dict) else []
    if not isinstance(all_tags, dict):
        all_tags = {}
    tags = {str(tag).strip().lower() for tag in all_tags.keys()}

    positive: list[str] = []
    negative: list[str] = []

    if {"1girl", "solo"} & tags:
        positive.append("single subject")
    if tags & _CAMILA_HAIR_COLOR_MATCH_TAGS:
        positive.append("camila hair color match")
    if tags & _CAMILA_HAIR_LENGTH_MATCH_TAGS:
        positive.append("camila hair length match")
    if tags & _CAMILA_HAIR_TEXTURE_MATCH_TAGS:
        positive.append("camila hair texture match")
    if tags & _CAMILA_SKIN_TONE_MATCH_TAGS:
        positive.append("camila skin tone match")

    if tags & _CAMILA_HAIR_COLOR_DRIFT_TAGS:
        negative.append("camila hair color drift")
    if tags & _CAMILA_HAIR_LENGTH_DRIFT_TAGS:
        negative.append("camila hair length drift")
    if tags & _CAMILA_SKIN_TONE_DRIFT_TAGS:
        negative.append("camila skin tone drift")
    if set(str(tag).strip().lower() for tag in bad_tags if isinstance(tag, str)) & _FACE_INTEGRITY_BAD_TAGS:
        negative.append("face integrity issue")

    face_boxes = await asyncio.to_thread(detect_faces, local_output_path)
    face_count = len(face_boxes)
    if face_count == 1:
        positive.append("single face")
    elif face_count == 0:
        negative.append("no readable face")
    else:
        negative.append("multiple faces")

    reference_positive, reference_negative = await asyncio.to_thread(
        _derive_camila_v2_visual_reference_signals,
        image_path=local_output_path,
        face_boxes=face_boxes,
    )
    for signal in reference_positive:
        if signal not in positive:
            positive.append(signal)
    for signal in reference_negative:
        if signal not in negative:
            negative.append(signal)

    canon = get_character_canon_v2(_CAMILA_V2_CANON_ID)
    if tags & set(canon.forbidden_wardrobe_tags):
        negative.append("camila wardrobe drift")
    if tags & set(canon.forbidden_youth_tags):
        negative.append("camila youth drift")
    if not any(
        signal in positive
        for signal in (
            "camila hair color match",
            "camila visual hair reference match",
            "camila skin tone match",
            "camila visual skin reference match",
        )
    ):
        if "camila reference descriptor missing" not in negative:
            negative.append("camila reference descriptor missing")

    if not positive and not negative:
        return None
    return {
        "identity_positive_signals": positive,
        "identity_negative_signals": negative,
    }


async def _ensure_local_callback_output_path(
    *,
    output_path: str,
    output_url: str | None,
) -> Path | None:
    normalized = str(output_path or "").strip().lstrip("/")
    if not normalized:
        return None

    local_path = (settings.DATA_DIR / normalized).resolve()
    if local_path.exists():
        return local_path

    if not output_url:
        return None

    local_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        response = await client.get(output_url)
        response.raise_for_status()
    await asyncio.to_thread(local_path.write_bytes, response.content)
    return local_path if local_path.exists() else None


def _merge_identity_assessment_payloads(
    base_payload: dict[str, Any] | None,
    derived_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if base_payload is None and derived_payload is None:
        return None
    merged: dict[str, Any] = {}
    for key in (
        "identity_positive_signals",
        "identity_negative_signals",
    ):
        values: list[str] = []
        for payload in (base_payload, derived_payload):
            if not isinstance(payload, dict):
                continue
            for value in _normalize_identity_signal_list(payload.get(key)):
                if value not in values:
                    values.append(value)
        if values:
            merged[key] = values
    return merged or None


def _merge_quality_assessment_payloads(
    base_payload: dict[str, Any] | None,
    derived_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if base_payload is None and derived_payload is None:
        return None

    merged: dict[str, Any] = {}
    positive_values: list[str] = []
    negative_values: list[str] = []
    for payload in (base_payload, derived_payload):
        if not isinstance(payload, dict):
            continue
        for value in _normalize_quality_signal_list(
            payload.get("positive_signals", payload.get("strengths"))
        ):
            if value not in positive_values:
                positive_values.append(value)
        for value in _normalize_quality_signal_list(
            payload.get("negative_signals", payload.get("issues"))
        ):
            if value not in negative_values:
                negative_values.append(value)

    if positive_values:
        merged["positive_signals"] = positive_values
    if negative_values:
        merged["negative_signals"] = negative_values
    return merged or None


def _has_camera_frame_overlay(arr: np.ndarray) -> bool:
    height, width, _ = arr.shape
    corner_h = max(72, int(height * 0.14))
    corner_w = max(72, int(width * 0.14))
    edge_h = max(10, int(height * 0.02))
    edge_w = max(10, int(width * 0.02))

    brightness = arr.mean(axis=2)
    chroma = arr.max(axis=2) - arr.min(axis=2)
    bright_white = (brightness >= 232.0) & (chroma <= 28.0)

    patches = (
        ("tl", bright_white[:corner_h, :corner_w]),
        ("tr", bright_white[:corner_h, width - corner_w :]),
        ("bl", bright_white[height - corner_h :, :corner_w]),
        ("br", bright_white[height - corner_h :, width - corner_w :]),
    )

    flagged_corners = 0
    for name, patch in patches:
        if patch.size == 0:
            continue
        if "t" in name:
            horizontal_ratio = float(patch[:edge_h, :].mean())
        else:
            horizontal_ratio = float(patch[-edge_h:, :].mean())
        if "l" in name:
            vertical_ratio = float(patch[:, :edge_w].mean())
        else:
            vertical_ratio = float(patch[:, -edge_w:].mean())
        if horizontal_ratio >= 0.06 and vertical_ratio >= 0.05:
            flagged_corners += 1

    return flagged_corners >= 2


def _has_lower_third_text_overlay(arr: np.ndarray) -> bool:
    height, width, _ = arr.shape
    top = int(height * 0.72)
    bottom = int(height * 0.97)
    left = int(width * 0.05)
    right = int(width * 0.95)
    region = arr[top:bottom, left:right]
    if region.size == 0:
        return False

    luminance = region.mean(axis=2)
    row_dark_ratio = float((luminance.mean(axis=1) < 90.0).mean())
    dark_pixel_ratio = float((luminance < 70.0).mean())
    bright_pixel_ratio = float((luminance > 220.0).mean())
    if (
        row_dark_ratio >= 0.45
        and dark_pixel_ratio >= 0.35
        and bright_pixel_ratio >= 0.004
    ):
        return True

    # Bright desks or tabletops with outlined subtitle-like text often evade the
    # coarse dark-row heuristic above. Detect them via dense local contrast in the
    # lower third combined with mixed dark/bright text colors.
    grad_x = np.abs(np.diff(luminance, axis=1))
    grad_y = np.abs(np.diff(luminance, axis=0))
    edge_ratio = float(((grad_x > 28.0).mean() + (grad_y > 28.0).mean()) / 2.0)
    dark_caption_ratio = float((luminance < 110.0).mean())
    bright_caption_ratio = float((luminance > 205.0).mean())
    return (
        edge_ratio >= 0.07
        and dark_caption_ratio >= 0.30
        and bright_caption_ratio >= 0.10
    )


def _derive_output_quality_assessment_from_output(
    image_path: Path,
) -> dict[str, Any] | None:
    with Image.open(image_path) as image:
        arr = np.asarray(image.convert("RGB"), dtype=np.float32)

    negative: list[str] = []
    if _has_camera_frame_overlay(arr):
        negative.extend(["camera frame", "viewfinder"])
    if _has_lower_third_text_overlay(arr):
        negative.extend(["subtitle overlay", "caption box", "random text"])

    if not negative:
        return None
    return {"negative_signals": negative}


def _assess_panel_candidate_quality(
    *,
    profile: Any,
    assessment_payload: dict[str, Any] | None,
) -> tuple[float, list[str]]:
    positive_signals, negative_signals = _normalize_quality_assessment_payload(
        assessment_payload
    )
    score = 0.5
    notes: list[str] = []

    for hint in getattr(profile, "quality_selector_hints", ()):
        markers = _QUALITY_HINT_MARKERS.get(str(hint), (str(hint),))
        if any(signal in markers for signal in positive_signals):
            score += 0.12
            notes.append(f"reward: {hint}")

    for label, markers in _QUALITY_PENALTY_MARKERS.items():
        if label == "empty establish room" and "establish" not in profile.panel_types:
            continue
        if label == "portrait pull on non-closeup role" and "closeup" in profile.panel_types:
            continue
        if any(signal in markers for signal in negative_signals):
            score -= _QUALITY_PENALTY_WEIGHTS[label]
            notes.append(f"penalty: {label}")

    return round(max(0.0, min(1.0, score)), 4), notes


def _build_generation_request(context: dict[str, Any]) -> GenerationCreate:
    profile = resolve_comic_panel_render_profile(context)
    if str(context.get("render_lane") or "").strip() == "character_canon_v2":
        series_style_id = str(context.get("series_style_id") or "").strip()
        binding_id = str(context.get("character_series_binding_id") or "").strip()
        if not series_style_id or not binding_id:
            raise ValueError(
                "character_canon_v2 lane requires series_style_id and character_series_binding_id"
            )
        binding = get_character_series_binding(binding_id)
        if binding.series_style_id != series_style_id:
            raise ValueError(
                "character_canon_v2 lane series_style_id does not match binding"
            )

        contract = resolve_comic_render_v2_contract(
            character_id=binding.character_id,
            series_style_id=series_style_id,
            binding_id=binding_id,
            panel_type=str(context.get("panel_type") or "").strip().lower(),
            location_label=cast(str | None, context.get("location_label")),
            continuity_notes=cast(str | None, context.get("scene_continuity_notes")),
            role_profile=profile,
        )
        execution_params = contract.execution_params
        lora_items = execution_params.get("loras", ())
        raw_v2_loras = [
            dict(item)
            for item in lora_items
            if isinstance(item, Mapping)
        ]
        filtered_v2_loras = filter_profile_loras(
            raw_v2_loras,
            lora_mode=profile.lora_mode,
        )
        resolver_sections = {
            "identity_block": [str(item) for item in contract.identity_block],
            "style_block": [str(item) for item in contract.style_block],
            "binding_block": [str(item) for item in contract.binding_block],
            "role_block": [str(item) for item in contract.role_block],
            "negative_rules": [str(item) for item in contract.negative_rules],
        }
        resolver_execution_summary = {
            key: (
                filtered_v2_loras
                if key == "loras" and isinstance(value, tuple | list)
                else value
            )
            for key, value in dict(execution_params).items()
        }
        if execution_params.get("reference_guided") is True:
            panel_type = str(context.get("panel_type") or "").strip().lower()
            binding_reference_set = binding.reference_sets.get(panel_type)
            if binding_reference_set is None:
                raise ValueError(
                    "Reference-guided comic render request missing binding reference set"
                )
            reference_images = [
                *binding_reference_set.primary,
                *binding_reference_set.secondary,
            ]
            if not reference_images:
                raise ValueError(
                    "Reference-guided comic render request missing binding reference images"
                )
            context["reference_images"] = [str(item) for item in reference_images]
            context["reference_guided"] = True
            context["still_backend_family"] = str(
                execution_params["still_backend_family"]
            )
            context["ipadapter_weight"] = _REFERENCE_GUIDED_IPADAPTER_WEIGHT
            context["ipadapter_start_at"] = _REFERENCE_GUIDED_IPADAPTER_START_AT
            context["ipadapter_end_at"] = _REFERENCE_GUIDED_IPADAPTER_END_AT
        story_prompt_fragments = _build_panel_story_prompt_sentences(
            context,
            profile=profile,
            style_and_subject=None,
            include_quality_focus=False,
        )
        prompt_fragments = [
            *resolver_sections["role_block"],
            *story_prompt_fragments,
            *(
                [
                    f"Quality focus: {', '.join(profile.quality_selector_hints)}."
                ]
                if profile.quality_selector_hints
                else []
            ),
            *resolver_sections["identity_block"],
            *resolver_sections["style_block"],
            *resolver_sections["binding_block"],
        ]
        prompt = " ".join(fragment.strip() for fragment in prompt_fragments if fragment.strip())
        if not prompt:
            raise ValueError("V2 comic render resolver returned an empty prompt")
        negative_prompt = ", ".join(
            rule.strip() for rule in resolver_sections["negative_rules"] if rule.strip()
        ) or None

        context["resolver_sections"] = resolver_sections
        context["resolver_execution_summary"] = resolver_execution_summary

        return GenerationCreate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            preserve_blank_negative_prompt=(
                not isinstance(negative_prompt, str) or not negative_prompt.strip()
            ),
            checkpoint=cast(str, execution_params["checkpoint"]),
            workflow_lane=infer_workflow_lane(cast(str, execution_params["checkpoint"])),
            loras=[
                LoraInput.model_validate(item)
                for item in filtered_v2_loras
            ],
            steps=int(execution_params["steps"]),
            cfg=float(execution_params["cfg"]),
            width=profile.width,
            height=profile.height,
            sampler=cast(str, execution_params["sampler"]),
            scheduler=cast(str, context["scheduler"]),
            clip_skip=int(context["clip_skip"]),
        )

    profile = resolve_comic_panel_render_profile(context)
    negative_prompt = context.get("negative_prompt")
    raw_loras = [
        cast(dict[str, Any], item)
        for item in _decode_json_list(cast(str | None, context.get("loras")))
    ]
    filtered_loras = filter_profile_loras(raw_loras, lora_mode=profile.lora_mode)
    merged_negative_prompt = merge_negative_prompt(
        cast(str | None, negative_prompt),
        profile.negative_prompt_append,
    )
    return GenerationCreate(
        prompt=_build_prompt(context),
        negative_prompt=merged_negative_prompt,
        preserve_blank_negative_prompt=(
            not isinstance(merged_negative_prompt, str)
            or not merged_negative_prompt.strip()
        ),
        checkpoint=cast(str, context["checkpoint"]),
        workflow_lane=cast(str, context["workflow_lane"]),
        loras=[
            LoraInput.model_validate(item)
            for item in filtered_loras
        ],
        steps=int(context["steps"]),
        cfg=float(context["cfg"]),
        width=profile.width,
        height=profile.height,
        sampler=cast(str, context["sampler"]),
        scheduler=cast(str, context["scheduler"]),
        clip_skip=int(context["clip_skip"]),
    )


async def _persist_missing_render_assets(
    *,
    panel_id: str,
    generation_rows: list[dict[str, Any]],
    prompt_snapshot: dict[str, Any],
) -> None:
    if not generation_rows:
        return

    async with get_db() as db:
        await db.execute("BEGIN")
        try:
            for generation_row in generation_rows:
                cursor = await db.execute(
                    """
                    SELECT 1
                    FROM comic_panel_render_assets
                    WHERE scene_panel_id = ? AND generation_id = ?
                    """,
                    (panel_id, generation_row["id"]),
                )
                if await cursor.fetchone() is not None:
                    continue
                await _insert_render_asset(
                    db,
                    panel_id=panel_id,
                    generation_id=cast(str, generation_row["id"]),
                    prompt_snapshot=prompt_snapshot,
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise


def _build_remote_render_job_request_json(
    *,
    panel_context: dict[str, Any],
    render_asset_id: str,
    generation_row: dict[str, Any],
) -> dict[str, Any]:
    loras = generation_row.get("loras")
    if isinstance(loras, str) and loras.strip():
        try:
            parsed_loras = json.loads(loras)
        except json.JSONDecodeError as exc:
            raise ValueError("Generation loras field is invalid JSON") from exc
    elif isinstance(loras, list):
        parsed_loras = loras
    else:
        parsed_loras = []

    comic_payload: dict[str, Any] = {
        "scene_panel_id": panel_context["id"],
        "render_asset_id": render_asset_id,
        "character_version_id": panel_context.get("character_version_id"),
    }
    optional_comic_fields = (
        "render_lane",
        "series_style_id",
        "character_series_binding_id",
        "resolver_sections",
        "resolver_execution_summary",
    )
    for field in optional_comic_fields:
        value = panel_context.get(field)
        if value is not None:
            comic_payload[field] = value

    request_json = {
        "backend_family": "sdxl_still",
        "model_profile": "comic_panel_sdxl_v1",
        "still_generation": {
            "prompt": generation_row.get("prompt"),
            "negative_prompt": generation_row.get("negative_prompt"),
            "checkpoint": generation_row.get("checkpoint"),
            "loras": parsed_loras,
            "seed": generation_row.get("seed"),
            "steps": generation_row.get("steps"),
            "cfg": generation_row.get("cfg"),
            "width": generation_row.get("width"),
            "height": generation_row.get("height"),
            "sampler": generation_row.get("sampler"),
            "scheduler": generation_row.get("scheduler"),
            "clip_skip": generation_row.get("clip_skip"),
            "source_id": generation_row.get("source_id"),
        },
        "comic": comic_payload,
    }
    request_json.update(
        _resolve_reference_guided_still_request_metadata(panel_context=panel_context)
    )
    return request_json


async def _create_missing_remote_render_jobs(
    *,
    panel_context: dict[str, Any],
    source_id: str,
    generation_rows: list[dict[str, Any]],
    render_assets: list[ComicPanelRenderAssetResponse],
) -> list[dict[str, Any]]:
    render_asset_by_generation_id = {
        asset.generation_id: asset for asset in render_assets
    }
    async with get_db() as db:
        await db.execute("BEGIN")
        try:
            for request_index, generation_row in enumerate(generation_rows):
                generation_id = cast(str, generation_row["id"])
                cursor = await db.execute(
                    """
                    SELECT 1
                    FROM comic_render_jobs
                    WHERE generation_id = ?
                    """,
                    (generation_id,),
                )
                if await cursor.fetchone() is not None:
                    continue
                render_asset = render_asset_by_generation_id.get(generation_id)
                if render_asset is None:
                    raise RuntimeError(
                        f"Missing comic render asset for generation {generation_id}"
                    )
                now = _now_iso()
                await db.execute(
                    """
                    INSERT INTO comic_render_jobs (
                        id,
                        scene_panel_id,
                        render_asset_id,
                        generation_id,
                        request_index,
                        source_id,
                        target_tool,
                        executor_mode,
                        executor_key,
                        status,
                        request_json,
                        external_job_id,
                        external_job_url,
                        output_path,
                        error_message,
                        submitted_at,
                        completed_at,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        panel_context["id"],
                        render_asset.id,
                        generation_id,
                        request_index,
                        source_id,
                        "comic_panel_still",
                        "remote_worker",
                        settings.ANIMATION_EXECUTOR_KEY,
                        "queued",
                        json.dumps(
                            _build_remote_render_job_request_json(
                                panel_context=panel_context,
                                render_asset_id=render_asset.id,
                                generation_row=generation_row,
                            ),
                            ensure_ascii=False,
                        ),
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        now,
                        now,
                    ),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
    return await _load_render_jobs_for_source(source_id)


async def _mark_remote_render_job_failed(
    *,
    job_id: str,
    generation_id: str,
    error_message: str,
) -> None:
    now = _now_iso()
    async with get_db() as db:
        await db.execute(
            """
            UPDATE comic_render_jobs
            SET status = 'failed',
                error_message = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (error_message, now, job_id),
        )
        await db.execute(
            """
            UPDATE generations
            SET status = 'failed',
                error_message = ?,
                completed_at = ?,
                comfyui_prompt_id = NULL
            WHERE id = ?
            """,
            (error_message, now, generation_id),
        )
        await db.commit()


async def _mark_remote_render_job_submitted(
    *,
    job_id: str,
    generation_id: str,
    external_job_id: str | None,
    external_job_url: str | None,
) -> None:
    now = _now_iso()
    async with get_db() as db:
        await db.execute(
            """
            UPDATE comic_render_jobs
            SET status = 'submitted',
                external_job_id = ?,
                external_job_url = ?,
                submitted_at = ?,
                error_message = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (external_job_id, external_job_url, now, now, job_id),
        )
        await db.execute(
            """
            UPDATE generations
            SET status = 'submitted',
                error_message = NULL,
                completed_at = NULL,
                comfyui_prompt_id = ?
            WHERE id = ?
            """,
            (external_job_id, generation_id),
        )
        await db.commit()


async def _dispatch_remote_render_jobs(
    *,
    jobs: list[dict[str, Any]],
    generation_rows: list[dict[str, Any]],
    render_assets: list[ComicPanelRenderAssetResponse],
    panel_context: dict[str, Any],
) -> list[dict[str, Any]]:
    generation_by_id = {cast(str, row["id"]): row for row in generation_rows}
    render_asset_by_generation_id = {
        asset.generation_id: {
            "id": asset.id,
            "scene_panel_id": asset.scene_panel_id,
        }
        for asset in render_assets
    }
    for job in jobs:
        if job.get("status") != "queued":
            continue
        generation = generation_by_id.get(cast(str, job["generation_id"]))
        if generation is None:
            raise RuntimeError(
                f"Missing generation for comic render job {job['id']}"
            )
        render_asset = render_asset_by_generation_id.get(cast(str, job["generation_id"]))
        if render_asset is None:
            raise RuntimeError(
                f"Missing render asset for comic render job {job['id']}"
            )
        try:
            dispatch_response = await dispatch_comic_render_job(
                job,
                generation,
                render_asset,
                panel_context,
            )
        except ComicRenderDispatchError as exc:
            await _mark_remote_render_job_failed(
                job_id=cast(str, job["id"]),
                generation_id=cast(str, job["generation_id"]),
                error_message=str(exc),
            )
            raise
        external_job_id = dispatch_response.get("job_id") or dispatch_response.get("id")
        external_job_url = dispatch_response.get("job_url") or dispatch_response.get("url")
        await _mark_remote_render_job_submitted(
            job_id=cast(str, job["id"]),
            generation_id=cast(str, job["generation_id"]),
            external_job_id=(
                str(external_job_id) if external_job_id is not None else None
            ),
            external_job_url=(
                str(external_job_url) if external_job_url is not None else None
            ),
        )
    return await _load_render_jobs_for_source(cast(str, panel_context["source_id"]))


async def queue_panel_render_candidates(
    *,
    panel_id: str,
    generation_service: GenerationService,
    candidate_count: int = 3,
    execution_mode: ComicRenderExecutionMode = "local_preview",
) -> ComicPanelRenderQueueResponse:
    context = await _load_panel_render_context(panel_id)
    profile = resolve_comic_panel_render_profile(context)
    profile_signature = _profile_signature(profile)
    source_id = _render_request_source_id(
        panel_id,
        candidate_count,
        execution_mode,
        profile_signature,
    )
    context["source_id"] = source_id
    existing_assets = await _load_reusable_render_assets_for_request(
        panel_id=panel_id,
        candidate_count=candidate_count,
        execution_mode=execution_mode,
        profile=profile,
        panel_updated_at=cast(str, context["updated_at"]),
    )
    reused_source_id, existing_assets = existing_assets
    if len(existing_assets) == candidate_count:
        existing_jobs = (
            await _load_render_jobs_for_source(reused_source_id or source_id)
            if execution_mode == "remote_worker"
            else []
        )
        if execution_mode != "remote_worker" or (
            len(existing_jobs) == candidate_count
            and not _has_queued_remote_render_job(existing_jobs)
        ):
            return _build_queue_response(
                panel=_panel_response(context),
                requested_count=candidate_count,
                queued_generation_count=len(existing_assets),
                render_assets=existing_assets,
                execution_mode=execution_mode,
                materialized_asset_count=(
                    _count_materialized_assets(existing_assets)
                    if execution_mode == "remote_worker"
                    else len(existing_assets)
                ),
                pending_render_job_count=sum(
                    1 for job in existing_jobs if _is_pending_remote_render_job(job)
                ),
                remote_job_count=len(existing_jobs),
            )

    generation = _build_generation_request(context).model_copy(
        update={"source_id": source_id}
    )
    if execution_mode == "remote_worker":
        _, queued_generations = await generation_service.create_generation_shell_batch(
            generation,
            count=candidate_count,
        )
    else:
        _, queued_generations = await generation_service.queue_generation_batch(
            generation,
            count=candidate_count,
        )
    prompt_snapshot = {
        "prompt": generation.prompt,
        "negative_prompt": generation.negative_prompt,
        "checkpoint": generation.checkpoint,
    }
    if str(context.get("render_lane") or "").strip() == "character_canon_v2":
        prompt_snapshot["render_lane"] = cast(str, context.get("render_lane"))
        prompt_snapshot["series_style_id"] = cast(str, context.get("series_style_id"))
        prompt_snapshot["character_series_binding_id"] = cast(
            str, context.get("character_series_binding_id")
        )
        prompt_snapshot["resolver_sections"] = cast(
            dict[str, Any], context.get("resolver_sections") or {}
        )
        prompt_snapshot["resolver_execution_summary"] = cast(
            dict[str, Any], context.get("resolver_execution_summary") or {}
        )
    await _persist_missing_render_assets(
        panel_id=panel_id,
        generation_rows=[
            {"id": queued_generation.id} for queued_generation in queued_generations
        ],
        prompt_snapshot=prompt_snapshot,
    )
    render_assets = await _load_render_assets_for_source(
        panel_id=panel_id,
        source_id=source_id,
    )
    if len(render_assets) != candidate_count:
        raise RuntimeError(
            f"Comic panel render queue expected {candidate_count} assets, "
            f"found {len(render_assets)}"
        )

    if execution_mode == "remote_worker":
        jobs = await _create_missing_remote_render_jobs(
            panel_context=context,
            source_id=source_id,
            generation_rows=[
                queued_generation.model_dump() for queued_generation in queued_generations
            ],
            render_assets=render_assets,
        )
        jobs = await _dispatch_remote_render_jobs(
            jobs=jobs,
            generation_rows=[
                queued_generation.model_dump() for queued_generation in queued_generations
            ],
            render_assets=render_assets,
            panel_context=context,
        )
        return _build_queue_response(
            panel=_panel_response(context),
            requested_count=candidate_count,
            queued_generation_count=len(render_assets),
            render_assets=render_assets,
            execution_mode=execution_mode,
            materialized_asset_count=_count_materialized_assets(render_assets),
            pending_render_job_count=sum(
                1 for job in jobs if _is_pending_remote_render_job(job)
            ),
            remote_job_count=len(jobs),
        )

    return _build_queue_response(
        panel=_panel_response(context),
        requested_count=candidate_count,
        queued_generation_count=len(render_assets),
        render_assets=render_assets,
        execution_mode=execution_mode,
    )


async def select_panel_render_asset(
    *,
    panel_id: str,
    asset_id: str,
) -> ComicPanelRenderAssetResponse:
    existing_asset = await _load_render_asset(panel_id=panel_id, asset_id=asset_id)
    if existing_asset is None:
        raise ValueError(f"Comic panel render asset not found: {asset_id}")

    now = _now_iso()
    async with get_db() as db:
        await db.execute(
            """
            UPDATE comic_panel_render_assets
            SET is_selected = 0,
                asset_role = CASE
                    WHEN asset_role = 'selected' THEN 'candidate'
                    ELSE asset_role
                END,
                updated_at = ?
            WHERE scene_panel_id = ? AND id <> ?
            """,
            (now, panel_id, asset_id),
        )
        await db.execute(
            """
            UPDATE comic_panel_render_assets
            SET is_selected = 1,
                asset_role = 'selected',
                updated_at = ?
            WHERE id = ? AND scene_panel_id = ?
            """,
            (now, asset_id, panel_id),
        )
        await db.commit()
        cursor = await db.execute(
            f"""
            SELECT {_RENDER_ASSET_SELECT_COLUMNS}
            FROM comic_panel_render_assets a
            LEFT JOIN generations g ON g.id = a.generation_id
            WHERE a.id = ?
            """,
            (asset_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise RuntimeError("Comic panel render asset vanished after selection")
    return _render_asset_response(cast(dict[str, Any], row))


async def list_panel_render_jobs(
    *,
    panel_id: str,
) -> list[ComicRenderJobResponse]:
    await _load_panel_render_context(panel_id)
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT *
            FROM comic_render_jobs
            WHERE scene_panel_id = ?
            ORDER BY updated_at DESC, created_at DESC, request_index DESC, id DESC
            """,
            (panel_id,),
        )
        rows = await cursor.fetchall()
    return [
        comic_render_job_response_from_row(cast(dict[str, Any], row))
        for row in rows
    ]


async def materialize_remote_render_job_callback(
    *,
    job_id: str,
    payload: AnimationJobCallbackPayload,
) -> ComicRenderJobResponse:
    async with get_db() as db:
        await db.execute("BEGIN IMMEDIATE")
        try:
            cursor = await db.execute(
                """
                SELECT *
                FROM comic_render_jobs
                WHERE id = ?
                """,
                (job_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise ValueError(f"Comic render job not found: {job_id}")
            current = cast(dict[str, Any], row)

            current_status = cast(str, current["status"])
            requested_status = payload.status or current_status
            terminal_statuses = {"completed", "failed", "cancelled"}

            if current_status in terminal_statuses:
                await db.rollback()
                return comic_render_job_response_from_row(current)

            next_status = requested_status
            next_external_job_id = (
                payload.external_job_id
                if payload.external_job_id is not None
                else current.get("external_job_id")
            )
            next_external_job_url = (
                payload.external_job_url
                if payload.external_job_url is not None
                else current.get("external_job_url")
            )
            next_output_url = payload.output_url
            next_output_path = (
                payload.output_path
                if payload.output_path is not None
                else current.get("output_path")
            )
            next_error_message = (
                payload.error_message
                if payload.error_message is not None
                else current.get("error_message")
            )
            next_request_json = _merge_request_json_payload(
                current.get("request_json"),
                payload.request_json,
            )

            if next_status == "completed" and not next_output_path:
                raise ValueError("Completed comic render callback requires output_path")
            if next_status in {"failed", "cancelled"} and not next_error_message:
                raise ValueError(
                    f"{next_status.capitalize()} comic render callback requires error_message"
                )

            now = _now_iso()
            next_submitted_at = current.get("submitted_at")
            if (
                next_status in {"submitted", "processing", "completed", "failed", "cancelled"}
                and not next_submitted_at
            ):
                next_submitted_at = now

            next_completed_at = current.get("completed_at")
            if next_status in {"completed", "failed", "cancelled"}:
                next_completed_at = next_completed_at or now

            generation_output_path = (
                next_output_path if next_status == "completed" else current.get("image_path")
            )
            asset_storage_path = (
                next_output_path
                if next_status == "completed"
                else current.get("output_path")
            )
            asset_quality_score: float | None = None
            asset_render_notes = (
                next_error_message if next_status in {"failed", "cancelled"} else None
            )
            if next_status == "completed" and isinstance(next_request_json, str):
                panel_cursor = await db.execute(
                    """
                    SELECT p.panel_type
                    FROM comic_scene_panels p
                    WHERE p.id = ?
                    """,
                    (current["scene_panel_id"],),
                )
                panel_row = await panel_cursor.fetchone()
                if panel_row is not None:
                    parsed_request_json = _parse_json_object(next_request_json)
                    assessment_payload = _extract_quality_assessment_payload(
                        parsed_request_json
                    )
                    identity_assessment_payload = _extract_identity_assessment_payload(
                        parsed_request_json
                    )
                    comic_payload = parsed_request_json.get("comic")
                    render_lane = (
                        str(comic_payload.get("render_lane") or "").strip()
                        if isinstance(comic_payload, dict)
                        else ""
                    )
                    local_output_path: Path | None = None
                    if next_output_path:
                        local_output_path = await _ensure_local_callback_output_path(
                            output_path=next_output_path,
                            output_url=next_output_url,
                        )
                        if local_output_path is not None:
                            assessment_payload = _merge_quality_assessment_payloads(
                                assessment_payload,
                                await asyncio.to_thread(
                                    _derive_output_quality_assessment_from_output,
                                    local_output_path,
                                ),
                            )
                    if render_lane == "character_canon_v2" and next_output_path:
                        if local_output_path is None:
                            identity_assessment_payload = _merge_identity_assessment_payloads(
                                identity_assessment_payload,
                                {
                                    "identity_negative_signals": [
                                        "identity analysis unavailable"
                                    ]
                                },
                            )
                        else:
                            identity_assessment_payload = _merge_identity_assessment_payloads(
                                identity_assessment_payload,
                                await _derive_camila_v2_identity_assessment_from_output(
                                    local_output_path=local_output_path,
                                ),
                            )

                    profile = resolve_comic_panel_render_profile(
                        cast(dict[str, Any], panel_row)
                    )
                    quality_notes: list[str] = []
                    readability_quality_score: float | None = None
                    if assessment_payload is not None:
                        readability_quality_score, quality_notes = _assess_panel_candidate_quality(
                            profile=profile,
                            assessment_payload=assessment_payload,
                        )

                    identity_score: float | None = None
                    identity_notes: list[str] = []
                    if identity_assessment_payload is not None:
                        identity_score, identity_notes = _assess_panel_candidate_identity(
                            panel_type=cast(str | None, panel_row.get("panel_type")),
                            assessment_payload=identity_assessment_payload,
                        )

                    asset_quality_score, blended_notes = _blend_candidate_selection_score(
                        panel_type=cast(str | None, panel_row.get("panel_type")),
                        quality_score=readability_quality_score,
                        quality_notes=quality_notes,
                        identity_score=identity_score,
                        identity_notes=identity_notes,
                    )
                    asset_render_notes = "; ".join(blended_notes) or None

            await db.execute(
                """
                UPDATE comic_render_jobs
                SET status = ?,
                    request_json = ?,
                    external_job_id = ?,
                    external_job_url = ?,
                    output_path = ?,
                    error_message = ?,
                    submitted_at = ?,
                    completed_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    next_request_json,
                    next_external_job_id,
                    next_external_job_url,
                    next_output_path,
                    next_error_message,
                    next_submitted_at,
                    next_completed_at,
                    now,
                    current["id"],
                ),
            )
            await db.execute(
                """
                UPDATE generations
                SET status = ?,
                    image_path = ?,
                    error_message = ?,
                    comfyui_prompt_id = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    generation_output_path,
                    next_error_message,
                    next_external_job_id,
                    next_completed_at,
                    current["generation_id"],
                ),
            )
            await db.execute(
                """
                UPDATE comic_panel_render_assets
                SET storage_path = ?,
                    quality_score = ?,
                    render_notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    asset_storage_path,
                    asset_quality_score,
                    asset_render_notes,
                    now,
                    current["render_asset_id"],
                ),
            )
            cursor = await db.execute(
                """
                SELECT *
                FROM comic_render_jobs
                WHERE id = ?
                """,
                (current["id"],),
            )
            row = await cursor.fetchone()
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    if row is None:
        raise RuntimeError("Comic render job vanished after callback materialization")
    return comic_render_job_response_from_row(cast(dict[str, Any], row))
