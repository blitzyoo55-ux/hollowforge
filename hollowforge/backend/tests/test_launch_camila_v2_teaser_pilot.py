from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_camila_v2_teaser_pilot.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_camila_v2_teaser_pilot",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("series_style_id", "expected_motion_policy", "expected_preset_id"),
    [
        ("camila_pilot_v1", "static_hero", "sdxl_ipadapter_microanim_v2"),
        ("camila_motion_test_v1", "subtle_loop", "sdxl_ipadapter_microanim_subtle_loop_v1"),
    ],
)
def test_main_maps_execution_from_series_style_motion_policy(
    monkeypatch,
    capsys,
    series_style_id: str,
    expected_motion_policy: str,
    expected_preset_id: str,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"

    episode_payload = {
        "episode": {
            "id": "comic-ep-v2-teaser-1",
            "render_lane": "character_canon_v2",
            "series_style_id": series_style_id,
            "character_series_binding_id": "camila_pilot_binding_v1",
        },
        "scenes": [
            {
                "scene": {"id": "scene-1"},
                "panels": [
                    {
                        "id": "panel-1",
                        "render_assets": [
                            {
                                "id": "asset-selected-1",
                                "is_selected": True,
                                "storage_path": "images/comics/panel-selected-1.png",
                                "generation_id": "gen-selected-1",
                            }
                        ],
                    }
                ],
            }
        ],
        "pages": [],
    }

    requests: list[tuple[str, str]] = []

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        requests.append((method, url))
        if (method, url) == ("GET", f"{base_url}/api/v1/comic/episodes/comic-ep-v2-teaser-1"):
            return episode_payload
        if (method, url) == ("GET", f"{base_url}/api/v1/generations/gen-selected-1"):
            return {
                "id": "gen-selected-1",
                "status": "completed",
                "image_path": "images/comics/panel-selected-1.png",
            }
        if (
            method,
            url,
        ) == (
            "POST",
            f"{base_url}/api/v1/animation/presets/{expected_preset_id}/launch",
        ):
            assert payload["generation_id"] == "gen-selected-1"
            assert payload["episode_id"] == "comic-ep-v2-teaser-1"
            assert payload["scene_panel_id"] == "panel-1"
            assert payload["selected_render_asset_id"] == "asset-selected-1"
            return {
                "preset": {"id": expected_preset_id},
                "animation_job": {
                    "id": "anim-job-1",
                    "status": "completed",
                    "output_path": "videos/comics/teaser-1.mp4",
                },
                "animation_shot_id": "anim-shot-1",
            }
        if (method, url) == ("GET", f"{base_url}/api/v1/animation/jobs/anim-job-1"):
            return {
                "id": "anim-job-1",
                "status": "completed",
                "output_path": "videos/comics/teaser-1.mp4",
            }
        raise AssertionError(f"Unexpected request: {(method, url)!r} payload={payload!r}")

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_camila_v2_teaser_pilot.py",
            "--base-url",
            base_url,
            "--episode-id",
            "comic-ep-v2-teaser-1",
        ],
    )

    assert module.main() == 0
    captured = capsys.readouterr()
    assert f"series_style_id: {series_style_id}" in captured.out
    assert "character_series_binding_id: camila_pilot_binding_v1" in captured.out
    assert "selected_render_asset_storage_path: images/comics/panel-selected-1.png" in captured.out
    assert f"teaser_motion_policy: {expected_motion_policy}" in captured.out
    assert f"preset_id: {expected_preset_id}" in captured.out
    assert "animation_job_id: anim-job-1" in captured.out
    assert "animation_shot_id: anim-shot-1" in captured.out
    assert "overall_success: true" in captured.out
    assert (
        "POST",
        f"{base_url}/api/v1/animation/presets/{expected_preset_id}/launch",
    ) in requests


def test_main_requires_completed_selected_render_from_v2_episode(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        if (method, url) == ("GET", f"{base_url}/api/v1/comic/episodes/comic-ep-v2-teaser-2"):
            return {
                "episode": {
                    "id": "comic-ep-v2-teaser-2",
                    "render_lane": "character_canon_v2",
                    "series_style_id": "camila_pilot_v1",
                    "character_series_binding_id": "camila_pilot_binding_v1",
                },
                "scenes": [
                    {
                        "scene": {"id": "scene-2"},
                        "panels": [
                            {
                                "id": "panel-2",
                                "render_assets": [
                                    {
                                        "id": "asset-selected-2",
                                        "is_selected": True,
                                        "storage_path": "images/comics/panel-selected-2.png",
                                        "generation_id": "gen-selected-2",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "pages": [],
            }
        if (method, url) == ("GET", f"{base_url}/api/v1/generations/gen-selected-2"):
            return {
                "id": "gen-selected-2",
                "status": "processing",
                "image_path": None,
            }
        raise AssertionError(f"Unexpected request: {(method, url)!r} payload={payload!r}")

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_camila_v2_teaser_pilot.py",
            "--base-url",
            base_url,
            "--episode-id",
            "comic-ep-v2-teaser-2",
        ],
    )
    assert module.main() == 1
    captured = capsys.readouterr()
    assert "overall_success: false" in captured.out
    assert "failed_step: require_completed_selected_render" in captured.out
    assert "requires a completed selected render generation" in captured.err
