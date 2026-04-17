"""Run a bounded remote comic still render smoke flow against a local backend."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import launch_comic_mvp_smoke as comic_smoke
from comic_verification_profiles import FULL_PROFILE


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TITLE = "Comic Remote Render Smoke"
DEFAULT_STORY_PROMPT = (
    "{character_name} pauses in a private lounge and studies whether the "
    "first panel can survive the remote still-render lane."
)
DEFAULT_STORY_LANE = "adult_nsfw"
DEFAULT_EXECUTION_MODE = "remote_worker"
DEFAULT_RENDER_POLL_ATTEMPTS = FULL_PROFILE.render_poll_attempts
DEFAULT_RENDER_POLL_SEC = FULL_PROFILE.render_poll_sec


def _assert_remote_queue_response(
    queue_response: dict[str, Any],
) -> None:
    execution_mode = str(queue_response.get("execution_mode") or "").strip()
    if execution_mode != DEFAULT_EXECUTION_MODE:
        raise RuntimeError(
            "Comic remote render smoke did not stay on execution_mode=remote_worker"
        )
    remote_job_count = int(queue_response.get("remote_job_count") or 0)
    if remote_job_count < 1:
        raise RuntimeError(
            "Comic remote render smoke did not create any remote render jobs"
        )


def _assert_selected_asset_contract(selected_asset: dict[str, Any]) -> None:
    if selected_asset.get("is_selected") is not True:
        raise RuntimeError(
            "Selected remote render asset must be marked as selected"
        )
    asset_role = str(selected_asset.get("asset_role") or "").strip().lower()
    if asset_role != "selected":
        raise RuntimeError(
            "Selected remote render asset must have asset_role=selected"
        )
    if not str(selected_asset.get("storage_path") or "").strip():
        raise RuntimeError("Selected remote render asset is missing storage_path")


def _poll_render_jobs_for_materialized_assets(
    *,
    base_url: str,
    panel_id: str,
    expected_asset_ids: set[str],
    poll_attempts: int,
    poll_sec: float,
) -> list[dict[str, Any]]:
    render_jobs_url = comic_smoke._build_url(
        base_url,
        f"/api/v1/comic/panels/{panel_id}/render-jobs",
    )
    last_relevant_jobs: list[dict[str, Any]] = []

    for attempt in range(poll_attempts):
        jobs = comic_smoke._require_list(
            comic_smoke._request_json("GET", render_jobs_url),
            label=f"comic remote render jobs {panel_id}",
        )
        relevant_jobs = [
            job
            for job in jobs
            if str(job.get("render_asset_id") or "") in expected_asset_ids
        ]
        last_relevant_jobs = relevant_jobs
        if any(str(job.get("output_path") or "").strip() for job in relevant_jobs):
            return relevant_jobs
        if attempt + 1 < poll_attempts:
            time.sleep(max(0.1, poll_sec))

    return last_relevant_jobs


def _queue_and_select_remote_panel_asset(
    *,
    base_url: str,
    panel_id: str,
    candidate_count: int,
    poll_attempts: int,
    poll_sec: float,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    queue_url = comic_smoke._build_url(
        base_url,
        f"/api/v1/comic/panels/{panel_id}/queue-renders",
        {
            "candidate_count": candidate_count,
            "execution_mode": DEFAULT_EXECUTION_MODE,
        },
    )
    queue_response = comic_smoke._require_object(
        comic_smoke._request_json("POST", queue_url),
        label=f"comic remote render queue {panel_id}",
    )
    _assert_remote_queue_response(queue_response)
    render_assets = comic_smoke._require_list(
        queue_response.get("render_assets") or [],
        label=f"comic remote render assets {panel_id}",
    )
    expected_asset_ids = {
        str(asset.get("id") or "").strip()
        for asset in render_assets
        if str(asset.get("id") or "").strip()
    }
    render_jobs = _poll_render_jobs_for_materialized_assets(
        base_url=base_url,
        panel_id=panel_id,
        expected_asset_ids=expected_asset_ids,
        poll_attempts=poll_attempts,
        poll_sec=poll_sec,
    )
    materialized_job = next(
        (
            job
            for job in render_jobs
            if str(job.get("output_path") or "").strip()
            and str(job.get("status") or "").strip().lower() == "completed"
        ),
        None,
    )
    if materialized_job is None:
        raise TimeoutError(
            f"Comic remote render smoke did not materialize a real asset for panel {panel_id}"
        )
    render_asset_id = str(materialized_job.get("render_asset_id") or "").strip()
    if not render_asset_id:
        raise RuntimeError("Materialized comic render job is missing render_asset_id")

    selected_asset = comic_smoke._require_object(
        comic_smoke._request_json(
            "POST",
            comic_smoke._build_url(
                base_url,
                f"/api/v1/comic/panels/{panel_id}/assets/{render_asset_id}/select",
            ),
        ),
        label=f"comic remote render asset selection {panel_id}",
    )
    _assert_selected_asset_contract(selected_asset)

    return queue_response, selected_asset, render_jobs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--character-id")
    parser.add_argument("--character-slug")
    parser.add_argument("--character-version-id")
    parser.add_argument("--story-prompt", default=DEFAULT_STORY_PROMPT)
    parser.add_argument("--story-lane", default=DEFAULT_STORY_LANE)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--panel-multiplier", type=int, default=1)
    parser.add_argument("--candidate-count", type=int, default=3)
    parser.add_argument(
        "--render-poll-attempts",
        type=int,
        default=DEFAULT_RENDER_POLL_ATTEMPTS,
    )
    parser.add_argument(
        "--render-poll-sec",
        type=float,
        default=DEFAULT_RENDER_POLL_SEC,
    )
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "base_url": args.base_url.rstrip("/"),
        "execution_mode": DEFAULT_EXECUTION_MODE,
        "import_success": False,
        "queue_renders_success": False,
        "overall_success": False,
        "selected_panel_asset_count": 0,
        "materialized_asset_count": 0,
        "real_selected_asset_materialized": False,
    }
    current_step = "bootstrap"

    try:
        if not comic_smoke._is_local_backend_url(args.base_url):
            raise RuntimeError(
                "Comic remote render smoke only supports local backend URLs"
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
            label="comic remote render story plan",
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
            label="comic remote render story import",
        )
        episode_id = comic_smoke._extract_episode_id(episode_detail)
        panel_id = comic_smoke._extract_first_panel_id(episode_detail)
        summary["import_success"] = True
        summary["episode_id"] = episode_id
        summary["panel_id"] = panel_id
        summary["panel_count"] = len(comic_smoke._extract_panel_ids(episode_detail))
        summary["scene_count"] = len(episode_detail.get("scenes") or [])

        current_step = "queue_renders"
        queue_response, selected_asset, render_jobs = _queue_and_select_remote_panel_asset(
            base_url=args.base_url,
            panel_id=panel_id,
            candidate_count=args.candidate_count,
            poll_attempts=args.render_poll_attempts,
            poll_sec=args.render_poll_sec,
        )
        render_assets = comic_smoke._require_list(
            queue_response.get("render_assets") or [],
            label=f"comic remote render assets {panel_id}",
        )
        summary["queue_renders_success"] = True
        summary["queued_generation_count"] = int(queue_response.get("queued_generation_count") or 0)
        summary["render_asset_count"] = len(render_assets)
        summary["remote_job_count"] = len(render_jobs)
        summary["pending_render_job_count"] = sum(
            1
            for job in render_jobs
            if str(job.get("status") or "").strip().lower()
            in {"queued", "submitted", "processing"}
        )
        summary["materialized_asset_count"] = sum(
            1 for job in render_jobs if str(job.get("output_path") or "").strip()
        )
        summary["selected_render_asset_is_selected"] = selected_asset.get("is_selected")
        summary["selected_render_asset_role"] = selected_asset.get("asset_role")
        summary["selected_render_asset_id"] = selected_asset.get("id")
        summary["selected_render_asset_storage_path"] = selected_asset.get("storage_path")
        summary["selected_panel_asset_count"] = int(
            selected_asset.get("is_selected") is True
            and str(selected_asset.get("asset_role") or "").strip().lower() == "selected"
        )
        summary["real_selected_asset_materialized"] = bool(
            summary["selected_panel_asset_count"]
            and str(selected_asset.get("storage_path") or "").strip()
        )
        if not summary["real_selected_asset_materialized"]:
            raise RuntimeError("Smoke did not materialize a real selected asset")

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
