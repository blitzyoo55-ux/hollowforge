from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_comic_one_panel_verification.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_one_panel_verification",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_prints_success_markers_for_one_panel_verification(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"
    remote_queue_calls: list[dict[str, object]] = []

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

    async def fake_create_episode(**_: object) -> dict[str, object]:
        return {
            "episode": {
                "id": "comic-verify-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
                "title": "Comic One Panel Verification",
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
        module,
        "_create_one_panel_verification_episode",
        fake_create_episode,
    )
    monkeypatch.setattr(
        module.remote_smoke,
        "_queue_and_select_remote_panel_asset",
        lambda **kwargs: remote_queue_calls.append(kwargs) or (
            {
                "requested_count": 1,
                "queued_generation_count": 1,
                "execution_mode": "remote_worker",
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
        ("POST", f"{base_url}/api/v1/comic/panels/panel-1/dialogues/generate"): {
            "generated_count": 2,
            "dialogues": [{"id": "dlg-1"}, {"id": "dlg-2"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-verify-1/pages/assemble"): {
            "episode_id": "comic-verify-1",
            "layout_template_id": "jp_2x2_v1",
            "pages": [{"id": "page-1", "page_no": 1}],
            "teaser_handoff_manifest_path": "comics/manifests/comic-verify-1_teaser.json",
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-verify-1/pages/export"): {
            "episode_id": "comic-verify-1",
            "layout_template_id": "jp_2x2_v1",
            "pages": [{"id": "page-1", "page_no": 1, "export_state": "exported"}],
            "export_zip_path": "comics/exports/comic-verify-1_handoff.zip",
            "teaser_handoff_manifest_path": "comics/manifests/comic-verify-1_teaser.json",
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(
        module,
        "_run_production_dry_run",
        lambda **_: {
            "dry_run_success": True,
            "layered_package_verified": True,
            "layered_manifest_path": "comics/exports/comic-verify-1/manifest.json",
            "handoff_validation_path": "comics/exports/comic-verify-1/handoff_validation.json",
            "hard_block_count": 0,
            "report_path": "comics/reports/comic-verify-1_dry_run.json",
            "page_count": 1,
            "selected_panel_asset_count": 1,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_one_panel_verification.py",
            "--base-url",
            base_url,
        ],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    assert len(remote_queue_calls) == 1
    assert remote_queue_calls[0]["candidate_count"] == 1
    assert remote_queue_calls[0]["poll_attempts"] == 360
    assert remote_queue_calls[0]["poll_sec"] == 2.0
    assert "execution_mode: remote_worker" in captured.out
    assert "episode_create_success: true" in captured.out
    assert "episode_id: comic-verify-1" in captured.out
    assert "queue_renders_success: true" in captured.out
    assert "materialized_asset_count: 1" in captured.out
    assert "selected_panel_asset_count: 1" in captured.out
    assert "dialogues_success: true" in captured.out
    assert "assemble_success: true" in captured.out
    assert "export_success: true" in captured.out
    assert "dry_run_success: true" in captured.out
    assert "layered_package_verified: true" in captured.out
    assert "layered_manifest_path: comics/exports/comic-verify-1/manifest.json" in captured.out
    assert (
        "handoff_validation_path: comics/exports/comic-verify-1/handoff_validation.json"
        in captured.out
    )
    assert "hard_block_count: 0" in captured.out
    assert "overall_success: true" in captured.out


def test_main_rejects_remote_backend_urls_for_local_verification(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_one_panel_verification.py",
            "--base-url",
            "https://remote.example.com",
        ],
    )

    assert module.main() == 1

    captured = capsys.readouterr()
    assert "episode_create_success: false" in captured.out
    assert "failed_step: bootstrap" in captured.out
    assert "one-panel verification only supports local backend URLs" in captured.out


def test_main_supports_local_preview_execution_mode(
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

    async def fake_create_episode(**_: object) -> dict[str, object]:
        return {
            "episode": {
                "id": "comic-verify-local-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
                "title": "Comic One Panel Verification",
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
        module,
        "_create_one_panel_verification_episode",
        fake_create_episode,
    )

    local_queue_calls: list[str] = []
    monkeypatch.setattr(
        module.comic_smoke,
        "_queue_and_select_panel_asset",
        lambda **kwargs: local_queue_calls.append(kwargs["panel_id"]) or (
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
            False,
        ),
    )

    responses = {
        ("POST", f"{base_url}/api/v1/comic/panels/panel-1/dialogues/generate"): {
            "generated_count": 1,
            "dialogues": [{"id": "dlg-1"}],
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-verify-local-1/pages/assemble"): {
            "episode_id": "comic-verify-local-1",
            "layout_template_id": "jp_2x2_v1",
            "pages": [{"id": "page-1", "page_no": 1}],
            "teaser_handoff_manifest_path": "comics/manifests/comic-verify-local-1_teaser.json",
        },
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-verify-local-1/pages/export"): {
            "episode_id": "comic-verify-local-1",
            "layout_template_id": "jp_2x2_v1",
            "pages": [{"id": "page-1", "page_no": 1, "export_state": "exported"}],
            "export_zip_path": "comics/exports/comic-verify-local-1_handoff.zip",
            "teaser_handoff_manifest_path": "comics/manifests/comic-verify-local-1_teaser.json",
        },
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module.comic_smoke, "_request_json", fake_request_json)
    monkeypatch.setattr(
        module,
        "_run_production_dry_run",
        lambda **_: {
            "dry_run_success": True,
            "layered_package_verified": True,
            "layered_manifest_path": "comics/exports/comic-verify-local-1/manifest.json",
            "handoff_validation_path": "comics/exports/comic-verify-local-1/handoff_validation.json",
            "hard_block_count": 0,
            "report_path": "comics/reports/comic-verify-local-1_dry_run.json",
            "page_count": 1,
            "selected_panel_asset_count": 1,
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_one_panel_verification.py",
            "--base-url",
            base_url,
            "--execution-mode",
            "local_preview",
        ],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    assert "execution_mode: local_preview" in captured.out
    assert "queue_renders_success: true" in captured.out
    assert "materialized_asset_count: 1" in captured.out
    assert local_queue_calls == ["panel-1"]


def test_run_production_dry_run_uses_layered_handoff_contract(
    monkeypatch,
) -> None:
    module = _load_module()

    episode_detail = {
        "episode": {"id": "comic-verify-1"},
        "scenes": [
            {
                "scene": {"id": "scene-1", "scene_no": 1},
                "panels": [{"id": "panel-1", "panel_no": 1}],
            }
        ],
    }
    assembly_detail = {
        "episode_id": "comic-verify-1",
        "teaser_handoff_manifest_path": "comics/manifests/comic-verify-1_teaser.json",
    }
    export_detail = {
        "episode_id": "comic-verify-1",
        "export_zip_path": "comics/exports/comic-verify-1_handoff.zip",
        "pages": [{"id": "page-1", "page_no": 1, "export_state": "exported"}],
        "layered_manifest_path": "comics/exports/comic-verify-1/manifest.json",
        "handoff_validation_path": "comics/exports/comic-verify-1/handoff_validation.json",
        "hard_block_count": 0,
    }
    layered_handoff_summary = {
        "layered_manifest_path": "comics/exports/comic-verify-1/manifest.json",
        "handoff_validation_path": "comics/exports/comic-verify-1/handoff_validation.json",
        "hard_block_count": 0,
    }
    selected_panel_assets = [{"id": "asset-1", "storage_path": "images/panel-1-a.png"}]
    validate_export_zip_calls: list[tuple[str, dict[str, object]]] = []
    write_report_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        module.comic_dry_run,
        "_ensure_exported_episode",
        lambda **_: (episode_detail, assembly_detail, export_detail),
    )
    monkeypatch.setattr(
        module.comic_dry_run,
        "_extract_selected_panel_assets",
        lambda detail, **kwargs: selected_panel_assets if detail is assembly_detail else [],
    )
    monkeypatch.setattr(
        module.comic_dry_run,
        "_extract_layered_handoff_summary",
        lambda detail: layered_handoff_summary if detail is export_detail else {},
    )
    monkeypatch.setattr(
        module.comic_dry_run,
        "_validate_export_zip",
        lambda export_zip_path, detail, **kwargs: validate_export_zip_calls.append(
            (export_zip_path, detail)
        ),
    )
    monkeypatch.setattr(
        module.comic_dry_run,
        "_write_report",
        lambda **kwargs: write_report_calls.append(kwargs) or Path("/tmp/comic-verify-report.json"),
    )
    monkeypatch.setattr(
        module.comic_dry_run,
        "_relative_data_path",
        lambda path: "comics/reports/comic-verify-report.json",
    )
    monkeypatch.setattr(
        module.comic_dry_run,
        "_extract_panel_ids",
        lambda detail: ["panel-1"] if detail is episode_detail else [],
    )

    result = module._run_production_dry_run(
        base_url="http://127.0.0.1:8000",
        episode_id="comic-verify-1",
        layout_template_id="jp_2x2_v1",
        manuscript_profile_id="jp_manga_rightbound_v1",
    )

    assert validate_export_zip_calls == [
        ("comics/exports/comic-verify-1_handoff.zip", export_detail)
    ]
    assert len(write_report_calls) == 1
    assert write_report_calls[0]["layered_handoff_summary"] == layered_handoff_summary
    assert result == {
        "dry_run_success": True,
        "layered_package_verified": True,
        "panel_count": 1,
        "selected_panel_asset_count": 1,
        "page_count": 1,
        "export_zip_path": "comics/exports/comic-verify-1_handoff.zip",
        "layered_manifest_path": "comics/exports/comic-verify-1/manifest.json",
        "handoff_validation_path": "comics/exports/comic-verify-1/handoff_validation.json",
        "hard_block_count": 0,
        "report_path": "comics/reports/comic-verify-report.json",
    }
