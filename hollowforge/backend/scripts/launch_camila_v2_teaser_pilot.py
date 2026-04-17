"""Launch a bounded Camila V2 teaser pilot helper."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

BACKEND_DIR = SCRIPT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.series_style_canon_registry import get_series_style_canon


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_POLL_SEC = 1.0
DEFAULT_TIMEOUT_SEC = 120.0
REQUIRED_RENDER_LANE = "character_canon_v2"

MOTION_POLICY_PRESET_MAP: dict[str, str] = {
    "static_hero": "sdxl_ipadapter_microanim_v2",
    "subtle_loop": "sdxl_ipadapter_microanim_subtle_loop_v1",
}


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


def _require_object(payload: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object for {label}")
    return payload


def _print_marker(key: str, value: Any) -> None:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif value is None:
        rendered = ""
    else:
        rendered = str(value)
    print(f"{key}: {rendered}")


def _resolve_execution_preset_for_style(series_style_id: str) -> tuple[str, str]:
    style = get_series_style_canon(series_style_id=series_style_id)
    motion_policy = style.teaser_motion_policy
    preset_id = MOTION_POLICY_PRESET_MAP.get(motion_policy)
    if not preset_id:
        raise RuntimeError(
            "No teaser preset mapping configured for teaser_motion_policy="
            f"{motion_policy}"
        )
    return motion_policy, preset_id


def _extract_episode_v2_context(episode_detail: dict[str, Any]) -> dict[str, str]:
    episode = episode_detail.get("episode")
    if not isinstance(episode, dict):
        raise RuntimeError("Episode detail is missing episode payload")

    episode_id = str(episode.get("id") or "").strip()
    render_lane = str(episode.get("render_lane") or "").strip()
    series_style_id = str(episode.get("series_style_id") or "").strip()
    character_series_binding_id = str(
        episode.get("character_series_binding_id") or ""
    ).strip()
    if not episode_id:
        raise RuntimeError("Episode detail is missing episode id")
    if render_lane != REQUIRED_RENDER_LANE:
        raise RuntimeError(
            f"Episode {episode_id} is not in render_lane={REQUIRED_RENDER_LANE}"
        )
    if not series_style_id:
        raise RuntimeError("V2 episode is missing series_style_id")
    if not character_series_binding_id:
        raise RuntimeError("V2 episode is missing character_series_binding_id")
    return {
        "episode_id": episode_id,
        "series_style_id": series_style_id,
        "character_series_binding_id": character_series_binding_id,
    }


def _resolve_selected_render_context(
    *,
    episode_detail: dict[str, Any],
    selected_scene_panel_id: str | None,
    selected_render_asset_id: str | None,
    selected_render_generation_id: str | None,
    selected_render_asset_storage_path: str | None,
) -> dict[str, str]:
    episode_context = _extract_episode_v2_context(episode_detail)

    explicit_scene_panel_id = str(selected_scene_panel_id or "").strip()
    explicit_asset_id = str(selected_render_asset_id or "").strip()
    explicit_generation_id = str(selected_render_generation_id or "").strip()
    explicit_storage_path = str(selected_render_asset_storage_path or "").strip()

    explicit_values = (
        explicit_scene_panel_id,
        explicit_asset_id,
        explicit_generation_id,
        explicit_storage_path,
    )
    if any(explicit_values):
        if not all(explicit_values):
            raise RuntimeError(
                "Explicit selected render context requires scene_panel_id, "
                "selected_render_asset_id, selected_render_generation_id, and "
                "selected_render_asset_storage_path"
            )
        return {
            **episode_context,
            "selected_scene_panel_id": explicit_scene_panel_id,
            "selected_render_asset_id": explicit_asset_id,
            "selected_render_generation_id": explicit_generation_id,
            "selected_render_asset_storage_path": explicit_storage_path,
        }

    return episode_context


def _require_completed_generation(*, base_url: str, generation_id: str) -> None:
    generation = _require_object(
        _request_json("GET", f"{base_url.rstrip('/')}/api/v1/generations/{generation_id}"),
        label=f"generation {generation_id}",
    )
    status = str(generation.get("status") or "").strip().lower()
    image_path = str(generation.get("image_path") or "").strip()
    if status != "completed" or not image_path:
        raise RuntimeError(
            "Camila teaser pilot requires a completed selected render generation"
        )


def _poll_animation_job(
    *,
    base_url: str,
    animation_job_id: str,
    poll_sec: float,
    timeout_sec: float,
) -> dict[str, Any]:
    start = time.time()
    while True:
        job = _require_object(
            _request_json(
                "GET",
                f"{base_url.rstrip('/')}/api/v1/animation/jobs/{animation_job_id}",
            ),
            label=f"animation job {animation_job_id}",
        )
        status = str(job.get("status") or "").strip().lower()
        if status in {"completed", "failed", "cancelled"}:
            return job
        if (time.time() - start) > timeout_sec:
            raise TimeoutError(f"Timed out waiting for animation job {animation_job_id}")
        time.sleep(max(0.1, poll_sec))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--selected-scene-panel-id")
    parser.add_argument("--selected-render-asset-id")
    parser.add_argument("--selected-render-generation-id")
    parser.add_argument("--selected-render-asset-storage-path")
    parser.add_argument("--poll-sec", type=float, default=DEFAULT_POLL_SEC)
    parser.add_argument("--timeout-sec", type=float, default=DEFAULT_TIMEOUT_SEC)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "episode_id": str(args.episode_id or "").strip(),
        "series_style_id": "",
        "character_series_binding_id": "",
        "selected_scene_panel_id": "",
        "selected_render_asset_id": "",
        "selected_render_generation_id": "",
        "selected_render_asset_storage_path": "",
        "teaser_motion_policy": "",
        "preset_id": "",
        "animation_job_id": "",
        "animation_shot_id": "",
        "output_path": "",
        "overall_success": False,
        "failed_step": "bootstrap",
    }
    current_step = "bootstrap"

    try:
        current_step = "resolve_v2_episode_context"
        episode_detail = _require_object(
            _request_json(
                "GET",
                f"{args.base_url.rstrip('/')}/api/v1/comic/episodes/{args.episode_id}",
            ),
            label=f"comic episode {args.episode_id}",
        )
        comic_context = _resolve_selected_render_context(
            episode_detail=episode_detail,
            selected_scene_panel_id=args.selected_scene_panel_id,
            selected_render_asset_id=args.selected_render_asset_id,
            selected_render_generation_id=args.selected_render_generation_id,
            selected_render_asset_storage_path=args.selected_render_asset_storage_path,
        )
        summary["episode_id"] = comic_context["episode_id"]
        summary["series_style_id"] = comic_context["series_style_id"]
        summary["character_series_binding_id"] = comic_context[
            "character_series_binding_id"
        ]
        summary["selected_scene_panel_id"] = comic_context["selected_scene_panel_id"]
        summary["selected_render_asset_id"] = comic_context["selected_render_asset_id"]
        summary["selected_render_generation_id"] = comic_context[
            "selected_render_generation_id"
        ]
        summary["selected_render_asset_storage_path"] = comic_context[
            "selected_render_asset_storage_path"
        ]

        current_step = "resolve_motion_policy"
        motion_policy, preset_id = _resolve_execution_preset_for_style(
            comic_context["series_style_id"]
        )
        summary["teaser_motion_policy"] = motion_policy
        summary["preset_id"] = preset_id

        current_step = "require_completed_selected_render"
        _require_completed_generation(
            base_url=args.base_url,
            generation_id=comic_context["selected_render_generation_id"],
        )

        current_step = "launch_animation"
        launch_response = _require_object(
            _request_json(
                "POST",
                f"{args.base_url.rstrip('/')}/api/v1/animation/presets/{preset_id}/launch",
                {
                    "generation_id": comic_context["selected_render_generation_id"],
                    "dispatch_immediately": True,
                    "request_overrides": {},
                    "episode_id": comic_context["episode_id"],
                    "scene_panel_id": comic_context["selected_scene_panel_id"],
                    "selected_render_asset_id": comic_context["selected_render_asset_id"],
                },
            ),
            label=f"animation preset launch {preset_id}",
        )

        animation_job = _require_object(
            launch_response.get("animation_job") or {},
            label="animation launch job payload",
        )
        animation_job_id = str(animation_job.get("id") or "").strip()
        if not animation_job_id:
            raise RuntimeError("Animation launch response did not include animation job id")
        summary["animation_job_id"] = animation_job_id
        summary["animation_shot_id"] = str(
            launch_response.get("animation_shot_id")
            or launch_response.get("shot_id")
            or ""
        ).strip()

        if args.no_wait:
            summary["output_path"] = str(animation_job.get("output_path") or "").strip()
            summary["overall_success"] = True
            summary["failed_step"] = ""
            return 0

        current_step = "poll_animation"
        final_job = _poll_animation_job(
            base_url=args.base_url,
            animation_job_id=animation_job_id,
            poll_sec=args.poll_sec,
            timeout_sec=args.timeout_sec,
        )
        summary["output_path"] = str(final_job.get("output_path") or "").strip()
        final_status = str(final_job.get("status") or "").strip().lower()
        summary["overall_success"] = final_status == "completed"
        summary["failed_step"] = "" if summary["overall_success"] else current_step
        return 0 if summary["overall_success"] else 1
    except (
        HTTPError,
        URLError,
        RuntimeError,
        ValueError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        summary["failed_step"] = current_step
        return 1
    finally:
        for key, value in summary.items():
            _print_marker(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
