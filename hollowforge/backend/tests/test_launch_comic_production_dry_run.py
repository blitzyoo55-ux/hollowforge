from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_comic_production_dry_run.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_production_dry_run",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_responses(base_url: str) -> dict[tuple[str, str], object]:
    return {
        ("GET", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1"): {
            "episode": {
                "id": "comic-ep-prod-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [
                        {"id": "panel-1", "panel_no": 1},
                        {"id": "panel-2", "panel_no": 2},
                    ],
                }
            ],
            "pages": [],
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/pages/assemble",
        ): {
            "episode_id": "comic-ep-prod-1",
            "layout_template_id": "jp_2x2_v1",
            "manuscript_profile": {"id": "jp_manga_rightbound_v1"},
            "pages": [
                {
                    "id": "page-1",
                    "page_no": 1,
                    "preview_path": "comics/previews/comic-ep-prod-1_page_01.png",
                    "export_state": "preview_ready",
                }
            ],
            "export_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_pages.json",
            "dialogue_json_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_dialogues.json",
            "panel_asset_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_panel_assets.json",
            "page_assembly_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_pages.json",
            "teaser_handoff_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_teaser_handoff.json",
            "manuscript_profile_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_manuscript_profile.json",
            "handoff_readme_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_handoff_readme.md",
            "production_checklist_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_production_checklist.json",
            "layered_manifest_path": "comics/exports/comic-ep-prod-1_jp_2x2_v1_layered/manifest.json",
            "handoff_validation_path": "comics/exports/comic-ep-prod-1_jp_2x2_v1_layered/handoff_validation.json",
            "hard_block_count": 0,
        },
        (
            "POST",
            f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/pages/export",
        ): {
            "episode_id": "comic-ep-prod-1",
            "layout_template_id": "jp_2x2_v1",
            "manuscript_profile": {"id": "jp_manga_rightbound_v1"},
            "pages": [
                {
                    "id": "page-1",
                    "page_no": 1,
                    "preview_path": "comics/previews/comic-ep-prod-1_page_01.png",
                    "export_state": "exported",
                }
            ],
            "export_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_pages.json",
            "dialogue_json_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_dialogues.json",
            "panel_asset_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_panel_assets.json",
            "page_assembly_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_pages.json",
            "teaser_handoff_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_teaser_handoff.json",
            "manuscript_profile_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_manuscript_profile.json",
            "handoff_readme_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_handoff_readme.md",
            "production_checklist_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_production_checklist.json",
            "export_zip_path": "comics/exports/comic-ep-prod-1_jp_2x2_v1_handoff.zip",
            "layered_manifest_path": "comics/exports/comic-ep-prod-1_jp_2x2_v1_layered/manifest.json",
            "handoff_validation_path": "comics/exports/comic-ep-prod-1_jp_2x2_v1_layered/handoff_validation.json",
            "hard_block_count": 0,
        },
        ("GET", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/detail"): {
            "episode": {
                "id": "comic-ep-prod-1",
                "character_id": "char_kaede_ren",
                "character_version_id": "charver_kaede_ren_still_v1",
            },
            "scenes": [
                {
                    "scene": {"id": "scene-1", "scene_no": 1},
                    "panels": [
                        {"id": "panel-1", "panel_no": 1},
                        {"id": "panel-2", "panel_no": 2},
                    ],
                }
            ],
            "pages": [
                {"id": "page-1", "page_no": 1, "export_state": "exported"}
            ],
        },
    }


def test_main_prints_success_markers_and_writes_report(
    monkeypatch,
    capsys,
    tmp_path,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"
    responses = _build_responses(base_url)

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(module.settings, "DATA_DIR", tmp_path / "data")

    teaser_manifest_path = (
        module.settings.DATA_DIR
        / "comics"
        / "manifests"
        / "comic-ep-prod-1_jp_2x2_v1_teaser_handoff.json"
    )
    teaser_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    teaser_manifest_path.write_text(
        json.dumps(
            {
                "episode_id": "comic-ep-prod-1",
                "selected_panel_assets": [
                    {
                        "panel_id": "panel-1",
                        "asset_id": "asset-1",
                        "storage_path": "comics/previews/comic-ep-prod-1_panel-1.png",
                    },
                    {
                        "panel_id": "panel-2",
                        "asset_id": "asset-2",
                        "storage_path": "comics/previews/comic-ep-prod-1_panel-2.png",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    export_zip_path = (
        module.settings.DATA_DIR
        / "comics"
        / "exports"
        / "comic-ep-prod-1_jp_2x2_v1_handoff.zip"
    )
    export_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(export_zip_path, mode="w") as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("handoff_validation.json", b"{}")
        archive.writestr("pages/page_001/frame_layer.json", b"{}")
        archive.writestr("pages/page_001/balloon_layer.json", b"{}")
        archive.writestr("pages/page_001/text_draft_layer.json", b"{}")
        archive.writestr("comics/previews/comic-ep-prod-1_panel-1.png", b"panel-1")
        archive.writestr("comics/previews/comic-ep-prod-1_panel-2.png", b"panel-2")

    layered_manifest_path = (
        module.settings.DATA_DIR
        / "comics"
        / "exports"
        / "comic-ep-prod-1_jp_2x2_v1_layered"
        / "manifest.json"
    )
    layered_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    layered_manifest_path.write_text('{"episode_id":"comic-ep-prod-1"}', encoding="utf-8")

    handoff_validation_path = layered_manifest_path.with_name("handoff_validation.json")
    handoff_validation_path.write_text('{"hard_blocks":[]}', encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_production_dry_run.py",
            "--base-url",
            base_url,
            "--episode-id",
            "comic-ep-prod-1",
            "--layout-template-id",
            "jp_2x2_v1",
            "--manuscript-profile-id",
            "jp_manga_rightbound_v1",
        ],
    )

    assert module.main() == 0

    captured = capsys.readouterr()
    assert "dry_run_success: true" in captured.out
    assert "episode_id: comic-ep-prod-1" in captured.out
    assert "panel_count: 2" in captured.out
    assert "selected_panel_asset_count: 2" in captured.out
    assert "page_count: 1" in captured.out
    assert "manuscript_profile_id: jp_manga_rightbound_v1" in captured.out
    assert (
        "layered_manifest_path: comics/exports/comic-ep-prod-1_jp_2x2_v1_layered/manifest.json"
        in captured.out
    )
    assert (
        "handoff_validation_path: comics/exports/comic-ep-prod-1_jp_2x2_v1_layered/handoff_validation.json"
        in captured.out
    )
    assert "hard_block_count: 0" in captured.out
    assert "report_path: comics/reports/" in captured.out

    report_path = (
        module.settings.DATA_DIR
        / "comics"
        / "reports"
        / "comic-ep-prod-1_jp_2x2_v1_jp_manga_rightbound_v1_dry_run.json"
    )
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["episode_id"] == "comic-ep-prod-1"
    assert report["export_zip_path"].endswith(".zip")
    assert report["layered_manifest_path"].endswith("/manifest.json")
    assert report["handoff_validation_path"].endswith("/handoff_validation.json")
    assert report["hard_block_count"] == 0
    assert report["teaser_handoff_manifest"]["selected_panel_assets"][0]["storage_path"].startswith(
        "comics/previews/"
    )


def test_main_rejects_hard_blocks_in_handoff_validation(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"
    responses = _build_responses(base_url)
    responses[("POST", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/pages/export")] = {
        **responses[("POST", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/pages/export")],
        "hard_block_count": 2,
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(module.settings, "DATA_DIR", tmp_path / "data")

    teaser_manifest_path = (
        module.settings.DATA_DIR
        / "comics"
        / "manifests"
        / "comic-ep-prod-1_jp_2x2_v1_teaser_handoff.json"
    )
    teaser_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    teaser_manifest_path.write_text(
        json.dumps(
            {
                "episode_id": "comic-ep-prod-1",
                "selected_panel_assets": [
                    {
                        "panel_id": "panel-1",
                        "asset_id": "asset-1",
                        "storage_path": "comics/previews/comic-ep-prod-1_panel-1.png",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    export_zip_path = (
        module.settings.DATA_DIR
        / "comics"
        / "exports"
        / "comic-ep-prod-1_jp_2x2_v1_handoff.zip"
    )
    export_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(export_zip_path, mode="w") as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("handoff_validation.json", b"{}")
        archive.writestr("pages/page_001/frame_layer.json", b"{}")
        archive.writestr("pages/page_001/balloon_layer.json", b"{}")
        archive.writestr("pages/page_001/text_draft_layer.json", b"{}")

    layered_dir = (
        module.settings.DATA_DIR
        / "comics"
        / "exports"
        / "comic-ep-prod-1_jp_2x2_v1_layered"
    )
    layered_dir.mkdir(parents=True, exist_ok=True)
    (layered_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (layered_dir / "handoff_validation.json").write_text(
        '{"hard_blocks":[{"code":"missing_text"}]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_production_dry_run.py",
            "--base-url",
            base_url,
            "--episode-id",
            "comic-ep-prod-1",
        ],
    )

    try:
        module.main()
    except RuntimeError as exc:
        assert "hard_block_count" in str(exc)
    else:
        raise AssertionError("Expected hard block rejection")


def test_main_rejects_export_zip_missing_layer_for_later_page(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"
    responses = _build_responses(base_url)
    two_page_export = {
        **responses[("POST", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/pages/export")],
        "pages": [
            {
                "id": "page-1",
                "page_no": 1,
                "preview_path": "comics/previews/comic-ep-prod-1_page_01.png",
                "export_state": "exported",
            },
            {
                "id": "page-2",
                "page_no": 2,
                "preview_path": "comics/previews/comic-ep-prod-1_page_02.png",
                "export_state": "exported",
            },
        ],
    }
    responses[("POST", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/pages/export")] = (
        two_page_export
    )

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        return responses[key]

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(module.settings, "DATA_DIR", tmp_path / "data")

    teaser_manifest_path = (
        module.settings.DATA_DIR
        / "comics"
        / "manifests"
        / "comic-ep-prod-1_jp_2x2_v1_teaser_handoff.json"
    )
    teaser_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    teaser_manifest_path.write_text(
        json.dumps(
            {
                "episode_id": "comic-ep-prod-1",
                "selected_panel_assets": [
                    {
                        "panel_id": "panel-1",
                        "asset_id": "asset-1",
                        "storage_path": "comics/previews/comic-ep-prod-1_panel-1.png",
                    },
                    {
                        "panel_id": "panel-2",
                        "asset_id": "asset-2",
                        "storage_path": "comics/previews/comic-ep-prod-1_panel-2.png",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    export_zip_path = (
        module.settings.DATA_DIR
        / "comics"
        / "exports"
        / "comic-ep-prod-1_jp_2x2_v1_handoff.zip"
    )
    export_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(export_zip_path, mode="w") as archive:
        archive.writestr("manifest.json", b"{}")
        archive.writestr("handoff_validation.json", b"{}")
        archive.writestr("pages/page_001/frame_layer.json", b"{}")
        archive.writestr("pages/page_001/balloon_layer.json", b"{}")
        archive.writestr("pages/page_001/text_draft_layer.json", b"{}")
        archive.writestr("pages/page_002/frame_layer.json", b"{}")
        archive.writestr("pages/page_002/text_draft_layer.json", b"{}")

    layered_dir = (
        module.settings.DATA_DIR
        / "comics"
        / "exports"
        / "comic-ep-prod-1_jp_2x2_v1_layered"
    )
    layered_dir.mkdir(parents=True, exist_ok=True)
    (layered_dir / "manifest.json").write_text("{}", encoding="utf-8")
    (layered_dir / "handoff_validation.json").write_text('{"hard_blocks":[]}', encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_production_dry_run.py",
            "--base-url",
            base_url,
            "--episode-id",
            "comic-ep-prod-1",
        ],
    )

    try:
        module.main()
    except RuntimeError as exc:
        assert "page_002/balloon_layer.json" in str(exc)
    else:
        raise AssertionError("Expected missing layered page artifact rejection")


def test_main_refuses_smoke_placeholder_assets(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    base_url = "http://127.0.0.1:8000"
    responses = _build_responses(base_url)
    responses[
        ("POST", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/pages/export")
    ] = {
        **responses[("POST", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/pages/export")],
        "teaser_handoff_manifest_path": "comics/manifests/comic-ep-prod-1_jp_2x2_v1_teaser_handoff.json",
    }

    def fake_request_json(method: str, url: str, payload=None):  # type: ignore[no-untyped-def]
        key = (method, url.split("?", 1)[0])
        if key not in responses:
            raise AssertionError(f"Unexpected request: {key!r} payload={payload!r}")
        if key == ("GET", f"{base_url}/api/v1/comic/episodes/comic-ep-prod-1/detail"):
            return responses[key]
        return responses[key]

    monkeypatch.setattr(module, "_request_json", fake_request_json)
    monkeypatch.setattr(module.settings, "DATA_DIR", tmp_path / "data")

    teaser_manifest_path = module.settings.DATA_DIR / "comics/manifests/comic-ep-prod-1_jp_2x2_v1_teaser_handoff.json"
    teaser_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    teaser_manifest_path.write_text(
        json.dumps(
            {
                "episode_id": "comic-ep-prod-1",
                "selected_panel_assets": [
                    {
                        "panel_id": "panel-1",
                        "asset_id": "asset-1",
                        "storage_path": "comics/previews/smoke_assets/panel-1_asset-1.png",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_production_dry_run.py",
            "--base-url",
            base_url,
            "--episode-id",
            "comic-ep-prod-1",
            "--layout-template-id",
            "jp_2x2_v1",
            "--manuscript-profile-id",
            "jp_manga_rightbound_v1",
        ],
    )

    try:
        module.main()
    except RuntimeError as exc:
        assert "smoke_assets" in str(exc)
    else:
        raise AssertionError("Expected smoke placeholder asset rejection")
