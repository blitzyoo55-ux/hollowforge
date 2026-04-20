"""Run a bounded Production Hub handoff smoke flow against a live backend."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = Path(__file__).resolve().parents[1]
for candidate in (SCRIPT_DIR, BACKEND_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import launch_comic_mvp_smoke as comic_smoke


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_CONTENT_MODE = "adult_nsfw"
DEFAULT_TITLE_PREFIX = "Smoke"
DEFAULT_STORY_PROMPT = (
    "{character_name} compares notes with a quiet messenger in the Moonlit Bathhouse corridor after closing."
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--content-mode", default=DEFAULT_CONTENT_MODE, choices=("all_ages", "adult_nsfw"))
    parser.add_argument("--title-prefix", default=DEFAULT_TITLE_PREFIX)
    parser.add_argument("--story-prompt", default=DEFAULT_STORY_PROMPT)
    parser.add_argument("--character-id")
    parser.add_argument("--character-version-id")
    parser.add_argument("--character-slug")
    parser.add_argument("--verification-run-id")
    return parser


def _timestamp_suffix() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _sequence_contract(content_mode: str) -> dict[str, Any]:
    if content_mode == "adult_nsfw":
        return {
            "policy_profile_id": "adult_stage1_v1",
            "beat_grammar_id": "adult_stage1_v1",
            "executor_policy": "adult_remote_prod",
            "shot_count": 6,
            "target_duration_sec": 36,
            "tone": "tense",
        }
    return {
        "policy_profile_id": "safe_stage1_v1",
        "beat_grammar_id": "stage1_single_location_v1",
        "executor_policy": "safe_remote_prod",
        "shot_count": 6,
        "target_duration_sec": 36,
        "tone": "tense",
    }


def _require_id(payload: dict[str, Any], key: str, *, label: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{label} did not include {key}")
    return value


def _require_nested_id(payload: dict[str, Any], key: str, *, label: str) -> str:
    nested = payload.get(key)
    if not isinstance(nested, dict):
        raise RuntimeError(f"{label} did not include {key}")
    return _require_id(nested, "id", label=label)


def _story_planner_registry_id(selected_character: dict[str, Any]) -> str:
    slug = str(selected_character.get("slug") or "").strip()
    if slug:
        return slug.replace("-", "_")

    character_id = str(selected_character.get("id") or "").strip()
    if character_id.startswith("char_"):
        return character_id[len("char_") :]
    if character_id:
        return character_id

    raise RuntimeError("Selected character is missing a usable story planner registry id")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        base_url = str(args.base_url or "").rstrip("/")
        content_mode = str(args.content_mode or DEFAULT_CONTENT_MODE)
        suffix = _timestamp_suffix()
        title_prefix = str(args.title_prefix or DEFAULT_TITLE_PREFIX).strip() or DEFAULT_TITLE_PREFIX
        verification_run_id = str(
            args.verification_run_id or f"prod-verify-{uuid.uuid4()}"
        ).strip()

        selected_character, selected_version, _, _ = comic_smoke._resolve_character_and_version(
            base_url=base_url,
            character_version_id=args.character_version_id,
            character_id=args.character_id,
            character_slug=args.character_slug,
        )

        character_name = str(selected_character.get("name") or selected_character.get("slug") or "Smoke Character")
        story_prompt = comic_smoke._render_story_prompt(
            str(args.story_prompt or DEFAULT_STORY_PROMPT),
            character_name=character_name,
            character_slug=str(selected_character.get("slug") or ""),
        )

        work = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(base_url, "/api/v1/production/works"),
                {
                    "title": f"{title_prefix} Work {suffix}",
                    "format_family": "mixed",
                    "default_content_mode": content_mode,
                    "status": "draft",
                    "record_origin": "verification_smoke",
                    "verification_run_id": verification_run_id,
                },
            ),
            label="production work",
        )
        work_id = _require_id(work, "id", label="production work")

        series = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(base_url, "/api/v1/production/series"),
                {
                    "work_id": work_id,
                    "title": f"{title_prefix} Series {suffix}",
                    "delivery_mode": "serial",
                    "audience_mode": content_mode,
                    "record_origin": "verification_smoke",
                    "verification_run_id": verification_run_id,
                },
            ),
            label="production series",
        )
        series_id = _require_id(series, "id", label="production series")

        production_episode = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(base_url, "/api/v1/production/episodes"),
                {
                    "work_id": work_id,
                    "series_id": series_id,
                    "title": f"{title_prefix} Production Episode",
                    "synopsis": "End-to-end smoke episode for ProductionHub handoff validation.",
                    "content_mode": content_mode,
                    "target_outputs": ["comic", "animation"],
                    "status": "draft",
                    "record_origin": "verification_smoke",
                    "verification_run_id": verification_run_id,
                },
            ),
            label="production episode",
        )
        production_episode_id = _require_id(production_episode, "id", label="production episode")

        approved_plan = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(base_url, "/api/v1/tools/story-planner/plan"),
                {
                    "story_prompt": story_prompt,
                    "lane": content_mode,
                    "cast": [
                        {
                            "role": "lead",
                            "source_type": "registry",
                            "character_id": _story_planner_registry_id(selected_character),
                        }
                    ],
                },
            ),
            label="story planner plan",
        )

        comic_episode_detail = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(base_url, "/api/v1/comic/episodes/import-story-plan"),
                {
                    "approved_plan": approved_plan,
                    "character_version_id": _require_id(
                        selected_version,
                        "id",
                        label="selected character version",
                    ),
                    "title": f"{title_prefix} Comic Track",
                    "panel_multiplier": 2,
                    "work_id": work_id,
                    "series_id": series_id,
                    "production_episode_id": production_episode_id,
                    "content_mode": content_mode,
                },
            ),
            label="comic import response",
        )
        comic_episode_id = comic_smoke._extract_episode_id(comic_episode_detail)

        location = comic_smoke._require_object(approved_plan.get("location"), label="story planner location")
        contract = _sequence_contract(content_mode)
        sequence_blueprint_detail = comic_smoke._require_object(
            comic_smoke._request_json(
                "POST",
                comic_smoke._build_url(base_url, "/api/v1/sequences/blueprints"),
                {
                    "work_id": work_id,
                    "series_id": series_id,
                    "production_episode_id": production_episode_id,
                    "content_mode": content_mode,
                    "policy_profile_id": contract["policy_profile_id"],
                    "character_id": _require_id(selected_character, "id", label="selected character"),
                    "location_id": _require_id(location, "id", label="story planner location"),
                    "beat_grammar_id": contract["beat_grammar_id"],
                    "target_duration_sec": contract["target_duration_sec"],
                    "shot_count": contract["shot_count"],
                    "tone": contract["tone"],
                    "executor_policy": contract["executor_policy"],
                },
            ),
            label="sequence blueprint response",
        )
        sequence_blueprint_id = _require_nested_id(
            sequence_blueprint_detail,
            "blueprint",
            label="sequence blueprint response",
        )

        refreshed_detail = comic_smoke._require_object(
            comic_smoke._request_json(
                "GET",
                comic_smoke._build_url(
                    base_url,
                    f"/api/v1/production/episodes/{production_episode_id}",
                ),
            ),
            label="production episode detail",
        )

        comic_track_count = int(refreshed_detail.get("comic_track_count") or 0)
        animation_track_count = int(refreshed_detail.get("animation_track_count") or 0)
        if comic_track_count < 1:
            raise RuntimeError("Production hub smoke did not link a comic track")
        if animation_track_count < 1:
            raise RuntimeError("Production hub smoke did not link an animation track")

        summary = {
            "suite_mode": "production_hub_smoke",
            "base_url": base_url,
            "content_mode": content_mode,
            "verification_run_id": verification_run_id,
            "work_id": work_id,
            "series_id": series_id,
            "production_episode_id": production_episode_id,
            "comic_episode_id": comic_episode_id,
            "sequence_blueprint_id": sequence_blueprint_id,
            "comic_track_count": comic_track_count,
            "animation_track_count": animation_track_count,
            "overall_success": True,
        }
        for key, value in summary.items():
            comic_smoke._print_marker(key, value)
        return 0
    except Exception as exc:
        comic_smoke._print_marker("suite_mode", "production_hub_smoke")
        comic_smoke._print_marker("overall_success", False)
        comic_smoke._print_marker("error_summary", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
