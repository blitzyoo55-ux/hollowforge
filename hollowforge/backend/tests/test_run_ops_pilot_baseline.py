from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_ops_pilot_baseline.py"
    spec = importlib.util.spec_from_file_location("run_ops_pilot_baseline", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_baseline_section_includes_all_expected_lines() -> None:
    module = _load_module()

    results = [
        module.CheckResult(
            name="backend tests",
            status="PASS",
            summary="5 files / 62 passed",
            details="",
            duration_sec=3.5,
        ),
        module.CheckResult(
            name="frontend tests",
            status="PASS",
            summary="vitest ok",
            details="",
            duration_sec=8.2,
        ),
        module.CheckResult(
            name="adult provider resolution",
            status="PASS",
            summary="prompt=adult_openrouter_grok runtime=adult_local_llm",
            details="",
            duration_sec=0.1,
        ),
        module.CheckResult(
            name="story planner smoke",
            status="FAIL",
            summary="lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=0",
            details="connection refused",
            duration_sec=1.2,
        ),
    ]

    rendered = module._render_baseline_section(results)

    assert rendered.splitlines() == [
        "## Baseline",
        "- backend tests: PASS - 5 files / 62 passed",
        "- frontend tests: PASS - vitest ok",
        "- adult provider resolution: PASS - prompt=adult_openrouter_grok runtime=adult_local_llm",
        "- story planner smoke: FAIL - lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=0",
    ]


def test_write_baseline_section_dry_run_does_not_modify_file(tmp_path: Path) -> None:
    module = _load_module()

    log_path = tmp_path / "pilot-log.md"
    log_path.write_text(
        "# HollowForge Ops Pilot Log\n\n"
        "## Baseline\n"
        "- backend tests:\n"
        "- frontend tests:\n"
        "- adult provider resolution:\n"
        "- story planner smoke:\n",
        encoding="utf-8",
    )

    original = log_path.read_text(encoding="utf-8")
    preview = module._write_baseline_section(
        log_path=log_path,
        rendered_baseline=(
            "## Baseline\n"
            "- backend tests: PASS - ok\n"
            "- frontend tests: PASS - ok\n"
            "- adult provider resolution: PASS - ok\n"
            "- story planner smoke: FAIL - offline\n"
        ),
        dry_run=True,
    )

    assert "PASS - ok" in preview
    assert preview.count("- backend tests: PASS - ok") == 1
    assert log_path.read_text(encoding="utf-8") == original


def test_write_baseline_section_preserves_other_sections(tmp_path: Path) -> None:
    module = _load_module()

    log_path = tmp_path / "pilot-log.md"
    log_path.write_text(
        "# HollowForge Ops Pilot Log\n\n"
        "## Baseline\n"
        "- backend tests:\n"
        "- frontend tests:\n"
        "- adult provider resolution:\n"
        "- story planner smoke:\n\n"
        "## Unexpected Section\n"
        "- keep-this-section\n\n"
        "## Episode Runs\n"
        "- episode:\n"
        "  - premise: keep-me\n\n"
        "## Ready Queue\n"
        "- selected generation ids: keep-me\n\n"
        "## Publishing Pilot\n"
        "- generation id: keep-me\n",
        encoding="utf-8",
    )

    module._write_baseline_section(
        log_path=log_path,
        rendered_baseline=(
            "## Baseline\n"
            "- backend tests: PASS - ok\n"
            "- frontend tests: PASS - ok\n"
            "- adult provider resolution: PASS - ok\n"
            "- story planner smoke: FAIL - offline\n"
        ),
        dry_run=False,
    )

    updated = log_path.read_text(encoding="utf-8")
    rendered_baseline = (
        "## Baseline\n"
        "- backend tests: PASS - ok\n"
        "- frontend tests: PASS - ok\n"
        "- adult provider resolution: PASS - ok\n"
        "- story planner smoke: FAIL - offline\n"
    )

    assert updated.count(rendered_baseline) == 1
    assert "- backend tests:\n" not in updated
    assert "- frontend tests:\n" not in updated
    assert "- adult provider resolution:\n" not in updated
    assert "- story planner smoke:\n" not in updated
    assert "## Unexpected Section\n- keep-this-section" in updated
    assert "premise: keep-me" in updated
    assert "selected generation ids: keep-me" in updated
    assert "generation id: keep-me" in updated


def test_run_checks_continues_after_failure() -> None:
    module = _load_module()
    seen: list[str] = []

    def fake_runner(spec: module.CheckSpec) -> module.CheckResult:
        seen.append(spec.name)
        if spec.name == "backend tests":
            return module.CheckResult(spec.name, "FAIL", "pytest failed", "exit 1", 0.2)
        return module.CheckResult(spec.name, "PASS", "ok", "", 0.1)

    results = module._run_checks(
        [
            module.CheckSpec(name="backend tests", command=["backend"], cwd=Path("/tmp"), timeout_sec=1),
            module.CheckSpec(name="frontend tests", command=["frontend"], cwd=Path("/tmp"), timeout_sec=1),
        ],
        runner=fake_runner,
    )

    assert seen == ["backend tests", "frontend tests"]
    assert [result.status for result in results] == ["FAIL", "PASS"]


def test_execute_check_reports_timeout_as_fail(tmp_path: Path) -> None:
    module = _load_module()
    spec = module.CheckSpec(
        name="frontend tests",
        command=["npm", "test"],
        cwd=tmp_path,
        timeout_sec=180,
    )

    def fake_subprocess_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd=kwargs["args"], timeout=180)

    result = module._execute_command_check(spec, run_command=fake_subprocess_run)

    assert result.status == "FAIL"
    assert result.summary == "timeout after 180s"


def test_execute_check_reports_zero_exit_as_pass(tmp_path: Path) -> None:
    module = _load_module()
    spec = module.CheckSpec(
        name="backend tests",
        command=["pytest"],
        cwd=tmp_path,
        timeout_sec=60,
    )

    def fake_subprocess_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=kwargs["args"],
            returncode=0,
            stdout="ok from stdout",
            stderr="",
        )

    result = module._execute_command_check(spec, run_command=fake_subprocess_run)

    assert result.status == "PASS"
    assert result.summary == "ok from stdout"


def test_execute_check_reports_non_zero_exit_as_fail(tmp_path: Path) -> None:
    module = _load_module()
    spec = module.CheckSpec(
        name="frontend tests",
        command=["npm", "test"],
        cwd=tmp_path,
        timeout_sec=60,
    )

    def fake_subprocess_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=kwargs["args"],
            returncode=3,
            stdout="",
            stderr="boom",
        )

    result = module._execute_command_check(spec, run_command=fake_subprocess_run)

    assert result.status == "FAIL"
    assert result.summary == "exit 3"


def test_execute_check_uses_parser_summary_on_pass(tmp_path: Path) -> None:
    module = _load_module()
    spec = module.CheckSpec(
        name="parser check",
        command=["tool"],
        cwd=tmp_path,
        timeout_sec=60,
        parser=lambda stdout: f"parsed: {stdout.upper()}",
    )

    def fake_subprocess_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=kwargs["args"],
            returncode=0,
            stdout="custom summary",
            stderr="",
        )

    result = module._execute_command_check(spec, run_command=fake_subprocess_run)

    assert result.status == "PASS"
    assert result.summary == "parsed: CUSTOM SUMMARY"
