from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_comic_remote_render_smoke.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_remote_render_smoke",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_uses_extended_default_remote_poll_budget(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"
    queue_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: (
            {
                "id": "char_camila_duarte",
                "slug": "camila-duarte",
                "name": "Camila Duarte",
            },
            {
                "id": "charver_camila_duarte_still_v1",
                "character_id": "char_camila_duarte",
                "version_name": "Still v1",
            },
            [{"id": "char_camila_duarte"}],
            [{"id": "charver_camila_duarte_still_v1"}],
        ),
    )

    monkeypatch.setattr(
        module,
        "_queue_and_select_remote_panel_asset",
        lambda **kwargs: queue_calls.append(kwargs) or (
            {
                "requested_count": 3,
                "queued_generation_count": 3,
                "execution_mode": "remote_worker",
                "remote_job_count": 3,
                "render_assets": [
                    {
                        "id": "asset-1",
                        "storage_path": "images/panel-1-a.png",
                        "is_selected": False,
                    }
                ],
            },
            {
                "id": "asset-1",
                "scene_panel_id": "panel-1",
                "asset_role": "selected",
                "storage_path": "images/panel-1-a.png",
                "is_selected": True,
            },
            [
                {
                    "id": "job-1",
                    "render_asset_id": "asset-1",
                    "status": "completed",
                    "output_path": "images/panel-1-a.png",
                }
            ],
        ),
    )

    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "Camila Duarte tests the first remote still-render lane.",
            "lane": "adult_nsfw",
            "approval_token": "approval-token",
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-remote-1",
                "character_id": "char_camila_duarte",
                "character_version_id": "charver_camila_duarte_still_v1",
                "title": "Comic Remote Render Smoke",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [{"id": "panel-1", "panel_no": 1}],
                }
            ],
            "pages": [],
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_remote_render_smoke.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    assert len(queue_calls) == 1
    assert queue_calls[0]["poll_attempts"] == 360
    assert queue_calls[0]["poll_sec"] == 2.0
    assert "queue_renders_success: true" in captured.out
    assert "overall_success: true" in captured.out
