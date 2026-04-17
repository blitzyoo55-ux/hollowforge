"""Launch a bounded Camila V2 comic pilot helper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import launch_comic_production_dry_run as comic_dry_run
from app.services.comic_render_service import select_best_render_asset_for_selection


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_STORY_PROMPT = (
    "In her artist loft on a quiet morning, Camila checks the studio lockbox by the window."
)
DEFAULT_STORY_LANE = "adult_nsfw"
DEFAULT_TITLE = "Camila V2 Comic Pilot"
DEFAULT_PANEL_MULTIPLIER = 1
DEFAULT_CANDIDATE_COUNT = 2
DEFAULT_EXECUTION_MODE = "remote_worker"
DEFAULT_RENDER_POLL_ATTEMPTS = 420
DEFAULT_RENDER_POLL_SEC = 1.0
DEFAULT_PANEL_LIMIT = 1
DEFAULT_LAYOUT_TEMPLATE_ID = comic_dry_run.DEFAULT_LAYOUT_TEMPLATE_ID
DEFAULT_MANUSCRIPT_PROFILE_ID = comic_dry_run.DEFAULT_MANUSCRIPT_PROFILE_ID

EXPECTED_CHARACTER_ID = "char_camila_duarte"
EXPECTED_CHARACTER_VERSION_ID = "charver_camila_duarte_still_v1"
DEFAULT_RENDER_LANE = "character_canon_v2"
DEFAULT_SERIES_STYLE_ID = "camila_pilot_v1"
DEFAULT_CHARACTER_SERIES_BINDING_ID = "camila_pilot_binding_v1"


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method.upper())
    with urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
    if not body.strip():
        return {}
    return json.loads(body)


def _build_url(base_url: str, path: str, params: dict[str, Any] | None = None) -> str:
    url = f"{base_url.rstrip('/')}{path}"
    if not params:
        return url
    encoded = urlencode(
        {key: value for key, value in params.items() if value is not None and value != ""}
    )
    return f"{url}?{encoded}" if encoded else url


def _require_object(payload: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object for {label}")
    return payload


def _require_list(payload: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeError(f"Expected JSON list for {label}")
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise RuntimeError(f"Expected JSON object rows for {label}")
        rows.append(item)
    return rows


def _print_marker(key: str, value: Any) -> None:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif value is None:
        rendered = ""
    else:
        rendered = str(value)
    print(f"{key}: {rendered}")


def _extract_episode_id(episode_detail: dict[str, Any]) -> str:
    episode = episode_detail.get("episode")
    if not isinstance(episode, dict):
        raise RuntimeError("Comic import response is missing episode detail")
    episode_id = str(episode.get("id") or "").strip()
    if not episode_id:
        raise RuntimeError("Comic import response did not include episode id")
    return episode_id


def _extract_panel_ids(episode_detail: dict[str, Any]) -> list[str]:
    scenes = episode_detail.get("scenes")
    if not isinstance(scenes, list):
        raise RuntimeError("Comic import response is missing scenes")
    panel_ids: list[str] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        panels = scene.get("panels")
        if not isinstance(panels, list):
            continue
        for panel in panels:
            if not isinstance(panel, dict):
                continue
            panel_id = str(panel.get("id") or "").strip()
            if panel_id:
                panel_ids.append(panel_id)
    if not panel_ids:
        raise RuntimeError("Comic import response did not include any panel ids")
    return panel_ids


def _validate_camila_ids(
    *,
    character_id: str,
    character_version_id: str,
    render_lane: str,
    series_style_id: str,
    character_series_binding_id: str,
) -> None:
    if character_id != EXPECTED_CHARACTER_ID:
        raise ValueError(
            f"Camila V2 pilot only supports character_id={EXPECTED_CHARACTER_ID}"
        )
    if character_version_id != EXPECTED_CHARACTER_VERSION_ID:
        raise ValueError(
            "Camila V2 pilot only supports "
            f"character_version_id={EXPECTED_CHARACTER_VERSION_ID}"
        )
    if render_lane != DEFAULT_RENDER_LANE:
        raise ValueError(
            f"Camila V2 pilot only supports render_lane={DEFAULT_RENDER_LANE}"
        )
    if not series_style_id.startswith("camila_"):
        raise ValueError("Camila V2 pilot requires a Camila series_style_id")
    if not character_series_binding_id.startswith("camila_"):
        raise ValueError("Camila V2 pilot requires a Camila character_series_binding_id")


def _pick_selectable_asset(
    render_assets: list[dict[str, Any]],
    *,
    panel_type: str | None,
) -> dict[str, Any]:
    selected = select_best_render_asset_for_selection(
        render_assets,
        panel_type=panel_type,
    )
    if selected is None:
        raise RuntimeError("Identity gate rejected all materialized candidates")
    asset_id = str(selected.get("id") or "").strip()
    if not asset_id:
        raise RuntimeError("Panel render candidate is missing id")
    return selected


def _poll_render_job_output_path(
    *,
    base_url: str,
    panel_id: str,
    generation_ids: set[str],
    poll_attempts: int,
    poll_sec: float,
) -> list[dict[str, Any]]:
    import time

    render_jobs_url = _build_url(
        base_url,
        f"/api/v1/comic/panels/{panel_id}/render-jobs",
    )
    for attempt in range(max(1, poll_attempts)):
        jobs = _require_list(
            _request_json("GET", render_jobs_url),
            label=f"comic panel render jobs {panel_id}",
        )
        relevant_jobs = [
            job
            for job in jobs
            if str(job.get("generation_id") or "").strip() in generation_ids
        ]
        if len(relevant_jobs) >= len(generation_ids):
            completed_paths = {
                str(job.get("generation_id") or "").strip(): str(job.get("output_path") or "").strip()
                for job in relevant_jobs
                if str(job.get("status") or "").strip() == "completed"
            }
            terminal_generation_ids = {
                str(job.get("generation_id") or "").strip()
                for job in relevant_jobs
                if str(job.get("status") or "").strip() in {"completed", "failed", "cancelled"}
            }
            if terminal_generation_ids >= generation_ids and all(
                completed_paths.get(generation_id) for generation_id in generation_ids
            ):
                return relevant_jobs
        if attempt < max(1, poll_attempts) - 1:
            time.sleep(max(0.1, poll_sec))

    raise RuntimeError(
        "Timed out waiting for panel render candidates to materialize "
        f"for panel {panel_id}"
    )


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

    layered_handoff_summary = comic_dry_run._extract_layered_handoff_summary(export_detail)
    comic_dry_run._validate_export_zip(export_zip_path, export_detail)
    report_path = comic_dry_run._write_report(
        episode_id=episode_id,
        layout_template_id=layout_template_id,
        manuscript_profile_id=manuscript_profile_id,
        episode_detail=episode_detail,
        assembly_detail=assembly_detail,
        export_detail=export_detail,
        selected_panel_assets=selected_panel_assets,
        layered_handoff_summary=layered_handoff_summary,
    )
    return {
        "dry_run_success": True,
        "layered_package_verified": True,
        "selected_panel_asset_count": len(selected_panel_assets),
        "page_count": len(export_detail.get("pages") or []),
        "export_zip_path": export_zip_path,
        "layered_manifest_path": layered_handoff_summary["layered_manifest_path"],
        "handoff_validation_path": layered_handoff_summary["handoff_validation_path"],
        "hard_block_count": layered_handoff_summary["hard_block_count"],
        "report_path": comic_dry_run._relative_data_path(report_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--story-prompt", default=DEFAULT_STORY_PROMPT)
    parser.add_argument("--story-lane", default=DEFAULT_STORY_LANE)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--panel-multiplier", type=int, default=DEFAULT_PANEL_MULTIPLIER)
    parser.add_argument("--candidate-count", type=int, default=DEFAULT_CANDIDATE_COUNT)
    parser.add_argument("--execution-mode", default=DEFAULT_EXECUTION_MODE)
    parser.add_argument("--render-poll-attempts", type=int, default=DEFAULT_RENDER_POLL_ATTEMPTS)
    parser.add_argument("--render-poll-sec", type=float, default=DEFAULT_RENDER_POLL_SEC)
    parser.add_argument("--panel-limit", type=int, default=DEFAULT_PANEL_LIMIT)
    parser.add_argument(
        "--run-production-dry-run",
        action="store_true",
        help="After candidate selection, draft dialogues and verify layered handoff export.",
    )
    parser.add_argument("--layout-template-id", default=DEFAULT_LAYOUT_TEMPLATE_ID)
    parser.add_argument(
        "--manuscript-profile-id",
        default=DEFAULT_MANUSCRIPT_PROFILE_ID,
    )
    parser.add_argument("--character-id", default=EXPECTED_CHARACTER_ID)
    parser.add_argument(
        "--character-version-id",
        default=EXPECTED_CHARACTER_VERSION_ID,
    )
    parser.add_argument("--render-lane", default=DEFAULT_RENDER_LANE)
    parser.add_argument("--series-style-id", default=DEFAULT_SERIES_STYLE_ID)
    parser.add_argument(
        "--character-series-binding-id",
        default=DEFAULT_CHARACTER_SERIES_BINDING_ID,
    )
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "episode_id": "",
        "series_style_id": str(args.series_style_id or "").strip(),
        "character_series_binding_id": str(args.character_series_binding_id or "").strip(),
        "candidate_count": int(args.candidate_count),
        "execution_mode": str(args.execution_mode or "").strip(),
        "panel_limit": int(args.panel_limit),
        "layout_template_id": str(args.layout_template_id or "").strip(),
        "manuscript_profile_id": str(args.manuscript_profile_id or "").strip(),
        "dialogues_success": False,
        "generated_dialogue_count": 0,
        "assemble_success": False,
        "export_success": False,
        "dry_run_success": False,
        "layered_package_verified": False,
        "layered_manifest_path": "",
        "handoff_validation_path": "",
        "hard_block_count": 0,
        "selected_panel_asset_count": 0,
        "page_count": 0,
        "export_zip_path": "",
        "dry_run_report_path": "",
        "selected_render_asset_id": "",
        "selected_render_generation_id": "",
        "selected_scene_panel_id": "",
        "selected_render_asset_storage_path": "",
        "queued_generation_count": 0,
        "overall_success": False,
        "failed_step": "bootstrap",
    }
    current_step = "bootstrap"

    try:
        current_step = "validate_camila_ids"
        _validate_camila_ids(
            character_id=str(args.character_id or "").strip(),
            character_version_id=str(args.character_version_id or "").strip(),
            render_lane=str(args.render_lane or "").strip(),
            series_style_id=str(args.series_style_id or "").strip(),
            character_series_binding_id=str(args.character_series_binding_id or "").strip(),
        )

        current_step = "plan_story"
        approved_plan = _require_object(
            _request_json(
                "POST",
                _build_url(args.base_url, "/api/v1/tools/story-planner/plan"),
                {
                    "story_prompt": args.story_prompt,
                    "lane": args.story_lane,
                },
            ),
            label="story planner plan",
        )

        current_step = "import_story_plan"
        episode_detail = _require_object(
            _request_json(
                "POST",
                _build_url(args.base_url, "/api/v1/comic/episodes/import-story-plan"),
                {
                    "approved_plan": approved_plan,
                    "character_version_id": args.character_version_id,
                    "title": args.title,
                    "panel_multiplier": args.panel_multiplier,
                    "render_lane": args.render_lane,
                    "series_style_id": args.series_style_id,
                    "character_series_binding_id": args.character_series_binding_id,
                },
            ),
            label="comic story import",
        )
        episode_id = _extract_episode_id(episode_detail)
        panel_ids = _extract_panel_ids(episode_detail)
        summary["episode_id"] = episode_id

        current_step = "queue_and_select_renders"
        total_queued = 0
        first_storage_path = ""
        first_selected_asset_id = ""
        first_generation_id = ""
        first_panel_id = ""
        panel_ids = panel_ids[: max(1, int(args.panel_limit or 1))]
        for index, panel_id in enumerate(panel_ids):
            queue_response = _require_object(
                _request_json(
                    "POST",
                    _build_url(
                        args.base_url,
                        f"/api/v1/comic/panels/{panel_id}/queue-renders",
                        {
                            "candidate_count": args.candidate_count,
                            "execution_mode": args.execution_mode,
                        },
                    ),
                ),
                label=f"comic panel render queue {panel_id}",
            )
            total_queued += int(queue_response.get("queued_generation_count") or 0)
            render_assets = _require_list(
                queue_response.get("render_assets") or [],
                label=f"comic panel render assets {panel_id}",
            )
            panel_type = str(
                _require_object(queue_response.get("panel") or {}, label=f"comic panel detail {panel_id}").get("panel_type")
                or ""
            ).strip()
            if args.execution_mode == "remote_worker":
                generation_ids = {
                    str(asset.get("generation_id") or "").strip()
                    for asset in render_assets
                    if str(asset.get("generation_id") or "").strip()
                }
                effective_poll_attempts = max(
                    int(args.render_poll_attempts or 0),
                    int(args.render_poll_attempts or 0) * max(1, len(generation_ids)),
                )
                _poll_render_job_output_path(
                    base_url=args.base_url,
                    panel_id=panel_id,
                    generation_ids=generation_ids,
                    poll_attempts=effective_poll_attempts,
                    poll_sec=args.render_poll_sec,
                )
                queue_response = _require_object(
                    _request_json(
                        "POST",
                        _build_url(
                            args.base_url,
                            f"/api/v1/comic/panels/{panel_id}/queue-renders",
                            {
                                "candidate_count": args.candidate_count,
                                "execution_mode": args.execution_mode,
                            },
                        ),
                    ),
                    label=f"comic panel render queue refresh {panel_id}",
                )
                render_assets = _require_list(
                    queue_response.get("render_assets") or [],
                    label=f"comic panel render assets refresh {panel_id}",
                )
            selected_candidate = _pick_selectable_asset(
                render_assets,
                panel_type=panel_type,
            )
            selected_asset = _require_object(
                _request_json(
                    "POST",
                    _build_url(
                        args.base_url,
                        f"/api/v1/comic/panels/{panel_id}/assets/{selected_candidate['id']}/select",
                    ),
                ),
                label=f"comic panel asset selection {panel_id}",
            )
            selected_asset_id = str(selected_asset.get("id") or "").strip()
            selected_generation_id = str(selected_asset.get("generation_id") or "").strip()
            selected_storage_path = str(selected_asset.get("storage_path") or "").strip()
            if index == 0:
                first_storage_path = selected_storage_path
                first_selected_asset_id = selected_asset_id
                first_generation_id = selected_generation_id
                first_panel_id = str(selected_asset.get("scene_panel_id") or panel_id).strip()

        summary["queued_generation_count"] = total_queued
        summary["selected_render_asset_id"] = first_selected_asset_id
        summary["selected_render_generation_id"] = first_generation_id
        summary["selected_scene_panel_id"] = first_panel_id
        summary["selected_render_asset_storage_path"] = first_storage_path

        if args.run_production_dry_run:
            current_step = "draft_dialogues"
            generated_dialogue_count = 0
            for panel_id in panel_ids:
                dialogue_response = _require_object(
                    _request_json(
                        "POST",
                        _build_url(
                            args.base_url,
                            f"/api/v1/comic/panels/{panel_id}/dialogues/generate",
                        ),
                    ),
                    label=f"comic dialogue generation {panel_id}",
                )
                generated_dialogue_count += int(
                    dialogue_response.get("generated_count") or 0
                )
            summary["dialogues_success"] = True
            summary["generated_dialogue_count"] = generated_dialogue_count

            current_step = "production_dry_run"
            dry_run_summary = _run_production_dry_run(
                base_url=args.base_url,
                episode_id=episode_id,
                layout_template_id=str(args.layout_template_id or "").strip(),
                manuscript_profile_id=str(args.manuscript_profile_id or "").strip(),
            )
            summary["assemble_success"] = True
            summary["export_success"] = True
            summary["dry_run_success"] = bool(dry_run_summary.get("dry_run_success"))
            summary["layered_package_verified"] = bool(
                dry_run_summary.get("layered_package_verified")
            )
            summary["selected_panel_asset_count"] = int(
                dry_run_summary.get("selected_panel_asset_count") or 0
            )
            summary["page_count"] = int(dry_run_summary.get("page_count") or 0)
            summary["export_zip_path"] = str(
                dry_run_summary.get("export_zip_path") or ""
            ).strip()
            summary["layered_manifest_path"] = str(
                dry_run_summary.get("layered_manifest_path") or ""
            ).strip()
            summary["handoff_validation_path"] = str(
                dry_run_summary.get("handoff_validation_path") or ""
            ).strip()
            summary["hard_block_count"] = int(
                dry_run_summary.get("hard_block_count") or 0
            )
            summary["dry_run_report_path"] = str(
                dry_run_summary.get("report_path") or ""
            ).strip()

        summary["overall_success"] = True
        summary["failed_step"] = ""
        return 0
    except (HTTPError, URLError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        summary["failed_step"] = current_step
        return 1
    finally:
        for key, value in summary.items():
            _print_marker(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
