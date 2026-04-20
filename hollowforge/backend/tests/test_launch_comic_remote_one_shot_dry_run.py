from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_comic_remote_one_shot_dry_run.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_remote_one_shot_dry_run",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_prints_success_markers_for_remote_one_shot_dry_run(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"

    monkeypatch.setattr(
        module.comic_smoke,
        "_resolve_character_and_version",
        lambda **_: (
            {
                "id": "char_kaede_ren",
                "slug": "kaede-ren",
                "name": "Kaede Ren",
            },
            {
                "id": "charver_kaede_ren_still_v1",
                "character_id": "char_kaede_ren",
                "version_name": "Still v1",
            },
            [{"id": "char_kaede_ren"}],
            [{"id": "charver_kaede_ren_still_v1"}],
        ),
    )

    responses = {
        ("POST", f"{base_url}/api/v1/tools/story-planner/plan"): {
            "story_prompt": "remote one-shot story",
            "lane": "adult_nsfw",
            "approval_token": "a" * 64,
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/import-story-plan"): {
            "episode": {
                "id": "comic-remote-oneshot-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [
                        {"id": "panel-1", "panel_no": 1},
                        {"id": "panel-2", "panel_no": 2},
                        {"id": "panel-3", "panel_no": 3},
                        {"id": "panel-4", "panel_no": 4},
                    ],
                }
            ],
            "pages": [],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-1/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-1a"}, {"id": "dlg-1b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-2/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-2a"}, {"id": "dlg-2b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-3/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-3a"}, {"id": "dlg-3b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/panels/panel-4/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-4a"}, {"id": "dlg-4b"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-remote-oneshot-1/pages/assemble"): {
            "episode_id": "comic-remote-oneshot-1",
            "pages": [{"id": "page-1", "page_no": 1}],
            "teaser_handoff_manifest_path": "comics/manifests/comic-remote-oneshot-1_teaser.json",
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-remote-oneshot-1/pages/export"): {
            "episode_id": "comic-remote-oneshot-1",
            "pages": [{"id": "page-1", "page_no": 1, "export_state": "exported"}],
            "export_zip_path": "comics/exports/comic-remote-oneshot-1_handoff.zip",
            "teaser_handoff_manifest_path": "comics/manifests/comic-remote-oneshot-1_teaser.json",
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)

    queued_panels: list[str] = []

    def fake_queue_and_select_remote_panel_asset(**kwargs):  # type: ignore[no-untyped-def]
        panel_id = kwargs["panel_id"]
        queued_panels.append(panel_id)
        return (
            {
                "requested_count": 3,
                "queued_generation_count": 3,
                "execution_mode": "remote_worker",
                "render_assets": [
                    {
                        "id": f"asset-{panel_id}",
                        "storage_path": f"outputs/{panel_id}.png",
                        "is_selected": False,
                    }
                ],
            },
            {
                "id": f"asset-{panel_id}",
                "scene_panel_id": panel_id,
                "asset_role": "selected",
                "storage_path": f"outputs/{panel_id}.png",
                "is_selected": True,
            },
            [
                {
                    "id": f"job-{panel_id}",
                    "render_asset_id": f"asset-{panel_id}",
                    "status": "completed",
                    "output_path": f"outputs/{panel_id}.png",
                }
            ],
        )

    monkeypatch.setattr(
        module.remote_smoke,
        "_queue_and_select_remote_panel_asset",
        fake_queue_and_select_remote_panel_asset,
    )
    monkeypatch.setattr(
        module,
        "_run_production_dry_run",
        lambda **_: {
            "dry_run_success": True,
            "report_path": "comics/reports/comic-remote-oneshot-1_dry_run.json",
            "page_count": 1,
            "selected_panel_asset_count": 4,
            "export_zip_path": "comics/exports/comic-remote-oneshot-1_handoff.zip",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_remote_one_shot_dry_run.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    assert "execution_mode: remote_worker" in captured.out
    assert "episode_create_success: true" in captured.out
    assert "episode_id: comic-remote-oneshot-1" in captured.out
    assert "queue_renders_success: true" in captured.out
    assert "selected_panel_asset_count: 4" in captured.out
    assert "dialogues_success: true" in captured.out
    assert "assemble_success: true" in captured.out
    assert "export_success: true" in captured.out
    assert "dry_run_success: true" in captured.out
    assert "overall_success: true" in captured.out
    assert queued_panels == ["panel-1", "panel-2", "panel-3", "panel-4"]


def test_main_rejects_remote_backend_urls_for_remote_one_shot_dry_run(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_remote_one_shot_dry_run.py",
            "--base-url",
            "https://remote.example.com",
        ],
    )

    assert module.main() == 1

    captured = capsys.readouterr()
    assert "episode_create_success: false" in captured.out
    assert "failed_step: bootstrap" in captured.out
    assert "remote one-shot dry-run only supports local backend URLs" in captured.out
