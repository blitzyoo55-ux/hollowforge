from __future__ import annotations

import importlib.util
from pathlib import Path


def _module_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "launch_production_hub_smoke.py"


def _load_module():
    module_path = _module_path()
    assert module_path.exists(), f"Missing script: {module_path}"
    spec = importlib.util.spec_from_file_location(
        "launch_production_hub_smoke",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_creates_linked_production_handoff_records_and_prints_markers(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8014"
    request_calls: list[tuple[str, str, dict[str, object] | None]] = []

    selected_character = {
        "id": "char_hana_seo",
        "slug": "hana-seo",
        "name": "Hana Seo",
    }
    selected_version = {
        "id": "charver_hana_seo_still_v1",
        "character_id": "char_hana_seo",
        "version_name": "canonical_still_v1",
    }

    story_plan = {
        "story_prompt": "Hana Seo compares notes with a quiet messenger in the Moonlit Bathhouse corridor after closing.",
        "lane": "adult_nsfw",
        "policy_pack_id": "canon_adult_nsfw_v1",
        "approval_token": "a" * 64,
        "anchor_render": {
            "policy_pack_id": "canon_adult_nsfw_v1",
            "checkpoint": "waiIllustriousSDXL_v140.safetensors",
            "workflow_lane": "sdxl_illustrious",
            "negative_prompt": "minors, age ambiguity, non-consensual framing",
            "preserve_blank_negative_prompt": False,
        },
        "resolved_cast": [
            {
                "source_type": "registry",
                "character_id": "hana_seo",
                "character_name": "Hana Seo",
            }
        ],
        "location": {
            "id": "moonlit_bathhouse",
            "name": "Moonlit Bathhouse",
            "match_note": "matched",
            "setting_anchor": "Moonlit Bathhouse corridor after closing.",
            "visual_rules": [],
            "restricted_elements": [],
        },
        "episode_brief": {
            "premise": "Hana Seo pauses before deciding whether to trust the messenger.",
        },
        "shots": [
            {"shot_no": 1},
            {"shot_no": 2},
            {"shot_no": 3},
            {"shot_no": 4},
        ],
    }

    production_episode_detail = {
        "id": "prod-ep-1",
        "work_id": "work-smoke-1",
        "series_id": "series-smoke-1",
        "title": "Smoke Production Episode",
        "synopsis": "End-to-end smoke episode for ProductionHub handoff validation.",
        "content_mode": "adult_nsfw",
        "status": "draft",
        "target_outputs": ["comic", "animation"],
        "continuity_summary": None,
        "comic_track_count": 0,
        "animation_track_count": 0,
        "comic_track": None,
        "animation_track": None,
        "created_at": "2026-04-18T00:00:00+00:00",
        "updated_at": "2026-04-18T00:00:00+00:00",
    }

    import_response = {
        "episode": {
            "id": "comic-ep-1",
            "character_id": "char_hana_seo",
            "character_version_id": "charver_hana_seo_still_v1",
            "production_episode_id": "prod-ep-1",
            "work_id": "work-smoke-1",
            "series_id": "series-smoke-1",
            "title": "Smoke Comic Track",
        },
        "scenes": [
            {
                "scene": {"id": "scene-1", "scene_no": 1},
                "panels": [{"id": "panel-1", "panel_no": 1}],
            }
        ],
        "pages": [],
    }

    blueprint_response = {
        "blueprint": {
            "id": "blueprint-1",
            "production_episode_id": "prod-ep-1",
            "work_id": "work-smoke-1",
            "series_id": "series-smoke-1",
            "content_mode": "adult_nsfw",
            "policy_profile_id": "adult_stage1_v1",
            "character_id": "char_hana_seo",
            "location_id": "moonlit_bathhouse",
            "beat_grammar_id": "adult_stage1_v1",
            "target_duration_sec": 36,
            "shot_count": 6,
            "tone": "tense",
            "executor_policy": "adult_remote_prod",
            "created_at": "2026-04-18T00:00:00+00:00",
            "updated_at": "2026-04-18T00:00:00+00:00",
        },
        "planned_shots": [],
    }

    linked_detail = {
        **production_episode_detail,
        "comic_track_count": 1,
        "animation_track_count": 1,
        "comic_track": {
            "id": "comic-ep-1",
            "status": "planned",
            "target_output": "oneshot_manga",
            "character_id": "char_hana_seo",
        },
        "animation_track": {
            "id": "blueprint-1",
            "content_mode": "adult_nsfw",
            "policy_profile_id": "adult_stage1_v1",
            "shot_count": 6,
            "executor_policy": "adult_remote_prod",
        },
    }

    def fake_request_json(
        method: str,
        url: str,
        payload: dict[str, object] | None = None,
    ):  # type: ignore[no-untyped-def]
        request_calls.append((method, url, payload))
        key = (method, url)
        responses = {
            ("POST", f"{base_url}/api/v1/production/works"): {
                "id": "work-smoke-1",
                "title": "Smoke Work",
                "format_family": "mixed",
                "default_content_mode": "adult_nsfw",
                "status": "draft",
                "canon_notes": None,
                "created_at": "2026-04-18T00:00:00+00:00",
                "updated_at": "2026-04-18T00:00:00+00:00",
            },
            ("POST", f"{base_url}/api/v1/production/series"): {
                "id": "series-smoke-1",
                "work_id": "work-smoke-1",
                "title": "Smoke Series",
                "delivery_mode": "serial",
                "audience_mode": "adult_nsfw",
                "visual_identity_notes": None,
                "created_at": "2026-04-18T00:00:00+00:00",
                "updated_at": "2026-04-18T00:00:00+00:00",
            },
            ("POST", f"{base_url}/api/v1/production/episodes"): production_episode_detail,
            ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): story_plan,
            ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): import_response,
            ("POST", f"{base_url}/api/v1/sequences/blueprints"): blueprint_response,
            ("GET", f"{base_url}/api/v1/production/episodes/prod-ep-1"): linked_detail,
        }
        if key not in responses:
            raise AssertionError(f"Unexpected request: {method} {url}")
        return responses[key]

    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: (
            selected_character,
            selected_version,
            [selected_character],
            [selected_version],
        ),
    )

    assert module.main(
        ["--base-url", base_url, "--verification-run-id", "run-smoke-1"]
    ) == 0

    captured = capsys.readouterr()
    assert "suite_mode: production_hub_smoke" in captured.out
    assert "production_episode_id: prod-ep-1" in captured.out
    assert "comic_episode_id: comic-ep-1" in captured.out
    assert "sequence_blueprint_id: blueprint-1" in captured.out
    assert "comic_track_count: 1" in captured.out
    assert "animation_track_count: 1" in captured.out
    assert "overall_success: true" in captured.out

    import_call = next(
        payload
        for method, url, payload in request_calls
        if method == "POST" and url == f"{base_url}/api/v1/comic/episodes/import-story-plan"
    )
    assert import_call is not None
    assert import_call["production_episode_id"] == "prod-ep-1"
    assert import_call["work_id"] == "work-smoke-1"
    assert import_call["series_id"] == "series-smoke-1"

    work_call = next(
        payload
        for method, url, payload in request_calls
        if method == "POST" and url == f"{base_url}/api/v1/production/works"
    )
    assert work_call is not None
    assert work_call["record_origin"] == "verification_smoke"
    assert work_call["verification_run_id"] == "run-smoke-1"

    series_call = next(
        payload
        for method, url, payload in request_calls
        if method == "POST" and url == f"{base_url}/api/v1/production/series"
    )
    assert series_call is not None
    assert series_call["record_origin"] == "verification_smoke"
    assert series_call["verification_run_id"] == "run-smoke-1"

    episode_call = next(
        payload
        for method, url, payload in request_calls
        if method == "POST" and url == f"{base_url}/api/v1/production/episodes"
    )
    assert episode_call is not None
    assert episode_call["record_origin"] == "verification_smoke"
    assert episode_call["verification_run_id"] == "run-smoke-1"

    blueprint_call = next(
        payload
        for method, url, payload in request_calls
        if method == "POST" and url == f"{base_url}/api/v1/sequences/blueprints"
    )
    assert blueprint_call is not None
    assert blueprint_call["production_episode_id"] == "prod-ep-1"
    assert blueprint_call["character_id"] == "char_hana_seo"
    assert blueprint_call["location_id"] == "moonlit_bathhouse"
