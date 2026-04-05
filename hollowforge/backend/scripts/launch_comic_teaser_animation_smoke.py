"""Launch a guarded HollowForge comic teaser animation smoke helper."""

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


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_PRESET_ID = "sdxl_ipadapter_microanim_v2"
PLACEHOLDER_ASSET_MARKER = "comics/previews/smoke_assets"


def _is_placeholder_asset(storage_path: str) -> bool:
    return PLACEHOLDER_ASSET_MARKER in storage_path.strip().replace("\\", "/")


def _print_summary(summary: dict[str, Any]) -> None:
    for key, value in summary.items():
        comic_smoke._print_marker(key, value)


def _resolve_source_asset(**_: Any) -> dict[str, Any]:
    raise RuntimeError("source asset resolution is not implemented yet")


def _extract_selected_asset_id(source_asset: dict[str, Any]) -> str:
    return str(
        source_asset.get("selected_render_asset_id") or source_asset.get("id") or ""
    ).strip()


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--episode-id")
    parser.add_argument("--panel-index", type=int, default=0)
    parser.add_argument("--preset-id", default=DEFAULT_PRESET_ID)
    parser.add_argument("--poll-sec", type=float, default=1.0)
    parser.add_argument("--timeout-sec", type=float, default=1800.0)
    args = parser.parse_args()

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

        summary["episode_id"] = str(source_asset.get("episode_id") or args.episode_id or "")
        summary["scene_panel_id"] = str(source_asset.get("scene_panel_id") or "")
        summary["selected_render_asset_id"] = _extract_selected_asset_id(source_asset)
        summary["generation_id"] = str(source_asset.get("generation_id") or "")

        storage_path = str(source_asset.get("storage_path") or "").strip()
        if not storage_path:
            raise RuntimeError("selected asset storage_path is missing")
        if _is_placeholder_asset(storage_path):
            raise RuntimeError("placeholder selected asset is not allowed")

        summary["failed_step"] = "launch"
        raise RuntimeError("animation launch is not implemented yet")
    except RuntimeError as exc:
        _print_summary(summary)
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
