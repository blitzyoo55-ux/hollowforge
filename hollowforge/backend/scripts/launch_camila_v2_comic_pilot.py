"""Launch a bounded Camila V2 comic pilot helper."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_STORY_PROMPT = "Camila checks the studio lockbox at closing."
DEFAULT_STORY_LANE = "adult_nsfw"
DEFAULT_TITLE = "Camila V2 Comic Pilot"
DEFAULT_PANEL_MULTIPLIER = 1
DEFAULT_CANDIDATE_COUNT = 3

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


def _pick_selectable_asset(render_assets: list[dict[str, Any]]) -> dict[str, Any]:
    selected = next(
        (asset for asset in render_assets if str(asset.get("storage_path") or "").strip()),
        None,
    )
    if selected is None and render_assets:
        selected = render_assets[0]
    if selected is None:
        raise RuntimeError("Panel render queue did not return any candidate assets")
    asset_id = str(selected.get("id") or "").strip()
    if not asset_id:
        raise RuntimeError("Panel render candidate is missing id")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--story-prompt", default=DEFAULT_STORY_PROMPT)
    parser.add_argument("--story-lane", default=DEFAULT_STORY_LANE)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--panel-multiplier", type=int, default=DEFAULT_PANEL_MULTIPLIER)
    parser.add_argument("--candidate-count", type=int, default=DEFAULT_CANDIDATE_COUNT)
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
        for index, panel_id in enumerate(panel_ids):
            queue_response = _require_object(
                _request_json(
                    "POST",
                    _build_url(
                        args.base_url,
                        f"/api/v1/comic/panels/{panel_id}/queue-renders",
                        {"candidate_count": args.candidate_count},
                    ),
                ),
                label=f"comic panel render queue {panel_id}",
            )
            total_queued += int(queue_response.get("queued_generation_count") or 0)
            render_assets = _require_list(
                queue_response.get("render_assets") or [],
                label=f"comic panel render assets {panel_id}",
            )
            selected_candidate = _pick_selectable_asset(render_assets)
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
            if index == 0:
                first_storage_path = str(selected_asset.get("storage_path") or "").strip()

        summary["queued_generation_count"] = total_queued
        summary["selected_render_asset_storage_path"] = first_storage_path
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
