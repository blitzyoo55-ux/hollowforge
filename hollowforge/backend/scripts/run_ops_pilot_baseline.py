import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


@dataclass(slots=True)
class CheckResult:
    name: str
    status: str
    summary: str
    details: str
    duration_sec: float


@dataclass(slots=True)
class CheckSpec:
    name: str
    command: list[str]
    cwd: Path
    timeout_sec: float
    parser: Callable[[str], str] | None = None


def _execute_command_check(
    spec: CheckSpec,
    *,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> CheckResult:
    started_at = time.perf_counter()
    try:
        completed = run_command(
            args=spec.command,
            cwd=spec.cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=spec.timeout_sec,
        )
    except subprocess.TimeoutExpired:
        duration_sec = time.perf_counter() - started_at
        return CheckResult(spec.name, "FAIL", f"timeout after {spec.timeout_sec}s", "", duration_sec)

    duration_sec = time.perf_counter() - started_at
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    details = stderr or stdout
    if completed.returncode == 0:
        summary = spec.parser(stdout) if spec.parser is not None else (stdout or "ok")
        return CheckResult(spec.name, "PASS", summary, details, duration_sec)

    summary = spec.parser(stdout) if spec.parser is not None else (stdout or f"exit {completed.returncode}")
    return CheckResult(spec.name, "FAIL", summary, details, duration_sec)


def _run_checks(
    specs: Sequence[CheckSpec],
    *,
    runner: Callable[[CheckSpec], CheckResult] = _execute_command_check,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for spec in specs:
        results.append(runner(spec))
    return results


def _render_baseline_section(results: Sequence[CheckResult]) -> str:
    lines = ["## Baseline"]
    by_name = {result.name: result for result in results}
    for check_name in (
        "backend tests",
        "frontend tests",
        "adult provider resolution",
        "story planner smoke",
    ):
        result = by_name.get(check_name)
        if result is None:
            lines.append(f"- {check_name}:")
            continue
        lines.append(f"- {check_name}: {result.status} - {result.summary}")
    return "\n".join(lines) + "\n"


def _write_baseline_section(*, log_path: Path, rendered_baseline: str, dry_run: bool) -> str:
    original = log_path.read_text(encoding="utf-8")
    start_marker = "## Baseline\n"

    start = original.find(start_marker)
    if start == -1:
        raise ValueError("Baseline section not found")

    section_start = start + len(start_marker)
    section_end = original.find("\n## ", section_start)
    if section_end == -1:
        section_end = len(original)

    updated = original[:start] + rendered_baseline + original[section_end:]
    if not dry_run:
        log_path.write_text(updated, encoding="utf-8")
    return rendered_baseline
