from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_comic_one_panel_smoke.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_one_panel_smoke",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_prints_success_markers_for_one_panel_smoke(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"
    local_queue_calls: list[dict[str, object]] = []
    dry_run_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        module.one_panel_verification.comic_smoke,
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

    async def fake_create_episode(**_: object) -> dict[str, object]:
        return {
            "episode": {
                "id": "comic-smoke-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
                "title": "Comic One Panel Smoke",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [{"id": "panel-1", "panel_no": 1}],
                }
            ],
            "pages": [],
        }

    monkeypatch.setattr(
        module.one_panel_verification,
        "_create_one_panel_verification_episode",
        fake_create_episode,
    )
    monkeypatch.setattr(
        module.one_panel_verification.comic_smoke,
        "_queue_and_select_panel_asset",
        lambda **kwargs: local_queue_calls.append(kwargs) or (
            {
                "requested_count": 1,
                "queued_generation_count": 1,
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
            True,
        ),
    )

    responses = {
        ("POST", f"{base_url}/api/v1/comic/panels/panel-1/dialogues/generate"): {
            "generated_count": 1,
            "dialogues": [{"id": "dlg-1"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-smoke-1/pages/assemble"): {
            "episode_id": "comic-smoke-1",
            "layout_template_id": "jp_2x2_v1",
            "pages": [{"id": "page-1", "page_no": 1}],
            "teaser_handoff_manifest_path": "comics/manifests/comic-smoke-1_teaser.json",
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-smoke-1/pages/export"): {
            "episode_id": "comic-smoke-1",
            "layout_template_id": "jp_2x2_v1",
            "pages": [{"id": "page-1", "page_no": 1, "export_state": "exported"}],
            "export_zip_path": "comics/exports/comic-smoke-1_handoff.zip",
            "teaser_handoff_manifest_path": "comics/manifests/comic-smoke-1_teaser.json",
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(
        module.one_panel_verification.comic_smoke,
        "_request_json",
        fake_request_json,
    )
    monkeypatch.setattr(
        module.one_panel_verification,
        "_run_production_dry_run",
        lambda **kwargs: dry_run_calls.append(kwargs) or {
            "dry_run_success": True,
            "layered_package_verified": True,
            "layered_manifest_path": "comics/exports/comic-smoke-1/manifest.json",
            "handoff_validation_path": "comics/exports/comic-smoke-1/handoff_validation.json",
            "hard_block_count": 0,
            "report_path": "comics/reports/comic-smoke-1_dry_run.json",
            "page_count": 1,
            "selected_panel_asset_count": 1,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_one_panel_smoke.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    assert len(local_queue_calls) == 1
    assert local_queue_calls[0]["panel_id"] == "panel-1"
    assert local_queue_calls[0]["candidate_count"] == 1
    assert local_queue_calls[0]["poll_attempts"] == 12
    assert local_queue_calls[0]["poll_sec"] == 0.5
    assert local_queue_calls[0]["allow_synthetic_asset_fallback"] is True
    assert len(dry_run_calls) == 1
    assert dry_run_calls[0]["allow_placeholder_assets"] is True
    assert "execution_mode: local_preview" in captured.out
    assert "queue_renders_success: true" in captured.out
    assert "dry_run_success: true" in captured.out
    assert "overall_success: true" in captured.out
