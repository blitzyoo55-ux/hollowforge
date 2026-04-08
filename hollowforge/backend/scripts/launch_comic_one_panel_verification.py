"""Run a local-only one-panel comic production verification flow."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import launch_comic_mvp_smoke as comic_smoke
import launch_comic_production_dry_run as comic_dry_run
from app.models import ComicEpisodeDraft, ComicEpisodeSceneDraft, ComicScenePanelDraft
from app.services.comic_repository import create_comic_episode_from_draft


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TITLE = "Comic One Panel Verification"
DEFAULT_STORY_PROMPT = (
    "{character_name} pauses before the first page turn and checks whether the "
    "handoff-safe composition still reads cleanly."
)
DEFAULT_LAYOUT_TEMPLATE_ID = "jp_2x2_v1"
DEFAULT_MANUSCRIPT_PROFILE_ID = "jp_manga_rightbound_v1"


def _build_one_panel_verification_draft(
    *,
    character_version_id: str,
    lead_character_id: str,
    title: str,
    story_prompt: str,
) -> ComicEpisodeDraft:
    source_story_plan = {
        "workflow": "comic_one_panel_verification",
        "story_prompt": story_prompt,
        "scene_count": 1,
        "panel_count": 1,
    }
    return ComicEpisodeDraft(
        character_version_id=character_version_id,
        title=title,
        synopsis=story_prompt,
        source_story_plan_json=json.dumps(
            source_story_plan,
            ensure_ascii=False,
            sort_keys=True,
        ),
        continuity_summary=(
            "Verification episode for a single approved panel before full one-shot production."
        ),
        scenes=[
            ComicEpisodeSceneDraft(
                scene_no=1,
                premise=story_prompt,
                location_label="Verification Stage",
                tension="Production validation",
                reveal="Confirm one selected panel can travel through handoff export cleanly.",
                continuity_notes=(
                    "Keep identity, wardrobe, and page-safe framing stable for a single-panel check."
                ),
                involved_character_ids=[lead_character_id],
                target_panel_count=1,
            )
        ],
        panels=[
            ComicScenePanelDraft(
                scene_no=1,
                panel_no=1,
                panel_type="beat",
                framing="Single-panel verification frame",
                camera_intent=(
                    "Medium shot with page-safe negative space for balloons and SFX placement."
                ),
                action_intent=story_prompt,
                expression_intent="Controlled focus suited for production handoff review.",
                dialogue_intent=(
                    "Generate minimal verification dialogue that proves text handoff works."
                ),
                continuity_lock=(
                    "Preserve selected character identity and keep export-safe composition."
                ),
                page_target_hint=1,
                reading_order=1,
            )
        ],
    )


async def _create_one_panel_verification_episode(
    *,
    character_id: str,
    character_version_id: str,
    title: str,
    story_prompt: str,
) -> dict[str, Any]:
    draft = _build_one_panel_verification_draft(
        character_version_id=character_version_id,
        lead_character_id=character_id,
        title=title,
        story_prompt=story_prompt,
    )
    detail = await create_comic_episode_from_draft(
        character_id=character_id,
        draft=draft,
    )
    return detail.model_dump(mode="json")


def _run_production_dry_run(
    *,
    base_url: str,
    episode_id: str,
    layout_template_id: str,
    manuscript_profile_id: str,
) -> dict[str, Any]:
    episode_detail, assembly_detail, export_detail = comic_dry_run._ensure_exported_episode(
        base_url=base_url,
        episode_id=episode_id,
        layout_template_id=layout_template_id,
        manuscript_profile_id=manuscript_profile_id,
    )
    selected_panel_assets = comic_dry_run._extract_selected_panel_assets(assembly_detail)
    export_zip_path = str(export_detail.get("export_zip_path") or "").strip()
    if not export_zip_path:
        raise RuntimeError("Comic export detail is missing export_zip_path")

    comic_dry_run._validate_export_zip(export_zip_path)
    report_path = comic_dry_run._write_report(
        episode_id=episode_id,
        layout_template_id=layout_template_id,
        manuscript_profile_id=manuscript_profile_id,
        episode_detail=episode_detail,
        assembly_detail=assembly_detail,
        export_detail=export_detail,
        selected_panel_assets=selected_panel_assets,
    )
    return {
        "dry_run_success": True,
        "panel_count": len(comic_dry_run._extract_panel_ids(episode_detail)),
        "selected_panel_asset_count": len(selected_panel_assets),
        "page_count": len(export_detail.get("pages") or []),
        "export_zip_path": export_zip_path,
        "report_path": comic_dry_run._relative_data_path(report_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--character-id")
    parser.add_argument("--character-slug")
    parser.add_argument("--character-version-id")
    parser.add_argument("--story-prompt", default=DEFAULT_STORY_PROMPT)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--candidate-count", type=int, default=3)
    parser.add_argument("--render-poll-attempts", type=int, default=20)
    parser.add_argument("--render-poll-sec", type=float, default=1.0)
    parser.add_argument("--layout-template-id", default=DEFAULT_LAYOUT_TEMPLATE_ID)
    parser.add_argument(
        "--manuscript-profile-id",
        default=DEFAULT_MANUSCRIPT_PROFILE_ID,
    )
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "base_url": args.base_url.rstrip("/"),
        "episode_create_success": False,
        "queue_renders_success": False,
        "dialogues_success": False,
        "assemble_success": False,
        "export_success": False,
        "dry_run_success": False,
        "overall_success": False,
        "selected_panel_asset_count": 0,
    }
    current_step = "bootstrap"

    try:
        if not comic_smoke._is_local_backend_url(args.base_url):
            raise RuntimeError(
                "Comic one-panel verification only supports local backend URLs"
            )

        current_step = "resolve_character_context"
        character, version, characters, versions = comic_smoke._resolve_character_and_version(
            base_url=args.base_url,
            character_version_id=args.character_version_id,
            character_id=args.character_id,
            character_slug=args.character_slug,
        )
        summary["character_count"] = len(characters)
        summary["character_version_count"] = len(versions)
        summary["character_id"] = character.get("id")
        summary["character_slug"] = character.get("slug")
        summary["character_version_id"] = version.get("id")

        current_step = "create_episode"
        story_prompt = comic_smoke._render_story_prompt(
            args.story_prompt,
            character_name=str(character.get("name") or "Lead"),
            character_slug=str(character.get("slug") or ""),
        )
        episode_detail = asyncio.run(
            _create_one_panel_verification_episode(
                character_id=str(character["id"]),
                character_version_id=str(version["id"]),
                title=args.title,
                story_prompt=story_prompt,
            )
        )
        episode_id = comic_smoke._extract_episode_id(episode_detail)
        panel_id = comic_smoke._extract_first_panel_id(episode_detail)
        summary["episode_create_success"] = True
        summary["episode_id"] = episode_id
        summary["panel_id"] = panel_id
        summary["panel_count"] = len(comic_smoke._extract_panel_ids(episode_detail))

        current_step = "queue_renders"
        queue_response, selected_asset, _ = comic_smoke._queue_and_select_panel_asset(
            base_url=args.base_url,
            panel_id=panel_id,
            candidate_count=args.candidate_count,
            poll_attempts=args.render_poll_attempts,
            poll_sec=args.render_poll_sec,
            allow_synthetic_asset_fallback=False,
        )
        render_assets = comic_smoke._require_list(
            queue_response.get("render_assets") or [],
            label=f"comic panel render assets {panel_id}",
        )
        summary["queue_renders_success"] = True
        summary["queued_generation_count"] = int(queue_response.get("queued_generation_count") or 0)
        summary["render_asset_count"] = len(render_assets)
        summary["selected_panel_asset_count"] = 1
        summary["selected_render_asset_id"] = selected_asset.get("id")

        current_step = "draft_dialogues"
        dialogue_response = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(
                    args.base_url,
                    f"/api/v1/comic/panels/{panel_id}/dialogues/generate",
                ),
            ),
            label="comic one-panel dialogue generation",
        )
        summary["dialogues_success"] = True
        summary["generated_dialogue_count"] = int(dialogue_response.get("generated_count") or 0)

        current_step = "assemble_pages"
        assembly_response = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(
                    args.base_url,
                    f"/api/v1/comic/episodes/{episode_id}/pages/assemble",
                    {
                        "layout_template_id": args.layout_template_id,
                        "manuscript_profile_id": args.manuscript_profile_id,
                    },
                ),
            ),
            label="comic one-panel assembly",
        )
        summary["assemble_success"] = True
        summary["page_count"] = len(assembly_response.get("pages") or [])

        current_step = "export_pages"
        export_response = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(
                    args.base_url,
                    f"/api/v1/comic/episodes/{episode_id}/pages/export",
                    {
                        "layout_template_id": args.layout_template_id,
                        "manuscript_profile_id": args.manuscript_profile_id,
                    },
                ),
            ),
            label="comic one-panel export",
        )
        summary["export_success"] = True
        summary["export_zip_path"] = export_response.get("export_zip_path")

        current_step = "production_dry_run"
        dry_run_summary = _run_production_dry_run(
            base_url=args.base_url,
            episode_id=episode_id,
            layout_template_id=args.layout_template_id,
            manuscript_profile_id=args.manuscript_profile_id,
        )
        summary["dry_run_success"] = bool(dry_run_summary.get("dry_run_success"))
        summary["report_path"] = dry_run_summary.get("report_path")
        summary["page_count"] = dry_run_summary.get("page_count")
        summary["selected_panel_asset_count"] = dry_run_summary.get(
            "selected_panel_asset_count"
        )
        summary["overall_success"] = True
        return 0
    except Exception as exc:  # pragma: no cover - CLI flow marker handling
        summary["error"] = str(exc)
        summary["failed_step"] = current_step
        return 1
    finally:
        for key, value in summary.items():
            comic_smoke._print_marker(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
