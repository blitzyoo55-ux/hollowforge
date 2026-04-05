from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REQUIRED_SUMMARY_MARKERS = (
    "episode_id:",
    "scene_panel_id:",
    "selected_render_asset_id:",
    "generation_id:",
    "preset_id:",
    "animation_job_id:",
    "output_path:",
    "teaser_success:",
    "overall_success:",
)


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "launch_comic_teaser_animation_smoke.py"
    )
    spec = importlib.util.spec_from_file_location(
        "launch_comic_teaser_animation_smoke",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_required_summary_markers(output: str) -> None:
    for marker in REQUIRED_SUMMARY_MARKERS:
        assert marker in output


def _assert_bounded_failure_invariants(output: str) -> None:
    assert "teaser_success: false" in output
    assert "animation_job_id: " in output
    assert "output_path: " in output


def test_is_placeholder_asset_rejects_only_the_exact_smoke_assets_prefix() -> None:
    module = _load_module()

    assert module._is_placeholder_asset("comics/previews/smoke_assets/panel-01.png") is True
    assert (
        module._is_placeholder_asset("comics/previews/smoke_assets_backup/panel-01.png")
        is False
    )


def test_main_rejects_remote_backend_urls_for_comic_teaser_smoke(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_teaser_animation_smoke.py",
            "--base-url",
            "https://remote.example.com",
        ],
    )
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "overall_success: false" in captured.out
    assert "failed_step: bootstrap" in captured.out
    assert "comic teaser animation smoke only supports local backend URLs" in captured.err


def test_main_invalid_cli_input_still_prints_summary_markers(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_teaser_animation_smoke.py",
            "--panel-index",
            "not-an-int",
        ],
    )
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "failed_step: bootstrap" in captured.out
    assert "invalid int value" in captured.err


def test_main_rejects_placeholder_selected_asset(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_resolve_source_asset",
        lambda **_: {
            "episode_id": "episode-1",
            "scene_panel_id": "panel-1",
            "id": "asset-1",
            "generation_id": "gen-1",
            "storage_path": "comics/previews/smoke_assets/panel-01.png",
        },
    )
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "episode_id: episode-1" in captured.out
    assert "scene_panel_id: panel-1" in captured.out
    assert "selected_render_asset_id: asset-1" in captured.out
    assert "generation_id: gen-1" in captured.out
    assert "failed_step: validate_source_asset" in captured.out
    assert "placeholder selected asset is not allowed" in captured.err


def test_main_rejects_missing_selected_asset_storage_path(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_resolve_source_asset",
        lambda **_: {
            "episode_id": "episode-2",
            "scene_panel_id": "panel-2",
            "selected_render_asset_id": "asset-2",
            "generation_id": "gen-2",
        },
    )
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "selected_render_asset_id: asset-2" in captured.out
    assert "failed_step: validate_source_asset" in captured.out
    assert "selected asset storage_path is missing" in captured.err


def test_main_rejects_missing_selected_render_asset_id(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_resolve_source_asset",
        lambda **_: {
            "episode_id": "episode-assetless",
            "scene_panel_id": "panel-assetless",
            "generation_id": "gen-assetless",
            "storage_path": "comics/previews/panel-assetless.png",
        },
    )
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "selected_render_asset_id: " in captured.out
    assert "failed_step: validate_source_asset" in captured.out
    assert "selected asset id is missing" in captured.err


def test_main_rejects_malformed_source_asset_payload(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(module, "_resolve_source_asset", lambda **_: None)
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "failed_step: resolve_source_asset" in captured.out
    assert "source asset resolution must return a mapping" in captured.err


def test_main_prints_summary_markers_for_non_runtime_error(monkeypatch, capsys):
    module = _load_module()

    def fail_resolve_source_asset(**_):
        raise ValueError("invalid source asset payload")

    monkeypatch.setattr(module, "_resolve_source_asset", fail_resolve_source_asset)
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "failed_step: resolve_source_asset" in captured.out
    assert "invalid source asset payload" in captured.err


def test_main_reports_bounded_stop_after_guardrails_pass(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_resolve_source_asset",
        lambda **_: {
            "episode_id": "episode-3",
            "scene_panel_id": "panel-3",
            "selected_render_asset_id": "asset-3",
            "generation_id": "gen-3",
            "storage_path": "comics/previews/panel-03.png",
        },
    )
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "failed_step: launch" in captured.out
    assert "animation launch is not implemented yet" in captured.err


def test_main_passes_cli_values_to_source_resolution_and_prints_custom_preset(
    monkeypatch,
    capsys,
):
    module = _load_module()
    received_kwargs = {}

    def fake_resolve_source_asset(**kwargs):
        received_kwargs.update(kwargs)
        return {
            "episode_id": "episode-cli",
            "scene_panel_id": "panel-cli",
            "selected_render_asset_id": "asset-cli",
            "generation_id": "gen-cli",
            "storage_path": "comics/previews/panel-cli.png",
        }

    monkeypatch.setattr(module, "_resolve_source_asset", fake_resolve_source_asset)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_teaser_animation_smoke.py",
            "--episode-id",
            "episode-cli",
            "--panel-index",
            "7",
            "--preset-id",
            "custom_teaser_v1",
            "--poll-sec",
            "2.5",
            "--timeout-sec",
            "900",
        ],
    )
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert received_kwargs == {
        "base_url": "http://127.0.0.1:8000",
        "episode_id": "episode-cli",
        "panel_index": 7,
        "preset_id": "custom_teaser_v1",
        "poll_sec": 2.5,
        "timeout_sec": 900.0,
    }
    assert "preset_id: custom_teaser_v1" in captured.out
    assert "animation launch is not implemented yet" in captured.err
