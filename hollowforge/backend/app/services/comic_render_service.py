"""Comic panel render queueing and asset selection helpers."""

from __future__ import annotations

import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, cast

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


def _build_prompt(context: dict[str, Any]) -> str:
    location_label = str(context.get("location_label") or "").strip()
    scene_continuity_notes = str(context.get("scene_continuity_notes") or "").strip()
    panel_type = str(context.get("panel_type") or "").strip()
    continuity_lock = str(context.get("continuity_lock") or "").strip()
    profile = resolve_comic_panel_render_profile(context)

    panel_type_lower = panel_type.lower()

    def _clean_fragment(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip().rstrip(" .,!?:;")
        return cleaned or None

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

    style_subject_fragments: list[str] = []
    for raw_value in (
        _clean_fragment(context.get("prompt_prefix")),
        _clean_fragment(context.get("canonical_prompt_anchor")),
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
    continuity_fragments: list[str | None] = [_clean_fragment(scene_continuity_notes)]
    cleaned_continuity_lock = _clean_fragment(continuity_lock)
    if cleaned_continuity_lock:
        primary_continuity = continuity_fragments[0]
        if primary_continuity is None or cleaned_continuity_lock not in primary_continuity:
            continuity_fragments.append(cleaned_continuity_lock)
    composition_priority_hint = {
        "establish": "environment-first framing, subject smaller in frame, room and props clearly readable",
        "beat": "subject and prop both readable in frame",
        "insert": "object-led framing, hands and invitation prioritized over a full-face portrait",
        "closeup": "emotional reaction framing with face and hands dominating the panel",
    }.get(panel_type_lower)
    setting_sentence = _build_labeled_sentence(
        "Setting",
        [f"inside {location_label}" if location_label else None],
    )
    action_sentence = _build_labeled_sentence(
        "Action",
        [_clean_fragment(context.get("action_intent"))],
    )
    emotion_sentence = _build_labeled_sentence(
        "Emotion",
        [_clean_fragment(context.get("expression_intent"))],
    )
    subject_prominence_sentence = _build_labeled_sentence(
        "Subject prominence",
        (
            [
                "keep the lead secondary to the room",
                "favor the environment over a glamour portrait",
            ]
            if profile.subject_prominence_mode == "reduced"
            else []
        ),
    )
    composition_sentence = _build_labeled_sentence(
        "Composition",
        [
            f"{panel_type_lower} manga panel" if panel_type_lower else None,
            composition_priority_hint,
            _clean_fragment(context.get("camera_intent")),
            _clean_fragment(context.get("framing")),
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
            continuity_sentence,
        ]
    cleaned = [sentence for sentence in prompt_sentences if sentence]
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
        resolver_sections = {
            "identity_block": [str(item) for item in contract.identity_block],
            "style_block": [str(item) for item in contract.style_block],
            "binding_block": [str(item) for item in contract.binding_block],
            "role_block": [str(item) for item in contract.role_block],
            "negative_rules": [str(item) for item in contract.negative_rules],
        }
        resolver_execution_summary = {
            key: (
                [dict(item) for item in value]
                if key == "loras" and isinstance(value, tuple | list)
                else value
            )
            for key, value in dict(execution_params).items()
        }
        prompt_fragments = [
            *resolver_sections["role_block"],
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
                for item in lora_items
                if isinstance(item, dict)
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

    return {
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
            asset_render_notes = (
                next_error_message if next_status in {"failed", "cancelled"} else None
            )

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
                    render_notes = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    asset_storage_path,
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
