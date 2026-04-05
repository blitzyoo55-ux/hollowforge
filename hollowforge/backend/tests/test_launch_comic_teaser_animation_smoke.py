from __future__ import annotations

import importlib.util
import json
import os
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
    assert "overall_success: false" in output
    assert "animation_job_id: " in output
    assert "output_path: " in output


def _write_dry_run_report(
    reports_dir: Path,
    name: str,
    *,
    episode_id: str,
    export_zip_path: str,
    layout_template_id: str = "jp_2x2_v1",
    manuscript_profile_id: str = "jp_manga_rightbound_v1",
    mtime: int,
) -> Path:
    report_path = reports_dir / name
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "episode_id": episode_id,
                "selected_panel_asset_count": 1 if export_zip_path else 0,
                "page_count": 1 if export_zip_path else 0,
                "layout_template_id": layout_template_id,
                "manuscript_profile_id": manuscript_profile_id,
                "export_zip_path": export_zip_path,
                "teaser_handoff_manifest_path": (
                    "comics/manifests/example_teaser_handoff.json" if export_zip_path else ""
                ),
                "episode_detail": {},
                "assembly_detail": {},
                "export_detail": (
                    {"export_zip_path": export_zip_path} if export_zip_path else {}
                ),
                "teaser_handoff_manifest": {
                    "selected_panel_assets": (
                        [{"panel_id": "panel-1", "asset_id": "asset-1"}]
                        if export_zip_path
                        else []
                    ),
                },
                "created_at": "2026-04-05T00:00:00+00:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    os.utime(report_path, (mtime, mtime))
    return report_path


def test_is_placeholder_asset_rejects_only_the_exact_smoke_assets_prefix() -> None:
    module = _load_module()

    assert module._is_placeholder_asset("comics/previews/smoke_assets/panel-01.png") is True
    assert (
        module._is_placeholder_asset("comics/previews/smoke_assets_backup/panel-01.png")
        is False
    )


def test_readme_documents_canonical_teaser_command_with_default_preset() -> None:
    module = _load_module()
    readme_path = Path(__file__).resolve().parents[2] / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")

    assert "./.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py \\" in readme_text
    assert f"--preset-id {module.DEFAULT_PRESET_ID}" in readme_text


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
            "--preset-id",
            "custom_teaser_v1",
            "--panel-index",
            "not-an-int",
        ],
    )
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "failed_step: bootstrap" in captured.out
    assert "preset_id: custom_teaser_v1" in captured.out
    assert "invalid int value" in captured.err


def test_main_invalid_cli_missing_preset_value_uses_safe_summary_value(monkeypatch, capsys):
    module = _load_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_teaser_animation_smoke.py",
            "--preset-id",
            "--panel-index",
            "not-an-int",
        ],
    )
    assert module.main() == 1
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "failed_step: bootstrap" in captured.out
    assert "preset_id: sdxl_ipadapter_microanim_v2" in captured.out
    assert "preset_id: --panel-index" not in captured.out
    assert "expected one argument" in captured.err


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


def test_resolve_source_asset_uses_latest_successful_dry_run_report_when_episode_id_omitted(
    monkeypatch,
    tmp_path,
) -> None:
    module = _load_module()
    data_dir = tmp_path / "data"
    reports_dir = data_dir / "comics" / "reports"
    monkeypatch.setattr(module.comic_dry_run.settings, "DATA_DIR", data_dir)

    _write_dry_run_report(
        reports_dir,
        "older_success_dry_run.json",
        episode_id="episode-old",
        export_zip_path="comics/exports/episode-old_handoff.zip",
        mtime=100,
    )
    _write_dry_run_report(
        reports_dir,
        "newest_missing_export_dry_run.json",
        episode_id="episode-skip",
        export_zip_path="",
        mtime=300,
    )
    _write_dry_run_report(
        reports_dir,
        "newest_success_dry_run.json",
        episode_id="episode-new",
        export_zip_path="comics/exports/episode-new_handoff.zip",
        layout_template_id="jp_3x1_cinematic_v2",
        manuscript_profile_id="jp_storyboard_vertical_v4",
        mtime=200,
    )

    received_kwargs = {}

    def fake_ensure_exported_episode(**kwargs):
        received_kwargs.update(kwargs)
        return {}, {"episode_id": kwargs["episode_id"]}, {}

    monkeypatch.setattr(
        module.comic_dry_run,
        "_ensure_exported_episode",
        fake_ensure_exported_episode,
    )
    monkeypatch.setattr(
        module.comic_dry_run,
        "_extract_selected_panel_assets",
        lambda _: [
            {
                "panel_id": "panel-0",
                "asset_id": "asset-0",
                "generation_id": "gen-0",
                "storage_path": "comics/previews/panel-0.png",
            },
            {
                "scene_panel_id": "panel-1",
                "selected_render_asset_id": "asset-1",
                "generation_id": "gen-1",
                "storage_path": "comics/previews/panel-1.png",
            },
        ],
    )

    source_asset = module._resolve_source_asset(
        base_url="http://127.0.0.1:8000",
        episode_id=None,
        panel_index=1,
    )

    assert source_asset == {
        "episode_id": "episode-new",
        "scene_panel_id": "panel-1",
        "selected_render_asset_id": "asset-1",
        "generation_id": "gen-1",
        "storage_path": "comics/previews/panel-1.png",
    }
    assert received_kwargs == {
        "base_url": "http://127.0.0.1:8000",
        "episode_id": "episode-new",
        "layout_template_id": "jp_3x1_cinematic_v2",
        "manuscript_profile_id": "jp_storyboard_vertical_v4",
    }


def test_resolve_source_asset_rejects_missing_selected_assets(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module.comic_dry_run,
        "_ensure_exported_episode",
        lambda **_: ({}, {"episode_id": "episode-empty"}, {}),
    )
    monkeypatch.setattr(module.comic_dry_run, "_extract_selected_panel_assets", lambda _: [])

    try:
        module._resolve_source_asset(
            base_url="http://127.0.0.1:8000",
            episode_id="episode-empty",
            panel_index=0,
        )
    except RuntimeError as exc:
        assert str(exc) == "Comic teaser handoff did not include any selected panel assets"
    else:
        raise AssertionError("Expected missing selected asset rejection")


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


def test_main_succeeds_with_resolved_source_asset_and_completed_mp4_output(
    monkeypatch,
    capsys,
    tmp_path,
):
    module = _load_module()
    data_dir = tmp_path / "data"
    output_path = data_dir / "animations" / "teaser.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"mp4")
    monkeypatch.setattr(module.comic_dry_run.settings, "DATA_DIR", data_dir)

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
    launch_kwargs = {}

    def fake_launch_job(**kwargs):
        launch_kwargs.update(kwargs)
        return "anim-job-3"

    monkeypatch.setattr(module.animation_smoke, "_launch_job", fake_launch_job)
    monkeypatch.setattr(
        module.animation_smoke,
        "_poll_job",
        lambda **_: {
            "id": "anim-job-3",
            "status": "completed",
            "output_path": "animations/teaser.mp4",
        },
    )
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])
    assert module.main() == 0
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    assert "animation_job_id: anim-job-3" in captured.out
    assert "output_path: animations/teaser.mp4" in captured.out
    assert "teaser_success: true" in captured.out
    assert "overall_success: true" in captured.out
    assert "launch_result:" not in captured.out
    assert "[status]" not in captured.out
    assert captured.err == ""
    assert launch_kwargs == {
        "base_url": "http://127.0.0.1:8000",
        "preset_id": module.DEFAULT_PRESET_ID,
        "generation_id": "gen-3",
        "request_overrides": {},
        "dispatch_immediately": True,
    }


def test_main_reconciles_stale_failure_before_launching_a_new_animation_job_id(
    monkeypatch,
    capsys,
    tmp_path,
):
    module = _load_module()
    rerun_animation_job_id = "anim-job-rerun"
    stale_animation_job = {
        "id": "anim-job-stale",
        "status": "processing",
        "error_message": None,
    }
    data_dir = tmp_path / "data"
    output_path = data_dir / "animations" / "teaser.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"mp4")
    monkeypatch.setattr(module.comic_dry_run.settings, "DATA_DIR", data_dir)
    resolve_kwargs = {}
    reconcile_called = False

    def reconcile_stale_animation_job() -> None:
        nonlocal reconcile_called
        reconcile_called = True
        stale_animation_job["status"] = "failed"
        stale_animation_job["error_message"] = "Worker restarted"

    def fake_resolve_source_asset(**kwargs):
        resolve_kwargs.update(kwargs)
        return {
            "episode_id": "episode-stale-failed",
            "scene_panel_id": "panel-stale",
            "selected_render_asset_id": "asset-stale",
            "generation_id": "gen-stale",
            "storage_path": "comics/previews/panel-stale.png",
        }

    def fake_launch_job(**kwargs):
        assert reconcile_called is True
        assert stale_animation_job == {
            "id": "anim-job-stale",
            "status": "failed",
            "error_message": "Worker restarted",
        }
        assert kwargs == {
            "base_url": "http://127.0.0.1:8000",
            "preset_id": module.DEFAULT_PRESET_ID,
            "generation_id": "gen-stale",
            "request_overrides": {},
            "dispatch_immediately": True,
        }
        return rerun_animation_job_id

    def fake_poll_job(**_):
        return {
            "id": rerun_animation_job_id,
            "status": "completed",
            "output_path": "animations/teaser.mp4",
        }

    assert stale_animation_job["status"] == "processing"
    assert stale_animation_job["error_message"] is None
    reconcile_stale_animation_job()
    monkeypatch.setattr(module, "_resolve_source_asset", fake_resolve_source_asset)
    monkeypatch.setattr(module.animation_smoke, "_launch_job", fake_launch_job)
    monkeypatch.setattr(module.animation_smoke, "_poll_job", fake_poll_job)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "launch_comic_teaser_animation_smoke.py",
            "--episode-id",
            "episode-stale-failed",
            "--panel-index",
            "0",
            "--preset-id",
            module.DEFAULT_PRESET_ID,
            "--poll-sec",
            "5",
            "--timeout-sec",
            "1800",
        ],
    )
    assert module.main() == 0
    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    assert resolve_kwargs == {
        "base_url": "http://127.0.0.1:8000",
        "episode_id": "episode-stale-failed",
        "panel_index": 0,
        "preset_id": module.DEFAULT_PRESET_ID,
        "poll_sec": 5.0,
        "timeout_sec": 1800.0,
    }
    assert f"animation_job_id: {rerun_animation_job_id}" in captured.out
    assert "animation_job_id: anim-job-stale" not in captured.out
    assert "teaser_success: true" in captured.out
    assert "overall_success: true" in captured.out
    assert captured.err == ""


def test_main_rejects_completed_animation_output_that_is_not_mp4(
    monkeypatch,
    capsys,
    tmp_path,
):
    module = _load_module()
    data_dir = tmp_path / "data"
    output_path = data_dir / "animations" / "teaser.gif"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"gif")
    monkeypatch.setattr(module.comic_dry_run.settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(
        module,
        "_resolve_source_asset",
        lambda **_: {
            "episode_id": "episode-cli",
            "scene_panel_id": "panel-cli",
            "selected_render_asset_id": "asset-cli",
            "generation_id": "gen-cli",
            "storage_path": "comics/previews/panel-cli.png",
        },
    )
    monkeypatch.setattr(module.animation_smoke, "_launch_job", lambda **_: "anim-job-cli")
    monkeypatch.setattr(
        module.animation_smoke,
        "_poll_job",
        lambda **_: {
            "id": "anim-job-cli",
            "status": "completed",
            "output_path": "animations/teaser.gif",
        },
    )
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
    assert "preset_id: custom_teaser_v1" in captured.out
    assert "animation_job_id: anim-job-cli" in captured.out
    assert "failed_step: validate_output_path" in captured.out
    assert "animation output_path must point to an .mp4 file" in captured.err


def test_main_rejects_missing_local_mp4_output_file(monkeypatch, capsys, tmp_path):
    module = _load_module()
    data_dir = tmp_path / "data"
    monkeypatch.setattr(module.comic_dry_run.settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(
        module,
        "_resolve_source_asset",
        lambda **_: {
            "episode_id": "episode-missing-file",
            "scene_panel_id": "panel-missing-file",
            "selected_render_asset_id": "asset-missing-file",
            "generation_id": "gen-missing-file",
            "storage_path": "comics/previews/panel-missing-file.png",
        },
    )
    monkeypatch.setattr(module.animation_smoke, "_launch_job", lambda **_: "anim-job-missing")
    monkeypatch.setattr(
        module.animation_smoke,
        "_poll_job",
        lambda **_: {
            "id": "anim-job-missing",
            "status": "completed",
            "output_path": "animations/teaser.mp4",
        },
    )
    monkeypatch.setattr(sys, "argv", ["launch_comic_teaser_animation_smoke.py"])

    assert module.main() == 1

    captured = capsys.readouterr()
    _assert_required_summary_markers(captured.out)
    _assert_bounded_failure_invariants(captured.out)
    assert "animation_job_id: anim-job-missing" in captured.out
    assert "output_path: animations/teaser.mp4" in captured.out
    assert "failed_step: validate_output_path" in captured.out
    assert "animation output file not found:" in captured.err
