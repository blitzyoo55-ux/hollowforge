"""Run a bounded HollowForge comic MVP smoke flow against a live backend."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_STORY_PROMPT = (
    "{character_name} pauses in a private intake lounge after closing "
    "to review a sealed invitation."
)
DEFAULT_TITLE = "Comic MVP Smoke"
DEFAULT_STORY_LANE = "adult_nsfw"
DEFAULT_LAYOUT_TEMPLATE_ID = "jp_2x2_v1"
DEFAULT_PANEL_MULTIPLIER = 1


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
        {
            key: value
            for key, value in params.items()
            if value is not None and value != ""
        }
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


def _render_story_prompt(template: str, *, character_name: str, character_slug: str) -> str:
    return (
        template.replace("{character_name}", character_name).replace(
            "{character_slug}", character_slug
        )
    )


def _resolve_character_and_version(
    *,
    base_url: str,
    character_version_id: str | None,
    character_id: str | None,
    character_slug: str | None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    def _version_sort_key(version_row: dict[str, Any]) -> tuple[int, str]:
        purpose = str(version_row.get("purpose") or "").lower()
        workflow_lane = str(version_row.get("workflow_lane") or "").lower()
        version_name = str(version_row.get("version_name") or "").lower()
        score = 0
        if any(token in purpose for token in ("comic", "manga", "still")):
            score += 10
        if any(token in purpose for token in ("anim", "animation", "video")):
            score -= 10
        if any(token in workflow_lane for token in ("sdxl", "illustrious")):
            score += 3
        if "still" in version_name:
            score += 1
        return (score, version_name)

    characters = _require_list(
        _request_json("GET", _build_url(base_url, "/api/v1/comic/characters")),
        label="comic characters",
    )
    versions = _require_list(
        _request_json(
            "GET",
            _build_url(base_url, "/api/v1/comic/character-versions"),
        ),
        label="comic character versions",
    )

    if not characters:
        raise RuntimeError("Comic smoke requires at least one comic character")
    if not versions:
        raise RuntimeError("Comic smoke requires at least one comic character version")

    characters_by_id = {
        str(item.get("id")): item for item in characters if str(item.get("id") or "").strip()
    }

    selected_character: dict[str, Any] | None = None
    if character_id:
        selected_character = characters_by_id.get(character_id)
        if selected_character is None:
            raise RuntimeError(f"Comic character not found: {character_id}")
    elif character_slug:
        selected_character = next(
            (
                item
                for item in characters
                if str(item.get("slug") or "").strip() == character_slug
            ),
            None,
        )
        if selected_character is None:
            raise RuntimeError(f"Comic character slug not found: {character_slug}")

    selected_version: dict[str, Any] | None = None
    if character_version_id:
        selected_version = next(
            (
                item
                for item in versions
                if str(item.get("id") or "").strip() == character_version_id
            ),
            None,
        )
        if selected_version is None:
            raise RuntimeError(f"Comic character version not found: {character_version_id}")
    else:
        candidate_versions = versions
        if selected_character is not None:
            candidate_versions = [
                item
                for item in versions
                if str(item.get("character_id") or "").strip()
                == str(selected_character.get("id") or "").strip()
            ]
        if not candidate_versions:
            raise RuntimeError("Comic smoke could not find a usable character version")
        candidate_versions.sort(key=_version_sort_key, reverse=True)
        selected_version = candidate_versions[0]

    version_character_id = str(selected_version.get("character_id") or "").strip()
    if not version_character_id:
        raise RuntimeError("Selected comic character version is missing character_id")

    if selected_character is None:
        selected_character = characters_by_id.get(version_character_id)
        if selected_character is None:
            raise RuntimeError(
                "Selected comic character version points to an unknown character"
            )

    return selected_character, selected_version, characters, versions


def _extract_episode_id(episode_detail: dict[str, Any]) -> str:
    episode = episode_detail.get("episode")
    if not isinstance(episode, dict):
        raise RuntimeError("Comic import response is missing episode detail")
    episode_id = str(episode.get("id") or "").strip()
    if not episode_id:
        raise RuntimeError("Comic import response did not include episode id")
    return episode_id


def _extract_first_panel_id(episode_detail: dict[str, Any]) -> str:
    return _extract_panel_ids(episode_detail)[0]


def _extract_panel_ids(episode_detail: dict[str, Any]) -> list[str]:
    scenes = episode_detail.get("scenes")
    if not isinstance(scenes, list):
        raise RuntimeError("Comic import response is missing scenes")

    panel_ids: list[str] = []
    for scene_detail in scenes:
        if not isinstance(scene_detail, dict):
            continue
        panels = scene_detail.get("panels")
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


def _print_marker(key: str, value: Any) -> None:
    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif value is None:
        rendered = ""
    else:
        rendered = str(value)
    print(f"{key}: {rendered}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _relative_data_path(path: Path) -> str:
    return str(path.resolve().relative_to(settings.DATA_DIR.resolve())).replace("\\", "/")


def _is_local_backend_url(base_url: str) -> bool:
    parsed = urlparse(base_url)
    hostname = (parsed.hostname or "").strip().lower()
    return hostname in {"127.0.0.1", "localhost", "::1"}


def _write_synthetic_asset_preview(*, panel_id: str, asset_id: str) -> str:
    output_dir = settings.COMICS_PREVIEWS_DIR / "smoke_assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{panel_id}_{asset_id}.png"

    image = Image.new("RGB", (832, 1216), "#f7f1e4")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((32, 32, 800, 1184), radius=28, outline="#3d2e1f", width=6, fill="#fffdf8")
    draw.text((72, 96), "Comic MVP Smoke Placeholder", fill="#2c2319")
    draw.text((72, 150), f"panel_id: {panel_id}", fill="#5a4633")
    draw.text((72, 204), f"asset_id: {asset_id}", fill="#5a4633")
    image.save(output_path, format="PNG")
    return _relative_data_path(output_path)


def _bind_asset_storage_path(*, asset_id: str, storage_path: str) -> None:
    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            UPDATE comic_panel_render_assets
            SET storage_path = ?, updated_at = ?
            WHERE id = ?
            """,
            (storage_path, _now_iso(), asset_id),
        )
        conn.commit()


def _queue_and_select_panel_asset(
    *,
    base_url: str,
    panel_id: str,
    candidate_count: int,
    poll_attempts: int,
    poll_sec: float,
    allow_synthetic_asset_fallback: bool,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    queue_url = _build_url(
        base_url,
        f"/api/v1/comic/panels/{panel_id}/queue-renders",
        {"candidate_count": candidate_count},
    )
    last_queue_response: dict[str, Any] | None = None
    selected_candidate: dict[str, Any] | None = None

    for attempt in range(poll_attempts):
        queue_response = _require_object(
            _request_json("POST", queue_url),
            label=f"comic panel render queue {panel_id}",
        )
        render_assets = _require_list(
            queue_response.get("render_assets") or [],
            label=f"comic panel render assets {panel_id}",
        )
        last_queue_response = queue_response
        selected_candidate = next(
            (
                asset
                for asset in render_assets
                if str(asset.get("storage_path") or "").strip()
            ),
            None,
        )
        if selected_candidate is not None:
            break
        if attempt + 1 < poll_attempts:
            time.sleep(max(0.1, poll_sec))

    if last_queue_response is None:
        raise RuntimeError(f"Comic smoke did not queue renders for panel {panel_id}")
    synthetic_fallback_used = False
    if selected_candidate is None:
        if allow_synthetic_asset_fallback:
            if not _is_local_backend_url(base_url):
                raise RuntimeError(
                    "Synthetic asset fallback is only supported for local backend URLs"
                )
            fallback_assets = _require_list(
                last_queue_response.get("render_assets") or [],
                label=f"comic panel render assets {panel_id}",
            )
            fallback_asset = fallback_assets[0] if fallback_assets else None
            if fallback_asset is None:
                raise RuntimeError(f"Comic smoke did not receive any render assets for panel {panel_id}")
            storage_path = _write_synthetic_asset_preview(
                panel_id=panel_id,
                asset_id=str(fallback_asset["id"]),
            )
            _bind_asset_storage_path(
                asset_id=str(fallback_asset["id"]),
                storage_path=storage_path,
            )
            selected_candidate = {
                **fallback_asset,
                "storage_path": storage_path,
            }
            synthetic_fallback_used = True
        else:
            raise TimeoutError(
                f"Comic smoke could not find a materialized render asset for panel {panel_id}"
            )

    select_response = _require_object(
        _request_json(
            "POST",
            _build_url(
                base_url,
                f"/api/v1/comic/panels/{panel_id}/assets/{selected_candidate['id']}/select",
            ),
        ),
        label=f"comic panel asset selection {panel_id}",
    )
    return last_queue_response, select_response, synthetic_fallback_used


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
    parser.add_argument("--render-poll-attempts", type=int, default=20)
    parser.add_argument("--render-poll-sec", type=float, default=1.0)
    parser.add_argument("--no-synthetic-asset-fallback", action="store_true")
    parser.add_argument(
        "--layout-template-id",
        default=DEFAULT_LAYOUT_TEMPLATE_ID,
    )
    args = parser.parse_args()

    summary: dict[str, Any] = {
        "base_url": args.base_url.rstrip("/"),
        "import_success": False,
        "queue_renders_success": False,
        "dialogues_success": False,
        "assemble_success": False,
        "export_success": False,
        "overall_success": False,
        "synthetic_asset_fallback_used": False,
        "synthetic_asset_fallback_count": 0,
    }
    current_step = "bootstrap"

    try:
        current_step = "resolve_character_context"
        character, version, characters, versions = _resolve_character_and_version(
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
        story_prompt = _render_story_prompt(
            args.story_prompt,
            character_name=str(character.get("name") or "Lead"),
            character_slug=str(character.get("slug") or ""),
        )
        approved_plan = _require_object(
            _request_json(
                "POST",
                _build_url(args.base_url, "/api/v1/tools/story-planner/plan"),
                {
                    "story_prompt": story_prompt,
                    "lane": args.story_lane,
                },
            ),
            label="story planner plan",
        )
        summary["story_prompt"] = approved_plan.get("story_prompt") or story_prompt
        summary["story_lane"] = approved_plan.get("lane") or args.story_lane
        summary["approval_token"] = approved_plan.get("approval_token")

        current_step = "import_story_plan"
        episode_detail = _require_object(
            _request_json(
                "POST",
                _build_url(args.base_url, "/api/v1/comic/episodes/import-story-plan"),
                {
                    "approved_plan": approved_plan,
                    "character_version_id": version["id"],
                    "title": args.title,
                    "panel_multiplier": args.panel_multiplier,
                },
            ),
            label="comic story import",
        )
        episode_id = _extract_episode_id(episode_detail)
        panel_ids = _extract_panel_ids(episode_detail)
        panel_id = panel_ids[0]
        summary["import_success"] = True
        summary["episode_id"] = episode_id
        summary["first_panel_id"] = panel_id
        summary["panel_count"] = len(panel_ids)
        summary["scene_count"] = len(episode_detail.get("scenes") or [])

        current_step = "queue_renders"
        queued_generation_count = 0
        render_asset_count = 0
        selected_asset_count = 0
        selected_asset = None
        for current_panel_id in panel_ids:
            queue_response, selected_asset_response, used_synthetic_fallback = _queue_and_select_panel_asset(
                base_url=args.base_url,
                panel_id=current_panel_id,
                candidate_count=args.candidate_count,
                poll_attempts=args.render_poll_attempts,
                poll_sec=args.render_poll_sec,
                allow_synthetic_asset_fallback=not args.no_synthetic_asset_fallback,
            )
            render_assets = _require_list(
                queue_response.get("render_assets") or [],
                label=f"comic panel render assets {current_panel_id}",
            )
            queued_generation_count += int(queue_response.get("queued_generation_count") or 0)
            render_asset_count += len(render_assets)
            selected_asset_count += 1
            if used_synthetic_fallback:
                summary["synthetic_asset_fallback_used"] = True
                summary["synthetic_asset_fallback_count"] = int(summary["synthetic_asset_fallback_count"]) + 1
            if current_panel_id == panel_id:
                selected_asset = selected_asset_response

        summary["queue_renders_success"] = True
        summary["queued_generation_count"] = queued_generation_count
        summary["render_asset_count"] = render_asset_count
        summary["selected_panel_asset_count"] = selected_asset_count
        summary["first_render_asset_id"] = selected_asset.get("id") if selected_asset else None
        summary["selected_render_asset_available"] = selected_asset is not None
        summary["selected_render_asset_id"] = (
            selected_asset.get("id") if selected_asset is not None else None
        )

        current_step = "draft_dialogues"
        dialogue_response = _require_object(
            _request_json(
                "POST",
                _build_url(
                    args.base_url,
                    f"/api/v1/comic/panels/{panel_id}/dialogues/generate",
                ),
            ),
            label="comic dialogue generation",
        )
        summary["dialogues_success"] = True
        summary["generated_dialogue_count"] = dialogue_response.get("generated_count")

        current_step = "assemble_pages"
        assemble_params = None
        if args.layout_template_id != DEFAULT_LAYOUT_TEMPLATE_ID:
            assemble_params = {"layout_template_id": args.layout_template_id}
        assembly_response = _require_object(
            _request_json(
                "POST",
                _build_url(
                    args.base_url,
                    f"/api/v1/comic/episodes/{episode_id}/pages/assemble",
                    assemble_params,
                ),
            ),
            label="comic page assembly",
        )
        assembled_pages = _require_list(
            assembly_response.get("pages") or [],
            label="comic assembled pages",
        )
        summary["assemble_success"] = True
        summary["assembled_page_count"] = len(assembled_pages)
        summary["first_preview_path"] = (
            assembled_pages[0].get("preview_path") if assembled_pages else None
        )
        summary["export_manifest_path"] = assembly_response.get("export_manifest_path")
        summary["dialogue_json_path"] = assembly_response.get("dialogue_json_path")
        summary["panel_asset_manifest_path"] = assembly_response.get(
            "panel_asset_manifest_path"
        )
        summary["page_assembly_manifest_path"] = assembly_response.get(
            "page_assembly_manifest_path"
        )

        current_step = "export_pages"
        export_params = None
        if args.layout_template_id != DEFAULT_LAYOUT_TEMPLATE_ID:
            export_params = {"layout_template_id": args.layout_template_id}
        export_response = _require_object(
            _request_json(
                "POST",
                _build_url(
                    args.base_url,
                    f"/api/v1/comic/episodes/{episode_id}/pages/export",
                    export_params,
                ),
            ),
            label="comic page export",
        )
        exported_pages = _require_list(
            export_response.get("pages") or [],
            label="comic exported pages",
        )
        summary["export_success"] = True
        summary["exported_page_count"] = len(exported_pages)
        summary["export_zip_path"] = export_response.get("export_zip_path")

        current_step = "fetch_episode"
        episode_refresh = _require_object(
            _request_json(
                "GET",
                _build_url(args.base_url, f"/api/v1/comic/episodes/{episode_id}"),
            ),
            label="comic episode detail",
        )
        summary["episode_scene_count"] = len(episode_refresh.get("scenes") or [])
        summary["episode_page_count"] = len(episode_refresh.get("pages") or [])
        summary["overall_success"] = True

        for key, value in summary.items():
            _print_marker(key, value)
        return 0
    except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        summary["failed_step"] = current_step
        summary["error_message"] = str(exc)
        for key, value in summary.items():
            _print_marker(key, value)
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
