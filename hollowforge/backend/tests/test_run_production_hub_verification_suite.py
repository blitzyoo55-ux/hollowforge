from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_production_hub_verification_suite.py"
    )
    spec = importlib.util.spec_from_file_location(
        "run_production_hub_verification_suite",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_stage_runner(
    module,
    monkeypatch,
    *,
    stage_exit_codes: dict[str, int] | None = None,
):
    calls: list[str] = []
    exit_codes = stage_exit_codes or {}

    monkeypatch.setattr(
        module,
        "_run_stage_process",
        lambda *, stage, base_url, verification_run_id=None: calls.append(stage)
        or exit_codes.get(stage, 0),
    )
    return calls


def _patch_persistence(
    module,
    monkeypatch,
    *,
    response: dict[str, object] | None = None,
):
    post_calls: list[tuple[str, dict[str, object]]] = []
    payload_response = response or {"id": "prod-run-1"}

    monkeypatch.setattr(
        module,
        "_post_json",
        lambda url, payload: post_calls.append((url, payload)) or payload_response,
        raising=False,
    )
    return post_calls


def test_main_runs_default_stage_order_and_prints_suite_summary(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    calls = _patch_stage_runner(module, monkeypatch)
    post_calls = _patch_persistence(module, monkeypatch)

    assert module.main(["--base-url", "http://127.0.0.1:8014"]) == 0

    captured = capsys.readouterr()
    assert calls == ["smoke", "ui"]
    assert "suite_mode: production_hub_verification" in captured.out
    assert "stages_requested: smoke,ui" in captured.out
    assert "stages_completed: smoke,ui" in captured.out
    assert "stage_smoke_exit_code: 0" in captured.out
    assert "stage_ui_exit_code: 0" in captured.out
    assert "overall_success: true" in captured.out
    assert "production_verification_run_persisted: true" in captured.out
    assert post_calls == [
        (
            "http://127.0.0.1:8014/api/v1/production/verification/runs",
            {
                "id": post_calls[0][1]["id"],
                "run_mode": "suite",
                "status": "completed",
                "overall_success": True,
                "failure_stage": None,
                "error_summary": None,
                "base_url": "http://127.0.0.1:8014",
                "total_duration_sec": pytest.approx(post_calls[0][1]["total_duration_sec"]),
                "started_at": post_calls[0][1]["started_at"],
                "finished_at": post_calls[0][1]["finished_at"],
                "stage_status": {
                    "smoke": {
                        "status": "passed",
                        "duration_sec": pytest.approx(post_calls[0][1]["stage_status"]["smoke"]["duration_sec"]),
                    },
                    "ui": {
                        "status": "passed",
                        "duration_sec": pytest.approx(post_calls[0][1]["stage_status"]["ui"]["duration_sec"]),
                    },
                },
            },
        )
    ]


@pytest.mark.parametrize(
    ("flag", "expected_stage"),
    [
        ("--smoke-only", "smoke"),
        ("--ui-only", "ui"),
    ],
)
def test_main_runs_selected_stage_only(
    monkeypatch,
    capsys,
    flag: str,
    expected_stage: str,
) -> None:
    module = _load_module()
    calls = _patch_stage_runner(module, monkeypatch)
    _patch_persistence(module, monkeypatch)

    assert module.main(["--base-url", "http://127.0.0.1:8014", flag]) == 0

    captured = capsys.readouterr()
    assert calls == [expected_stage]
    assert f"stages_requested: {expected_stage}" in captured.out
    assert f"stages_completed: {expected_stage}" in captured.out
    assert "overall_success: true" in captured.out


def test_main_rejects_multiple_stage_selection_flags(capsys) -> None:
    module = _load_module()

    assert module.main(["--smoke-only", "--ui-only"]) == 2

    captured = capsys.readouterr()
    assert "choose only one stage selection flag" in captured.err


def test_main_stops_on_first_failure_by_default(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    calls = _patch_stage_runner(
        module,
        monkeypatch,
        stage_exit_codes={"smoke": 0, "ui": 1},
    )

    assert module.main(["--base-url", "http://127.0.0.1:8014"]) == 1

    captured = capsys.readouterr()
    assert calls == ["smoke", "ui"]
    assert "failed_stage: ui" in captured.out
    assert "continue_on_failure: false" in captured.out
    assert "overall_success: false" in captured.out


def test_main_can_continue_after_failure_when_requested(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    calls = _patch_stage_runner(
        module,
        monkeypatch,
        stage_exit_codes={"smoke": 1, "ui": 0},
    )

    assert (
        module.main(
            [
                "--base-url",
                "http://127.0.0.1:8014",
                "--continue-on-failure",
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert calls == ["smoke", "ui"]
    assert "failed_stage: smoke" in captured.out
    assert "continue_on_failure: true" in captured.out
    assert "overall_success: false" in captured.out


def test_main_returns_nonzero_when_run_persistence_fails(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    _patch_stage_runner(module, monkeypatch)

    def _raise(url: str, payload: dict[str, object]) -> dict[str, object]:
        raise RuntimeError("persist boom")

    monkeypatch.setattr(module, "_post_json", _raise, raising=False)

    assert module.main(["--base-url", "http://127.0.0.1:8014"]) == 1

    captured = capsys.readouterr()
    assert "overall_success: true" in captured.out
    assert "production_verification_run_persisted: false" in captured.out
    assert "production_verification_run_persist_error: persist boom" in captured.out


def test_main_reuses_verification_run_id_for_smoke_stage_and_persistence(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    stage_calls: list[tuple[str, str | None]] = []

    def _fake_run_stage_process(
        *,
        stage: str,
        base_url: str,
        verification_run_id: str | None = None,
    ) -> int:
        assert base_url == "http://127.0.0.1:8014"
        stage_calls.append((stage, verification_run_id))
        return 0

    monkeypatch.setattr(module, "_run_stage_process", _fake_run_stage_process)
    post_calls = _patch_persistence(module, monkeypatch)

    assert module.main(["--base-url", "http://127.0.0.1:8014"]) == 0

    captured = capsys.readouterr()
    assert "production_verification_run_persisted: true" in captured.out

    smoke_run_id = next(
        verification_run_id
        for stage, verification_run_id in stage_calls
        if stage == "smoke"
    )
    assert smoke_run_id
    assert post_calls[0][1]["id"] == smoke_run_id


def test_resolve_stage_cwd_points_ui_stage_at_repo_frontend() -> None:
    module = _load_module()
    expected_repo_root = Path(__file__).resolve().parents[2]

    assert module._resolve_stage_cwd("smoke") == module.SCRIPT_DIR
    assert module._resolve_stage_cwd("ui") == expected_repo_root / "frontend"
