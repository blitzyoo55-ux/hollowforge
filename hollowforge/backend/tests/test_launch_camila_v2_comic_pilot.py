from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_camila_v2_comic_pilot.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_camila_v2_comic_pilot",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_builds_camila_v2_episode_with_explicit_ids_and_candidate_count_3(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"

    responses: dict[tuple[str, str], object] = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "Camila checks the studio lockbox at closing.",
            "lane": "adult_nsfw",
            "policy_pack_id": "adult_nsfw_default",
            "approval_token": "a" * 64,
            "anchor_render": {
                "prompt": "anchor",
                "negative_prompt": "negative",
                "checkpoint": "waiIllustriousSDXL_v160.safetensors",
                "workflow_lane": "sdxl_illustrious",
                "policy_pack_id": "adult_nsfw_default",
            },
            "resolved_cast": [],
            "location": {
                "id": "private-studio",
                "name": "Private Studio",
                "setting_anchor": "Warm, low-key studio.",
                "visual_rules": [],
                "restricted_elements": [],
                "match_note": "matched",
            },
            "episode_brief": {
                "title": "Camila Pilot",
                "logline": "Camila reviews a sealed request.",
                "core_conflict": "Trust the request or burn it.",
                "stakes": "Career and personal risk.",
                "tone": "quiet tension",
            },
            "shots": [
                {"shot_no": 1, "beat": "a", "camera": "a", "action": "a", "emotion": "a", "continuity_note": "a"},
                {"shot_no": 2, "beat": "b", "camera": "b", "action": "b", "emotion": "b", "continuity_note": "b"},
                {"shot_no": 3, "beat": "c", "camera": "c", "action": "c", "emotion": "c", "continuity_note": "c"},
                {"shot_no": 4, "beat": "d", "camera": "d", "action": "d", "emotion": "d", "continuity_note": "d"},
            ],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-ep-camila-v2-1",
                "render_lane": "character_canon_v2",
                "series_style_id": "camila_pilot_v1",
                "character_series_binding_id": "camila_pilot_binding_v1",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1"},
                    "panels": [{"id": "panel-1"}, {"id": "panel-2"}],
                }
            ],
            "pages": [],
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/panels/panel-1/queue-renders?candidate_count=3",
        ): {
            "queued_generation_count": 3,
            "render_assets": [
                {"id": "asset-1", "storage_path": "images/comics/panel-1-selected.png"}
            ],
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/panels/panel-1/assets/asset-1/select",
        ): {
            "id": "asset-1",
            "scene_panel_id": "panel-1",
            "storage_path": "images/comics/panel-1-selected.png",
            "is_selected": True,
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/panels/panel-2/queue-renders?candidate_count=3",
        ): {
            "queued_generation_count": 3,
            "render_assets": [
                {"id": "asset-2", "storage_path": "images/comics/panel-2-selected.png"}
            ],
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/panels/panel-2/assets/asset-2/select",
        ): {
            "id": "asset-2",
            "scene_panel_id": "panel-2",
            "storage_path": "images/comics/panel-2-selected.png",
            "is_selected": True,
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        if (method, url) == ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"):
            assert payload["render_lane"] == "character_canon_v2"
            assert payload["series_style_id"] == "camila_pilot_v1"
            assert payload["character_series_binding_id"] == "camila_pilot_binding_v1"
            assert payload["character_version_id"] == "charver_camila_duarte_still_v1"
        key = (method, url)
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_camila_v2_comic_pilot.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 0
    captured = capsys.readouterr()
    assert "episode_id: comic-ep-camila-v2-1" in captured.out
    assert "series_style_id: camila_pilot_v1" in captured.out
    assert "character_series_binding_id: camila_pilot_binding_v1" in captured.out
    assert "selected_render_asset_storage_path: images/comics/panel-1-selected.png" in captured.out
    assert "overall_success: true" in captured.out


def test_main_refuses_non_camila_ids(monkeypatch, capsys) -> None:
    module = _load_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_camila_v2_comic_pilot.py",
            "--character-id",
            "char_kaede_ren",
        ],
    )
    assert module.main() == 1
    captured = capsys.readouterr()
    assert "overall_success: false" in captured.out
    assert "failed_step: validate_camila_ids" in captured.out
    assert "Camila V2 pilot only supports character_id=char_camila_duarte" in captured.err
