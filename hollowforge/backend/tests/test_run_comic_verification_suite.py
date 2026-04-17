from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_comic_verification_suite.py"
    )
    spec = importlib.util.spec_from_file_location(
        "run_comic_verification_suite",
        module_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patch_stage_environment(
    module,
    monkeypatch,
    tmp_path: Path,
    *,
    stage_exit_codes: dict[str, int] | None = None,
    missing_stage: str | None = None,
):
    calls: list[str] = []
    exit_codes = stage_exit_codes or {}
    script_paths: dict[str, Path] = {}

    for stage in module.STAGE_ORDER:
        path = tmp_path / f"{stage}.py"
        if stage != missing_stage:
            path.write_text("# stub\n", encoding="utf-8")
        script_paths[stage] = path

    monkeypatch.setattr(
        module,
        "_resolve_stage_script_path",
        lambda stage: script_paths[stage],
    )
    monkeypatch.setattr(
        module,
        "_run_stage_process",
        lambda *, stage, script_path, base_url: calls.append(stage)
        or exit_codes.get(stage, 0),
    )
    return calls


def test_main_runs_default_stage_order_and_prints_suite_summary(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_module()
    calls = _patch_stage_environment(module, monkeypatch, tmp_path)

    assert module.main(["--base-url", "http://127.0.0.1:8012"]) == 0

    captured = capsys.readouterr()
    assert calls == ["smoke", "full", "remote"]
    assert "suite_mode: comic_verification" in captured.out
    assert "stages_requested: smoke,full,remote" in captured.out
    assert "stages_completed: smoke,full,remote" in captured.out
    assert "stage_smoke_exit_code: 0" in captured.out
    assert "stage_full_exit_code: 0" in captured.out
    assert "stage_remote_exit_code: 0" in captured.out
    assert "stage_smoke_duration_sec:" in captured.out
    assert "total_duration_sec:" in captured.out
    assert "overall_success: true" in captured.out


@pytest.mark.parametrize(
    ("flag", "expected_stage"),
    [
        ("--smoke-only", "smoke"),
        ("--full-only", "full"),
        ("--remote-only", "remote"),
    ],
)
def test_main_runs_selected_stage_only(
    monkeypatch,
    tmp_path: Path,
    capsys,
    flag: str,
    expected_stage: str,
) -> None:
    module = _load_module()
    calls = _patch_stage_environment(module, monkeypatch, tmp_path)

    assert module.main(["--base-url", "http://127.0.0.1:8012", flag]) == 0

    captured = capsys.readouterr()
    assert calls == [expected_stage]
    assert f"stages_requested: {expected_stage}" in captured.out
    assert f"stages_completed: {expected_stage}" in captured.out
    assert "overall_success: true" in captured.out


def test_main_rejects_multiple_stage_selection_flags(capsys) -> None:
    module = _load_module()

    assert (
        module.main(
            [
                "--base-url",
                "http://127.0.0.1:8012",
                "--smoke-only",
                "--full-only",
            ]
        )
        == 2
    )

    captured = capsys.readouterr()
    assert "choose only one stage selection flag" in captured.err


def test_main_stops_on_first_failure_by_default(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_module()
    calls = _patch_stage_environment(
        module,
        monkeypatch,
        tmp_path,
        stage_exit_codes={"smoke": 0, "full": 1, "remote": 0},
    )

    assert module.main(["--base-url", "http://127.0.0.1:8012"]) == 1

    captured = capsys.readouterr()
    assert calls == ["smoke", "full"]
    assert "stages_completed: smoke,full" in captured.out
    assert "failed_stage: full" in captured.out
    assert "continue_on_failure: false" in captured.out
    assert "overall_success: false" in captured.out


def test_main_can_continue_after_failure_when_requested(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_module()
    calls = _patch_stage_environment(
        module,
        monkeypatch,
        tmp_path,
        stage_exit_codes={"smoke": 0, "full": 1, "remote": 0},
    )

    assert (
        module.main(
            [
                "--base-url",
                "http://127.0.0.1:8012",
                "--continue-on-failure",
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert calls == ["smoke", "full", "remote"]
    assert "stages_completed: smoke,full,remote" in captured.out
    assert "failed_stage: full" in captured.out
    assert "continue_on_failure: true" in captured.out
    assert "overall_success: false" in captured.out


def test_main_reports_missing_stage_script_before_execution(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_module()
    calls = _patch_stage_environment(
        module,
        monkeypatch,
        tmp_path,
        missing_stage="full",
    )

    assert module.main(["--base-url", "http://127.0.0.1:8012"]) == 1

    captured = capsys.readouterr()
    assert calls == ["smoke"]
    assert "stages_completed: smoke,full" in captured.out
    assert "missing_stage_script: full" in captured.out
    assert "failed_stage: full" in captured.out
    assert "stage_full_exit_code: 1" in captured.out
    assert "overall_success: false" in captured.out
