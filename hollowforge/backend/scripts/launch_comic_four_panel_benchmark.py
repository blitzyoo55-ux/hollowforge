"""Run a four-panel comic verification benchmark and recommend the execution boundary."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
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
from app.config import settings

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TITLE = "Comic Four Panel Local Benchmark"
DEFAULT_STORY_PROMPT = (
    "{character_name} moves through a short four-beat manga page sequence so the "
    "local workstation throughput can be measured end to end."
)
DEFAULT_STORY_LANE = "adult_nsfw"
DEFAULT_LAYOUT_TEMPLATE_ID = "jp_2x2_v1"
DEFAULT_MANUSCRIPT_PROFILE_ID = "jp_manga_rightbound_v1"
DEFAULT_PANEL_MULTIPLIER = 1
DEFAULT_CANDIDATE_COUNT = 1
DEFAULT_EXECUTION_MODE = remote_smoke.DEFAULT_EXECUTION_MODE
DEFAULT_RENDER_POLL_ATTEMPTS = 360
DEFAULT_MAX_TOTAL_DURATION_SEC = 900.0
DEFAULT_MAX_PANEL_RENDER_DURATION_SEC = 180.0
DEFAULT_MAX_AVERAGE_PANEL_RENDER_DURATION_SEC = 120.0


class BenchmarkExecutionError(RuntimeError):
    def __init__(self, summary: dict[str, Any]) -> None:
        super().__init__(str(summary.get("error") or "Comic benchmark failed"))
        self.summary = summary


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_monotonic() -> float:
    return time.perf_counter()


def _round_duration(value: float) -> float:
    return round(max(0.0, value), 3)


def _relative_data_path(path: Path) -> str:
    return str(path.resolve().relative_to(settings.DATA_DIR.resolve())).replace(
        "\\",
        "/",
    )


def _measure_call(fn, *args, **kwargs):  # type: ignore[no-untyped-def]
    started = _now_monotonic()
    result = fn(*args, **kwargs)
    return result, _round_duration(_now_monotonic() - started)


def _average_panel_render_duration(panel_render_benchmarks: list[dict[str, Any]]) -> float:
    durations = [
        float(item["render_duration_sec"])
        for item in panel_render_benchmarks
        if isinstance(item, dict) and item.get("render_duration_sec") is not None
    ]
    if not durations:
        return 0.0
    return round(sum(durations) / len(durations), 3)


def _recommend_execution_boundary(
    summary: dict[str, Any],
    *,
    max_total_duration_sec: float,
    max_panel_render_duration_sec: float,
    max_average_panel_render_duration_sec: float,
) -> dict[str, Any]:
    panel_render_benchmarks = summary.get("panel_render_benchmarks") or []
    panel_durations = [
        float(item["render_duration_sec"])
        for item in panel_render_benchmarks
        if isinstance(item, dict) and item.get("render_duration_sec") is not None
    ]
    average_panel_render_duration_sec = (
        round(sum(panel_durations) / len(panel_durations), 3) if panel_durations else 0.0
    )
    max_observed_panel_render_duration_sec = (
        round(max(panel_durations), 3) if panel_durations else 0.0
    )
    total_duration_sec = round(float(summary.get("total_duration_sec") or 0.0), 3)
    reasons: list[str] = []

    if not summary.get("overall_success"):
        failed_step = str(summary.get("failed_step") or "unknown")
        if failed_step == "queue_renders_budget_exceeded":
            panel_id = str(summary.get("render_budget_exceeded_panel_id") or "").strip()
            threshold_sec = round(
                float(
                    summary.get("render_budget_exceeded_threshold_sec")
                    or max_panel_render_duration_sec
                ),
                3,
            )
            observed_sec = round(
                float(
                    summary.get("render_budget_exceeded_value_sec")
                    or max_observed_panel_render_duration_sec
                ),
                3,
            )
            panel_label = f"panel {panel_id} " if panel_id else ""
            reasons.append(
                f"{panel_label}render duration {observed_sec:.3f}s exceeded fail-fast budget "
                f"{threshold_sec:.3f}s"
            )
            mode = "remote_worker_recommended"
        elif failed_step == "queue_renders":
            reasons.append(
                "local render queue did not complete cleanly during the benchmark"
            )
            mode = "remote_worker_recommended"
        else:
            reasons.append(f"benchmark failed before completion at step '{failed_step}'")
            mode = "retry_local"
    else:
        if total_duration_sec > max_total_duration_sec:
            reasons.append(
                f"total duration {total_duration_sec:.3f}s exceeded budget {max_total_duration_sec:.3f}s"
            )
        if average_panel_render_duration_sec > max_average_panel_render_duration_sec:
            reasons.append(
                "average panel render duration "
                f"{average_panel_render_duration_sec:.3f}s exceeded budget "
                f"{max_average_panel_render_duration_sec:.3f}s"
            )
        if max_observed_panel_render_duration_sec > max_panel_render_duration_sec:
            reasons.append(
                "slowest panel render duration "
                f"{max_observed_panel_render_duration_sec:.3f}s exceeded budget "
                f"{max_panel_render_duration_sec:.3f}s"
            )
        mode = "remote_worker_recommended" if reasons else "stay_local"

    return {
        "mode": mode,
        "reasons": reasons,
        "total_duration_sec": total_duration_sec,
        "average_panel_render_duration_sec": average_panel_render_duration_sec,
        "max_observed_panel_render_duration_sec": max_observed_panel_render_duration_sec,
        "thresholds": {
            "max_total_duration_sec": round(max_total_duration_sec, 3),
            "max_panel_render_duration_sec": round(max_panel_render_duration_sec, 3),
            "max_average_panel_render_duration_sec": round(
                max_average_panel_render_duration_sec, 3
            ),
        },
    }


def _report_path_for(summary: dict[str, Any]) -> Path:
    episode_id = str(summary.get("episode_id") or "").strip()
    layout_template_id = str(summary.get("layout_template_id") or DEFAULT_LAYOUT_TEMPLATE_ID)
    manuscript_profile_id = str(
        summary.get("manuscript_profile_id") or DEFAULT_MANUSCRIPT_PROFILE_ID
    )
    if episode_id:
        filename = f"{episode_id}_{layout_template_id}_{manuscript_profile_id}_local_benchmark.json"
    else:
        filename = (
            "comic_four_panel_local_benchmark_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
    return settings.COMICS_REPORTS_DIR / filename


def _write_benchmark_report(
    summary: dict[str, Any],
    *,
    recommendation: dict[str, Any],
) -> Path:
    report_path = _report_path_for(summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "benchmark_kind": "comic_four_panel_local_benchmark",
        "created_at": _now_iso(),
        **summary,
        "recommendation": recommendation,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


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
        "panel_count": len(comic_dry_run._extract_panel_ids(episode_detail)),
        "selected_panel_asset_count": len(selected_panel_assets),
        "page_count": len(export_detail.get("pages") or []),
        "export_zip_path": export_zip_path,
        "layered_manifest_path": layered_handoff_summary["layered_manifest_path"],
        "handoff_validation_path": layered_handoff_summary["handoff_validation_path"],
        "hard_block_count": layered_handoff_summary["hard_block_count"],
        "report_path": comic_dry_run._relative_data_path(report_path),
    }


def _run_benchmark_flow(
    *,
    base_url: str,
    character_id: str | None,
    character_slug: str | None,
    character_version_id: str | None,
    story_prompt: str,
    story_lane: str,
    title: str,
    candidate_count: int,
    execution_mode: str = "local_preview",
    fail_fast_on_budget_exceed: bool = False,
    render_poll_attempts: int,
    render_poll_sec: float,
    layout_template_id: str,
    manuscript_profile_id: str,
    max_panel_render_duration_sec: float,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "base_url": base_url.rstrip("/"),
        "execution_mode": str(execution_mode or "").strip(),
        "layout_template_id": layout_template_id,
        "manuscript_profile_id": manuscript_profile_id,
        "story_lane": story_lane,
        "episode_create_success": False,
        "queue_renders_success": False,
        "dialogues_success": False,
        "assemble_success": False,
        "export_success": False,
        "dry_run_success": False,
        "overall_success": False,
        "layered_package_verified": False,
        "layered_manifest_path": "",
        "handoff_validation_path": "",
        "hard_block_count": 0,
        "materialized_asset_count": 0,
        "panel_render_benchmarks": [],
    }
    current_step = "bootstrap"
    total_started = _now_monotonic()

    try:
        if not comic_smoke._is_local_backend_url(base_url):
            raise RuntimeError(
                "Comic four-panel benchmark only supports local backend URLs"
            )

        current_step = "resolve_character_context"
        character, version, characters, versions = comic_smoke._resolve_character_and_version(
            base_url=base_url,
            character_version_id=character_version_id,
            character_id=character_id,
            character_slug=character_slug,
        )
        summary["character_count"] = len(characters)
        summary["character_version_count"] = len(versions)
        summary["character_id"] = character.get("id")
        summary["character_slug"] = character.get("slug")
        summary["character_version_id"] = version.get("id")

        rendered_story_prompt = comic_smoke._render_story_prompt(
            story_prompt,
            character_name=str(character.get("name") or "Lead"),
            character_slug=str(character.get("slug") or ""),
        )
        summary["story_prompt"] = rendered_story_prompt

        current_step = "plan_story"
        approved_plan, duration_sec = _measure_call(
            comic_smoke._request_json,
            "POST",
            comic_smoke._build_url(base_url, "/api/v1/tools/story-planner/plan"),
            {
                "story_prompt": rendered_story_prompt,
                "lane": story_lane,
            },
        )
        approved_plan = comic_smoke._require_object(
            approved_plan,
            label="story planner plan",
        )
        summary["plan_story_duration_sec"] = duration_sec
        summary["approval_token"] = approved_plan.get("approval_token")

        current_step = "import_story_plan"
        episode_detail, duration_sec = _measure_call(
            comic_smoke._request_json,
            "POST",
            comic_smoke._build_url(base_url, "/api/v1/comic/episodes/import-story-plan"),
            {
                "approved_plan": approved_plan,
                "character_version_id": version["id"],
                "title": title,
                "panel_multiplier": DEFAULT_PANEL_MULTIPLIER,
            },
        )
        episode_detail = comic_smoke._require_object(
            episode_detail,
            label="comic story import",
        )
        summary["import_story_plan_duration_sec"] = duration_sec
        episode_id = comic_smoke._extract_episode_id(episode_detail)
        panel_ids = comic_smoke._extract_panel_ids(episode_detail)
        if len(panel_ids) != 4:
            raise RuntimeError(
                f"Comic four-panel benchmark requires exactly 4 panels, got {len(panel_ids)}"
            )
        summary["episode_id"] = episode_id
        summary["panel_count"] = len(panel_ids)
        summary["scene_count"] = len(episode_detail.get("scenes") or [])
        summary["episode_create_success"] = True

        current_step = "queue_renders"
        queued_generation_count = 0
        render_asset_count = 0
        selected_panel_asset_count = 0
        materialized_asset_count = 0
        remote_job_count = 0
        panel_render_benchmarks: list[dict[str, Any]] = []
        for panel_id in panel_ids:
            if execution_mode == DEFAULT_EXECUTION_MODE:
                (
                    result,
                    render_duration_sec,
                ) = _measure_call(
                    remote_smoke._queue_and_select_remote_panel_asset,
                    base_url=base_url,
                    panel_id=panel_id,
                    candidate_count=candidate_count,
                    poll_attempts=render_poll_attempts,
                    poll_sec=render_poll_sec,
                )
                queue_response, selected_asset, render_jobs = result
                remote_job_count += len(render_jobs)
                materialized_asset_count += sum(
                    1 for job in render_jobs if str(job.get("output_path") or "").strip()
                )
            else:
                (
                    result,
                    render_duration_sec,
                ) = _measure_call(
                    comic_smoke._queue_and_select_panel_asset,
                    base_url=base_url,
                    panel_id=panel_id,
                    candidate_count=candidate_count,
                    poll_attempts=render_poll_attempts,
                    poll_sec=render_poll_sec,
                    allow_synthetic_asset_fallback=False,
                )
                queue_response, selected_asset, _ = result
                materialized_asset_count += 1
            render_assets = comic_smoke._require_list(
                queue_response.get("render_assets") or [],
                label=f"comic panel render assets {panel_id}",
            )
            queued_generation_count += int(queue_response.get("queued_generation_count") or 0)
            render_asset_count += len(render_assets)
            selected_panel_asset_count += 1
            panel_render_benchmarks.append(
                {
                    "panel_id": panel_id,
                    "render_duration_sec": render_duration_sec,
                    "queued_generation_count": int(
                        queue_response.get("queued_generation_count") or 0
                    ),
                    "render_asset_count": len(render_assets),
                    "selected_render_asset_id": selected_asset.get("id"),
                }
            )
            summary["panel_render_benchmarks"] = panel_render_benchmarks
            summary["queued_generation_count"] = queued_generation_count
            summary["render_asset_count"] = render_asset_count
            summary["selected_panel_asset_count"] = selected_panel_asset_count
            summary["materialized_asset_count"] = materialized_asset_count
            summary["remote_job_count"] = remote_job_count
            summary["average_panel_render_duration_sec"] = _average_panel_render_duration(
                panel_render_benchmarks
            )
            if render_duration_sec > max_panel_render_duration_sec:
                if not str(summary.get("render_budget_exceeded_panel_id") or "").strip():
                    summary["render_budget_exceeded_panel_id"] = panel_id
                    summary["render_budget_exceeded_threshold_sec"] = round(
                        max_panel_render_duration_sec,
                        3,
                    )
                    summary["render_budget_exceeded_value_sec"] = render_duration_sec
                if fail_fast_on_budget_exceed:
                    current_step = "queue_renders_budget_exceeded"
                    raise RuntimeError(
                        f"Panel {panel_id} render duration {render_duration_sec:.3f}s "
                        f"exceeded fail-fast budget {max_panel_render_duration_sec:.3f}s"
                    )

        summary["panel_render_benchmarks"] = panel_render_benchmarks
        summary["queue_renders_success"] = True
        summary["queued_generation_count"] = queued_generation_count
        summary["render_asset_count"] = render_asset_count
        summary["selected_panel_asset_count"] = selected_panel_asset_count
        summary["materialized_asset_count"] = materialized_asset_count
        summary["remote_job_count"] = remote_job_count
        summary["average_panel_render_duration_sec"] = _average_panel_render_duration(
            panel_render_benchmarks
        )

        current_step = "draft_dialogues"
        dialogue_started = _now_monotonic()
        generated_dialogue_count = 0
        dialogue_benchmarks: list[dict[str, Any]] = []
        for panel_id in panel_ids:
            dialogue_response = comic_smoke._require_object(
                comic_smoke._request_json(
                    "POST",
                    comic_smoke._build_url(
                        base_url,
                        f"/api/v1/comic/panels/{panel_id}/dialogues/generate",
                    ),
                ),
                label=f"comic dialogue generation {panel_id}",
            )
            generated_count = int(dialogue_response.get("generated_count") or 0)
            generated_dialogue_count += generated_count
            dialogue_benchmarks.append(
                {
                    "panel_id": panel_id,
                    "generated_dialogue_count": generated_count,
                }
            )
        summary["dialogues_duration_sec"] = _round_duration(
            _now_monotonic() - dialogue_started
        )
        summary["generated_dialogue_count"] = generated_dialogue_count
        summary["dialogue_benchmarks"] = dialogue_benchmarks
        summary["dialogues_success"] = True

        current_step = "assemble_pages"
        assembly_response, duration_sec = _measure_call(
            comic_smoke._request_json,
            "POST",
            comic_smoke._build_url(
                base_url,
                f"/api/v1/comic/episodes/{episode_id}/pages/assemble",
                {
                    "layout_template_id": layout_template_id,
                    "manuscript_profile_id": manuscript_profile_id,
                },
            ),
        )
        assembly_response = comic_smoke._require_object(
            assembly_response,
            label="comic benchmark assembly",
        )
        summary["assemble_pages_duration_sec"] = duration_sec
        summary["assemble_success"] = True
        summary["page_count"] = len(assembly_response.get("pages") or [])

        current_step = "export_pages"
        export_response, duration_sec = _measure_call(
            comic_smoke._request_json,
            "POST",
            comic_smoke._build_url(
                base_url,
                f"/api/v1/comic/episodes/{episode_id}/pages/export",
                {
                    "layout_template_id": layout_template_id,
                    "manuscript_profile_id": manuscript_profile_id,
                },
            ),
        )
        export_response = comic_smoke._require_object(
            export_response,
            label="comic benchmark export",
        )
        summary["export_pages_duration_sec"] = duration_sec
        summary["export_success"] = True
        summary["export_zip_path"] = export_response.get("export_zip_path")

        current_step = "production_dry_run"
        dry_run_summary, duration_sec = _measure_call(
            _run_production_dry_run,
            base_url=base_url,
            episode_id=episode_id,
            layout_template_id=layout_template_id,
            manuscript_profile_id=manuscript_profile_id,
        )
        summary["production_dry_run_duration_sec"] = duration_sec
        summary["dry_run_success"] = bool(dry_run_summary.get("dry_run_success"))
        summary["layered_package_verified"] = bool(
            dry_run_summary.get("layered_package_verified")
        )
        summary["page_count"] = int(dry_run_summary.get("page_count") or summary["page_count"])
        summary["selected_panel_asset_count"] = int(
            dry_run_summary.get("selected_panel_asset_count")
            or summary["selected_panel_asset_count"]
        )
        summary["export_zip_path"] = (
            dry_run_summary.get("export_zip_path") or summary.get("export_zip_path")
        )
        summary["layered_manifest_path"] = (
            dry_run_summary.get("layered_manifest_path") or ""
        )
        summary["handoff_validation_path"] = (
            dry_run_summary.get("handoff_validation_path") or ""
        )
        summary["hard_block_count"] = int(dry_run_summary.get("hard_block_count") or 0)
        summary["dry_run_report_path"] = dry_run_summary.get("report_path") or dry_run_summary.get(
            "dry_run_report_path"
        )

        summary["total_duration_sec"] = _round_duration(_now_monotonic() - total_started)
        summary["overall_success"] = True
        return summary
    except Exception as exc:
        summary["total_duration_sec"] = _round_duration(_now_monotonic() - total_started)
        summary["error"] = str(exc)
        summary["failed_step"] = current_step
        raise BenchmarkExecutionError(summary) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--character-id")
    parser.add_argument("--character-slug")
    parser.add_argument("--character-version-id")
    parser.add_argument("--story-prompt", default=DEFAULT_STORY_PROMPT)
    parser.add_argument("--story-lane", default=DEFAULT_STORY_LANE)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--candidate-count", type=int, default=DEFAULT_CANDIDATE_COUNT)
    parser.add_argument(
        "--execution-mode",
        default=DEFAULT_EXECUTION_MODE,
        choices=("local_preview", "remote_worker"),
    )
    parser.add_argument(
        "--fail-fast-on-budget-exceed",
        action="store_true",
    )
    parser.add_argument(
        "--render-poll-attempts",
        type=int,
        default=DEFAULT_RENDER_POLL_ATTEMPTS,
    )
    parser.add_argument("--render-poll-sec", type=float, default=1.0)
    parser.add_argument("--layout-template-id", default=DEFAULT_LAYOUT_TEMPLATE_ID)
    parser.add_argument(
        "--manuscript-profile-id",
        default=DEFAULT_MANUSCRIPT_PROFILE_ID,
    )
    parser.add_argument(
        "--max-total-duration-sec",
        type=float,
        default=DEFAULT_MAX_TOTAL_DURATION_SEC,
    )
    parser.add_argument(
        "--max-panel-render-duration-sec",
        type=float,
        default=DEFAULT_MAX_PANEL_RENDER_DURATION_SEC,
    )
    parser.add_argument(
        "--max-average-panel-render-duration-sec",
        type=float,
        default=DEFAULT_MAX_AVERAGE_PANEL_RENDER_DURATION_SEC,
    )
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "base_url": args.base_url.rstrip("/"),
        "layout_template_id": args.layout_template_id,
        "manuscript_profile_id": args.manuscript_profile_id,
        "overall_success": False,
    }
    exit_code = 0

    try:
        summary = _run_benchmark_flow(
            base_url=args.base_url,
            character_id=args.character_id,
            character_slug=args.character_slug,
            character_version_id=args.character_version_id,
            story_prompt=args.story_prompt,
            story_lane=args.story_lane,
            title=args.title,
            candidate_count=args.candidate_count,
            execution_mode=args.execution_mode,
            fail_fast_on_budget_exceed=args.fail_fast_on_budget_exceed,
            render_poll_attempts=args.render_poll_attempts,
            render_poll_sec=args.render_poll_sec,
            layout_template_id=args.layout_template_id,
            manuscript_profile_id=args.manuscript_profile_id,
            max_panel_render_duration_sec=args.max_panel_render_duration_sec,
        )
    except BenchmarkExecutionError as exc:
        summary = exc.summary
        exit_code = 1

    recommendation = _recommend_execution_boundary(
        summary,
        max_total_duration_sec=args.max_total_duration_sec,
        max_panel_render_duration_sec=args.max_panel_render_duration_sec,
        max_average_panel_render_duration_sec=args.max_average_panel_render_duration_sec,
    )
    summary["recommendation_mode"] = recommendation["mode"]
    summary["recommendation_reasons"] = recommendation["reasons"]
    report_path = _write_benchmark_report(
        summary,
        recommendation=recommendation,
    )
    summary["benchmark_report_path"] = _relative_data_path(report_path)

    for key, value in summary.items():
        comic_smoke._print_marker(key, value)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
