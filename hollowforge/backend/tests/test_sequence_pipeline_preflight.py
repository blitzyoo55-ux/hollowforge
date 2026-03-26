from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

import pytest


def _load_preflight_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "check_sequence_pipeline_preflight.py"
    )
    spec = importlib.util.spec_from_file_location(
        "check_sequence_pipeline_preflight",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_fails_when_selected_executor_profile_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    preflight = _load_preflight_module()

    monkeypatch.setattr(preflight, "_check_db_state", lambda: [])
    monkeypatch.setattr(preflight, "_check_prompt_profiles", lambda: [])
    monkeypatch.setattr(preflight, "_canonical_executor_checks", lambda: [])
    monkeypatch.setattr(
        preflight,
        "_check_ffmpeg",
        lambda: preflight.CheckResult(
            name="ffmpeg_bin",
            status="PASS",
            detail="resolved",
        ),
    )

    exit_code = preflight.run(
        ["--executor-profile-id", "missing_profile", "--worker-check", "skip"]
    )

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "[FAIL] selected_executor_profile:missing_profile:" in output


def test_check_remote_worker_fails_when_health_payload_is_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflight = _load_preflight_module()
    monkeypatch.setattr(
        preflight.settings,
        "ANIMATION_REMOTE_BASE_URL",
        "http://worker.test",
    )
    monkeypatch.setattr(
        preflight,
        "_fetch_json",
        lambda url: {"status": "error", "executor_backend": "stub"},
    )

    result = preflight._check_remote_worker(
        Namespace(
            executor_profile_id=["safe_remote_prod"],
            worker_check="auto",
        ),
        [
            {
                "id": "safe_remote_prod",
                "executor_mode": "remote_worker",
            }
        ],
    )

    assert result.status == "FAIL"
    assert "unhealthy" in result.detail


def test_check_remote_worker_passes_when_health_payload_is_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preflight = _load_preflight_module()
    monkeypatch.setattr(
        preflight.settings,
        "ANIMATION_REMOTE_BASE_URL",
        "http://worker.test",
    )
    monkeypatch.setattr(
        preflight,
        "_fetch_json",
        lambda url: {"status": "ready", "executor_backend": "stub", "accepting_jobs": True},
    )

    result = preflight._check_remote_worker(
        Namespace(
            executor_profile_id=["safe_remote_prod"],
            worker_check="auto",
        ),
        [
            {
                "id": "safe_remote_prod",
                "executor_mode": "remote_worker",
            }
        ],
    )

    assert result.status == "PASS"
    assert "status=ready" in result.detail
