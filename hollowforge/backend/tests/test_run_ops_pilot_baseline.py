from __future__ import annotations

import importlib.util
import subprocess
import sys
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


def test_execute_check_collapses_multiline_success_summary_and_preserves_details(
    tmp_path: Path,
) -> None:
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
            stdout="................................ [100%]\n62 passed in 3.03s\n",
            stderr="",
        )

    result = module._execute_command_check(spec, run_command=fake_subprocess_run)

    assert result.status == "PASS"
    assert result.summary == "62 passed in 3.03s"
    assert result.details == "................................ [100%]\n62 passed in 3.03s"


def test_execute_check_reports_non_zero_exit_prefers_stderr_summary(tmp_path: Path) -> None:
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
    assert result.summary == "boom"


def test_execute_check_collapses_multiline_failure_summary_and_preserves_details(
    tmp_path: Path,
) -> None:
    module = _load_module()
    spec = module.CheckSpec(
        name="story planner smoke",
        command=["python"],
        cwd=tmp_path,
        timeout_sec=60,
    )

    def fake_subprocess_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(
            args=kwargs["args"],
            returncode=1,
            stdout="ignored stdout",
            stderr="[ERROR] connection refused\nTraceback line 1\nTraceback line 2\n",
        )

    result = module._execute_command_check(spec, run_command=fake_subprocess_run)

    assert result.status == "FAIL"
    assert result.summary == "[ERROR] connection refused"
    assert result.details == "[ERROR] connection refused\nTraceback line 1\nTraceback line 2"


def test_execute_check_uses_parser_result_on_pass(tmp_path: Path) -> None:
    module = _load_module()

    def parser(completed: subprocess.CompletedProcess[str]) -> object:
        return module.CheckResult(
            name="parser check",
            status="PASS",
            summary=f"parsed: {completed.stdout.upper()}",
            details=completed.stdout,
            duration_sec=999.0,
        )

    spec = module.CheckSpec(
        name="parser check",
        command=["tool"],
        cwd=tmp_path,
        timeout_sec=60,
        parser=parser,
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


def test_build_check_specs_uses_expected_commands_and_workdirs() -> None:
    module = _load_module()
    repo_root = Path("/repo/hollowforge")

    specs = module._build_check_specs(
        repo_root=repo_root,
        base_url="http://127.0.0.1:8000",
        ui_base_url="http://localhost:5173",
        story_prompt="adult pilot story",
        lane="adult_nsfw",
        candidate_count=2,
    )

    assert len(specs) == 4

    assert specs[0].name == "backend tests"
    assert specs[0].cwd == repo_root / "backend"
    assert specs[0].command[:3] == [sys.executable, "-m", "pytest"]
    assert "tests/test_sequence_registry.py" in specs[0].command

    assert specs[1].name == "adult provider resolution"
    assert specs[1].cwd == repo_root / "backend"
    assert specs[1].command[:2] == [sys.executable, "-c"]
    assert "prompt_factory_adult_default" in specs[1].command[2]
    assert "sequence_runtime_adult_default" in specs[1].command[2]

    assert specs[2].name == "story planner smoke"
    assert specs[2].cwd == repo_root / "backend"
    assert specs[2].command == [
        sys.executable,
        "scripts/launch_story_planner_smoke.py",
        "--base-url",
        "http://127.0.0.1:8000",
        "--ui-base-url",
        "http://localhost:5173",
        "--story-prompt",
        "adult pilot story",
        "--lane",
        "adult_nsfw",
        "--candidate-count",
        "2",
    ]

    assert specs[3].name == "frontend tests"
    assert specs[3].cwd == repo_root / "frontend"
    assert specs[3].command == ["npm", "test"]


def test_parse_story_planner_smoke_summary_extracts_lane_policy_and_queue() -> None:
    module = _load_module()
    completed = subprocess.CompletedProcess(
        args=["python"],
        returncode=0,
        stdout=(
            "plan_result:\n"
            "lane: adult_nsfw\n"
            "policy_pack_id: canon_adult_nsfw_v1\n"
            "queue_result:\n"
            "queued_generation_count: 8\n"
        ),
        stderr="",
    )

    result = module._parse_story_planner_smoke_result(completed)

    assert result.status == "PASS"
    assert result.summary == "lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=8"


def test_parse_provider_resolution_summary_extracts_both_defaults() -> None:
    module = _load_module()
    completed = subprocess.CompletedProcess(
        args=["python"],
        returncode=0,
        stdout=(
            "prompt_factory_adult_default: adult_openrouter_grok\n"
            "sequence_runtime_adult_default: adult_local_llm\n"
        ),
        stderr="",
    )

    result = module._parse_provider_resolution_result(completed)

    assert result.status == "PASS"
    assert result.summary == "prompt=adult_openrouter_grok runtime=adult_local_llm"


def test_parse_provider_resolution_summary_fails_on_mismatched_default() -> None:
    module = _load_module()
    completed = subprocess.CompletedProcess(
        args=["python"],
        returncode=0,
        stdout=(
            "prompt_factory_adult_default: adult_local_llm\n"
            "sequence_runtime_adult_default: adult_local_llm\n"
        ),
        stderr="",
    )

    result = module._parse_provider_resolution_result(completed)

    assert result.status == "FAIL"
    assert (
        result.summary
        == "unexpected defaults: prompt=adult_local_llm runtime=adult_local_llm"
    )


def test_parse_story_planner_smoke_summary_fails_on_missing_required_label() -> None:
    module = _load_module()
    completed = subprocess.CompletedProcess(
        args=["python"],
        returncode=0,
        stdout=(
            "plan_result:\n"
            "lane: adult_nsfw\n"
            "queue_result:\n"
            "queued_generation_count: 8\n"
        ),
        stderr="",
    )

    result = module._parse_story_planner_smoke_result(completed)

    assert result.status == "FAIL"
    assert result.summary == "missing labels: policy_pack_id:"


def test_parse_story_planner_smoke_summary_fails_on_none_placeholder_values() -> None:
    module = _load_module()
    completed = subprocess.CompletedProcess(
        args=["python"],
        returncode=0,
        stdout=(
            "plan_result:\n"
            "lane: None\n"
            "policy_pack_id: None\n"
            "queue_result:\n"
            "queued_generation_count: None\n"
        ),
        stderr="",
    )

    result = module._parse_story_planner_smoke_result(completed)

    assert result.status == "FAIL"
    assert result.summary == "missing labels: lane:, policy_pack_id:, queued_generation_count:"


def test_dry_run_main_prints_rendered_baseline_and_does_not_modify_log(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
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

    captured_kwargs: dict[str, object] = {}

    def fake_build_check_specs(**kwargs):  # type: ignore[no-untyped-def]
        captured_kwargs.update(kwargs)
        return [
            module.CheckSpec(
                name="backend tests",
                command=["backend"],
                cwd=Path("/tmp"),
                timeout_sec=1,
            )
        ]

    def fake_run_checks(specs):  # type: ignore[no-untyped-def]
        assert len(specs) == 1
        return [
            module.CheckResult(
                name="backend tests",
                status="PASS",
                summary="ok",
                details="",
                duration_sec=0.1,
            ),
            module.CheckResult(
                name="frontend tests",
                status="PASS",
                summary="vitest ok",
                details="",
                duration_sec=0.2,
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
                status="PASS",
                summary="lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=8",
                details="",
                duration_sec=0.4,
            ),
        ]

    monkeypatch.setattr(module, "_build_check_specs", fake_build_check_specs)
    monkeypatch.setattr(module, "_run_checks", fake_run_checks)

    exit_code = module.main(
        [
            "--dry-run",
            "--base-url",
            "http://127.0.0.1:8000",
            "--ui-base-url",
            "http://localhost:5173",
            "--story-prompt",
            "adult pilot story",
            "--lane",
            "adult_nsfw",
            "--candidate-count",
            "2",
            "--log-path",
            str(log_path),
        ]
    )

    stdout = capsys.readouterr().out

    assert exit_code == 0
    assert captured_kwargs["base_url"] == "http://127.0.0.1:8000"
    assert captured_kwargs["ui_base_url"] == "http://localhost:5173"
    assert captured_kwargs["story_prompt"] == "adult pilot story"
    assert captured_kwargs["lane"] == "adult_nsfw"
    assert captured_kwargs["candidate_count"] == 2
    assert "## Baseline" in stdout
    assert "- backend tests: PASS - ok" in stdout
    assert (
        "- story planner smoke: PASS - lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=8"
        in stdout
    )
    assert log_path.read_text(encoding="utf-8") == original


def test_dry_run_main_prints_final_aggregate_fail_status(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
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

    def fake_build_check_specs(**kwargs):  # type: ignore[no-untyped-def]
        return [
            module.CheckSpec(
                name="backend tests",
                command=["backend"],
                cwd=Path("/tmp"),
                timeout_sec=1,
            )
        ]

    def fake_run_checks(specs):  # type: ignore[no-untyped-def]
        assert len(specs) == 1
        return [
            module.CheckResult(
                name="backend tests",
                status="PASS",
                summary="ok",
                details="",
                duration_sec=0.1,
            ),
            module.CheckResult(
                name="frontend tests",
                status="FAIL",
                summary="boom",
                details="[ERROR] boom",
                duration_sec=0.2,
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
                details="[ERROR] connection refused",
                duration_sec=0.4,
            ),
        ]

    monkeypatch.setattr(module, "_build_check_specs", fake_build_check_specs)
    monkeypatch.setattr(module, "_run_checks", fake_run_checks)

    exit_code = module.main(["--dry-run", "--log-path", str(log_path)])

    stdout = capsys.readouterr().out

    assert exit_code == 1
    assert "Overall status: FAIL" in stdout
