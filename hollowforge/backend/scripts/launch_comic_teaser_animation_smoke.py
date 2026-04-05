"""Launch a guarded HollowForge comic teaser animation smoke helper."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from collections.abc import Mapping
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
import launch_animation_preset_smoke as animation_smoke


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PRESET_ID = "sdxl_ipadapter_microanim_v2"
PLACEHOLDER_ASSET_PREFIX = "comics/previews/smoke_assets/"


def _is_placeholder_asset(storage_path: str) -> bool:
    normalized = storage_path.strip().replace("\\", "/")
    return normalized.startswith(PLACEHOLDER_ASSET_PREFIX) or (
        f"/{PLACEHOLDER_ASSET_PREFIX}" in normalized
    )


def _print_summary(summary: dict[str, Any]) -> None:
    for key, value in summary.items():
        comic_smoke._print_marker(key, value)


def _find_latest_successful_dry_run_report() -> tuple[Path, str]:
    reports_dir = comic_dry_run.settings.DATA_DIR / "comics" / "reports"
    latest_report: tuple[float, Path, str] | None = None
    for report_path in reports_dir.glob("*_dry_run.json"):
        if not report_path.is_file():
            continue
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        episode_id = str(payload.get("episode_id") or "").strip()
        export_zip_path = str(payload.get("export_zip_path") or "").strip()
        if not episode_id or not export_zip_path:
            continue
        candidate = (report_path.stat().st_mtime, report_path, episode_id)
        if latest_report is None or candidate[:2] > latest_report[:2]:
            latest_report = candidate
    if latest_report is None:
        raise RuntimeError("No successful comic dry-run report found under data/comics/reports")
    return latest_report[1], latest_report[2]


def _resolve_episode_id(episode_id: str | None) -> str:
    explicit_episode_id = str(episode_id or "").strip()
    if explicit_episode_id:
        return explicit_episode_id
    _, resolved_episode_id = _find_latest_successful_dry_run_report()
    return resolved_episode_id


def _resolve_source_asset(
    *,
    base_url: str,
    episode_id: str | None,
    panel_index: int,
    **_: Any,
) -> dict[str, Any]:
    resolved_episode_id = _resolve_episode_id(episode_id)
    _, assembly_detail, _ = comic_dry_run._ensure_exported_episode(
        base_url=base_url,
        episode_id=resolved_episode_id,
        layout_template_id=comic_dry_run.DEFAULT_LAYOUT_TEMPLATE_ID,
        manuscript_profile_id=comic_dry_run.DEFAULT_MANUSCRIPT_PROFILE_ID,
    )
    selected_panel_assets = comic_dry_run._extract_selected_panel_assets(assembly_detail)
    if not selected_panel_assets:
        raise RuntimeError("Comic teaser handoff did not include any selected panel assets")
    if panel_index < 0 or panel_index >= len(selected_panel_assets):
        raise RuntimeError(
            f"panel_index {panel_index} is out of range for {len(selected_panel_assets)} selected panel assets"
        )

    selected_asset = dict(selected_panel_assets[panel_index])
    return {
        "episode_id": resolved_episode_id,
        "scene_panel_id": str(
            selected_asset.get("scene_panel_id") or selected_asset.get("panel_id") or ""
        ).strip(),
        "selected_render_asset_id": _extract_selected_asset_id(selected_asset)
        or str(selected_asset.get("asset_id") or "").strip(),
        "generation_id": str(selected_asset.get("generation_id") or "").strip(),
        "storage_path": str(selected_asset.get("storage_path") or "").strip(),
    }


def _extract_selected_asset_id(source_asset: dict[str, Any]) -> str:
    return str(
        source_asset.get("selected_render_asset_id") or source_asset.get("id") or ""
    ).strip()


def _validate_source_asset(source_asset: dict[str, Any]) -> None:
    selected_asset_id = _extract_selected_asset_id(source_asset)
    if not selected_asset_id:
        raise RuntimeError("selected asset id is missing")

    generation_id = str(source_asset.get("generation_id") or "").strip()
    if not generation_id:
        raise RuntimeError("selected asset generation_id is missing")

    storage_path = str(source_asset.get("storage_path") or "").strip()
    if not storage_path:
        raise RuntimeError("selected asset storage_path is missing")
    if _is_placeholder_asset(storage_path):
        raise RuntimeError("placeholder selected asset is not allowed")


def _require_source_asset_mapping(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise RuntimeError("source asset resolution must return a mapping")
    return dict(payload)


def _extract_preset_id_from_argv(argv: list[str]) -> str:
    preset_parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    preset_parser.add_argument("--preset-id", default=DEFAULT_PRESET_ID)
    try:
        namespace, _ = preset_parser.parse_known_args(argv)
    except (argparse.ArgumentError, SystemExit):
        return DEFAULT_PRESET_ID

    preset_id = str(namespace.preset_id or "").strip()
    return preset_id or DEFAULT_PRESET_ID


def _build_summary(*, preset_id: str) -> dict[str, Any]:
    return {
        "episode_id": "",
        "scene_panel_id": "",
        "selected_render_asset_id": "",
        "generation_id": "",
        "preset_id": preset_id,
        "animation_job_id": "",
        "output_path": "",
        "teaser_success": False,
        "overall_success": False,
        "failed_step": "bootstrap",
    }


def _validate_output_path(output_path: str) -> Path:
    normalized_output_path = str(output_path or "").strip()
    if not normalized_output_path:
        raise RuntimeError("animation output_path is missing")
    if not normalized_output_path.lower().endswith(".mp4"):
        raise RuntimeError("animation output_path must point to an .mp4 file")

    output_file = Path(normalized_output_path)
    if not output_file.is_absolute():
        output_file = comic_dry_run.settings.DATA_DIR / output_file
    if not output_file.is_file():
        raise RuntimeError(f"animation output file not found: {output_file}")
    return output_file


def main() -> int:
    argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--episode-id")
    parser.add_argument("--panel-index", type=int, default=0)
    parser.add_argument("--preset-id", default=DEFAULT_PRESET_ID)
    parser.add_argument("--poll-sec", type=float, default=1.0)
    parser.add_argument("--timeout-sec", type=float, default=1800.0)
    summary = _build_summary(preset_id=_extract_preset_id_from_argv(argv))
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if exc.code == 0:
            return 0
        _print_summary(summary)
        return 1

    summary = _build_summary(preset_id=args.preset_id)

    try:
        if not comic_smoke._is_local_backend_url(args.base_url):
            raise RuntimeError("comic teaser animation smoke only supports local backend URLs")

        summary["failed_step"] = "resolve_source_asset"
        source_asset = _resolve_source_asset(
            base_url=args.base_url,
            episode_id=args.episode_id,
            panel_index=args.panel_index,
            preset_id=args.preset_id,
            poll_sec=args.poll_sec,
            timeout_sec=args.timeout_sec,
        )
        source_asset = _require_source_asset_mapping(source_asset)

        summary["episode_id"] = str(source_asset.get("episode_id") or args.episode_id or "")
        summary["scene_panel_id"] = str(source_asset.get("scene_panel_id") or "")
        summary["selected_render_asset_id"] = _extract_selected_asset_id(source_asset)
        summary["generation_id"] = str(source_asset.get("generation_id") or "")

        summary["failed_step"] = "validate_source_asset"
        _validate_source_asset(source_asset)
        summary["failed_step"] = "launch"
        with contextlib.redirect_stdout(io.StringIO()):
            animation_job_id = animation_smoke._launch_job(
                base_url=args.base_url,
                preset_id=args.preset_id,
                generation_id=summary["generation_id"],
                request_overrides={},
                dispatch_immediately=True,
            )
        summary["animation_job_id"] = animation_job_id

        summary["failed_step"] = "poll"
        with contextlib.redirect_stdout(io.StringIO()):
            final_job = animation_smoke._poll_job(
                base_url=args.base_url,
                job_id=animation_job_id,
                poll_sec=args.poll_sec,
                timeout_sec=args.timeout_sec,
            )

        final_job_status = str(final_job.get("status") or "").strip()
        if final_job_status != "completed":
            raise RuntimeError(f"animation job did not complete successfully: {final_job_status}")

        summary["output_path"] = str(final_job.get("output_path") or "").strip()
        summary["failed_step"] = "validate_output_path"
        _validate_output_path(summary["output_path"])

        summary["teaser_success"] = True
        summary["overall_success"] = True
        summary["failed_step"] = ""
        _print_summary(summary)
        return 0
    except Exception as exc:
        _print_summary(summary)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
