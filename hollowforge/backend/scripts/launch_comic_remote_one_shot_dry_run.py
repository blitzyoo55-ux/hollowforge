"""Run a stable remote-worker one-shot comic production dry-run."""

from __future__ import annotations

import argparse
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
import launch_comic_remote_render_smoke as remote_smoke


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TITLE = "Comic Remote One Shot Dry Run"
DEFAULT_STORY_PROMPT = (
    "{character_name} advances through a short manga one-shot so the remote still-render "
    "lane can be validated through export and handoff."
)
DEFAULT_STORY_LANE = "adult_nsfw"
DEFAULT_LAYOUT_TEMPLATE_ID = "jp_2x2_v1"
DEFAULT_MANUSCRIPT_PROFILE_ID = "jp_manga_rightbound_v1"
DEFAULT_PANEL_MULTIPLIER = 1
DEFAULT_EXECUTION_MODE = remote_smoke.DEFAULT_EXECUTION_MODE
DEFAULT_RENDER_POLL_ATTEMPTS = 360


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
    parser.add_argument("--story-lane", default=DEFAULT_STORY_LANE)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--panel-multiplier", type=int, default=DEFAULT_PANEL_MULTIPLIER)
    parser.add_argument("--candidate-count", type=int, default=3)
    parser.add_argument("--render-poll-attempts", type=int, default=DEFAULT_RENDER_POLL_ATTEMPTS)
    parser.add_argument("--render-poll-sec", type=float, default=1.0)
    parser.add_argument("--layout-template-id", default=DEFAULT_LAYOUT_TEMPLATE_ID)
    parser.add_argument("--manuscript-profile-id", default=DEFAULT_MANUSCRIPT_PROFILE_ID)
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "base_url": args.base_url.rstrip("/"),
        "execution_mode": DEFAULT_EXECUTION_MODE,
        "episode_create_success": False,
        "queue_renders_success": False,
        "dialogues_success": False,
        "assemble_success": False,
        "export_success": False,
        "dry_run_success": False,
        "overall_success": False,
        "selected_panel_asset_count": 0,
        "materialized_asset_count": 0,
    }
    current_step = "bootstrap"

    try:
        if not comic_smoke._is_local_backend_url(args.base_url):
            raise RuntimeError(
                "Comic remote one-shot dry-run only supports local backend URLs"
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

        current_step = "plan_story"
        story_prompt = comic_smoke._render_story_prompt(
            args.story_prompt,
            character_name=str(character.get("name") or "Lead"),
            character_slug=str(character.get("slug") or ""),
        )
        approved_plan = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(args.base_url, "/api/v1/tools/story-planner/plan"),
                {
                    "story_prompt": story_prompt,
                    "lane": args.story_lane,
                },
            ),
            label="comic remote one-shot story plan",
        )
        summary["story_prompt"] = approved_plan.get("story_prompt") or story_prompt
        summary["story_lane"] = approved_plan.get("lane") or args.story_lane
        summary["approval_token"] = approved_plan.get("approval_token")

        current_step = "import_story_plan"
        episode_detail = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(args.base_url, "/api/v1/comic/episodes/import-story-plan"),
                {
                    "approved_plan": approved_plan,
                    "character_version_id": version["id"],
                    "title": args.title,
                    "panel_multiplier": args.panel_multiplier,
                },
            ),
            label="comic remote one-shot story import",
        )
        episode_id = comic_smoke._extract_episode_id(episode_detail)
        panel_ids = comic_smoke._extract_panel_ids(episode_detail)
        summary["episode_create_success"] = True
        summary["episode_id"] = episode_id
        summary["panel_count"] = len(panel_ids)
        summary["scene_count"] = len(episode_detail.get("scenes") or [])

        current_step = "queue_renders"
        queued_generation_count = 0
        render_asset_count = 0
        selected_panel_asset_count = 0
        materialized_asset_count = 0
        remote_job_count = 0
        selected_render_asset_ids: list[str] = []
        for panel_id in panel_ids:
            queue_response, selected_asset, render_jobs = (
                remote_smoke._queue_and_select_remote_panel_asset(
                    base_url=args.base_url,
                    panel_id=panel_id,
                    candidate_count=args.candidate_count,
                    poll_attempts=args.render_poll_attempts,
                    poll_sec=args.render_poll_sec,
                )
            )
            render_assets = comic_smoke._require_list(
                queue_response.get("render_assets") or [],
                label=f"comic remote one-shot render assets {panel_id}",
            )
            queued_generation_count += int(queue_response.get("queued_generation_count") or 0)
            render_asset_count += len(render_assets)
            remote_job_count += len(render_jobs)
            materialized_asset_count += sum(
                1 for job in render_jobs if str(job.get("output_path") or "").strip()
            )
            selected_panel_asset_count += 1
            selected_render_asset_id = str(selected_asset.get("id") or "").strip()
            if selected_render_asset_id:
                selected_render_asset_ids.append(selected_render_asset_id)

        summary["queue_renders_success"] = True
        summary["queued_generation_count"] = queued_generation_count
        summary["render_asset_count"] = render_asset_count
        summary["remote_job_count"] = remote_job_count
        summary["materialized_asset_count"] = materialized_asset_count
        summary["selected_panel_asset_count"] = selected_panel_asset_count
        summary["selected_render_asset_ids"] = ",".join(selected_render_asset_ids)

        current_step = "draft_dialogues"
        generated_dialogue_count = 0
        for panel_id in panel_ids:
            dialogue_response = comic_smoke._require_object(
                comic_smoke._request_json(
                    "POST",
                    comic_smoke._build_url(
                        args.base_url,
                        f"/api/v1/comic/panels/{panel_id}/dialogues/generate",
                    ),
                ),
                label=f"comic remote one-shot dialogue generation {panel_id}",
            )
            generated_dialogue_count += int(dialogue_response.get("generated_count") or 0)
        summary["dialogues_success"] = True
        summary["generated_dialogue_count"] = generated_dialogue_count

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
            label="comic remote one-shot assembly",
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
            label="comic remote one-shot export",
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
        summary["page_count"] = int(dry_run_summary.get("page_count") or summary["page_count"])
        summary["selected_panel_asset_count"] = int(
            dry_run_summary.get("selected_panel_asset_count")
            or summary["selected_panel_asset_count"]
        )
        summary["dry_run_report_path"] = dry_run_summary.get("report_path")
        summary["export_zip_path"] = dry_run_summary.get("export_zip_path") or summary.get(
            "export_zip_path"
        )

        summary["overall_success"] = True
        exit_code = 0
    except Exception as exc:
        summary["failed_step"] = current_step
        summary["error"] = str(exc)
        exit_code = 1

    for key, value in summary.items():
        comic_smoke._print_marker(key, value)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
