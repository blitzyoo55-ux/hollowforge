import argparse
import inspect
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


BACKEND_TEST_TIMEOUT_SEC = 120
PROVIDER_RESOLUTION_TIMEOUT_SEC = 15
STORY_PLANNER_SMOKE_TIMEOUT_SEC = 60
FRONTEND_TEST_TIMEOUT_SEC = 180

DEFAULT_LOG_RELATIVE_PATH = Path(
    "docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md"
)
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_UI_BASE_URL = "http://localhost:5173"
DEFAULT_STORY_PROMPT = (
    "Hana Seo compares notes with a quiet messenger in the "
    "Moonlit Bathhouse corridor after closing."
)
DEFAULT_LANE = "unrestricted"
DEFAULT_CANDIDATE_COUNT = 2

BACKEND_TEST_PATHS = [
    "tests/test_sequence_registry.py",
    "tests/test_story_planner_catalog.py",
    "tests/test_story_planner_routes.py",
    "tests/test_marketing_routes.py",
    "tests/test_sequence_run_service.py",
]
EXPECTED_ADULT_PROMPT_FACTORY_DEFAULT = "adult_openrouter_grok"
EXPECTED_ADULT_SEQUENCE_RUNTIME_DEFAULT = "adult_local_llm"
PROVIDER_PROMPT_LABEL = "prompt_factory_adult_default"
PROVIDER_RUNTIME_LABEL = "sequence_runtime_adult_default"


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
    parser: Callable[..., str | CheckResult] | None = None


def _extract_labeled_value(stdout: str, label: str) -> str | None:
    prefix = f"{label}:"
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _call_parser(
    parser: Callable[..., str | CheckResult],
    completed: subprocess.CompletedProcess[str],
    duration_sec: float,
    *,
    fallback_name: str,
) -> CheckResult:
    parameter_count = len(inspect.signature(parser).parameters)
    if parameter_count == 1:
        summary = parser((completed.stdout or "").strip())
        assert isinstance(summary, str)
        details = ((completed.stderr or "").strip() or (completed.stdout or "").strip())
        status = "PASS" if completed.returncode == 0 else "FAIL"
        return CheckResult(fallback_name, status, summary, details, duration_sec)

    parsed = parser(completed, duration_sec=duration_sec)
    assert isinstance(parsed, CheckResult)
    return parsed


def _parse_provider_resolution_result(
    completed: subprocess.CompletedProcess[str],
    *,
    duration_sec: float,
) -> CheckResult:
    stdout = (completed.stdout or "").strip()
    prompt_default = _extract_labeled_value(stdout, PROVIDER_PROMPT_LABEL)
    runtime_default = _extract_labeled_value(stdout, PROVIDER_RUNTIME_LABEL)
    expected_summary = (
        f"prompt={EXPECTED_ADULT_PROMPT_FACTORY_DEFAULT} "
        f"runtime={EXPECTED_ADULT_SEQUENCE_RUNTIME_DEFAULT}"
    )
    if (
        prompt_default == EXPECTED_ADULT_PROMPT_FACTORY_DEFAULT
        and runtime_default == EXPECTED_ADULT_SEQUENCE_RUNTIME_DEFAULT
    ):
        return CheckResult(
            name="adult provider resolution",
            status="PASS",
            summary=expected_summary,
            details=stdout,
            duration_sec=duration_sec,
        )

    missing_labels: list[str] = []
    if prompt_default is None:
        missing_labels.append(PROVIDER_PROMPT_LABEL)
    if runtime_default is None:
        missing_labels.append(PROVIDER_RUNTIME_LABEL)
    if missing_labels:
        summary = "missing labels: " + ", ".join(missing_labels)
    else:
        summary = (
            f"unexpected defaults: prompt={prompt_default} runtime={runtime_default}"
        )
    return CheckResult(
        name="adult provider resolution",
        status="FAIL",
        summary=summary,
        details=stdout,
        duration_sec=duration_sec,
    )


def _parse_story_planner_smoke_result(
    completed: subprocess.CompletedProcess[str],
    *,
    duration_sec: float,
) -> CheckResult:
    stdout = (completed.stdout or "").strip()
    saw_plan_result = False
    saw_queue_result = False
    lane: str | None = None
    policy_pack_id: str | None = None
    queued_generation_count: str | None = None

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line == "plan_result:":
            saw_plan_result = True
            continue
        if line == "queue_result:":
            saw_queue_result = True
            continue
        if saw_plan_result and not saw_queue_result and line.startswith("lane:"):
            lane = line.split(":", 1)[1].strip()
            continue
        if saw_plan_result and not saw_queue_result and line.startswith("policy_pack_id:"):
            policy_pack_id = line.split(":", 1)[1].strip()
            continue
        if saw_queue_result and line.startswith("queued_generation_count:"):
            queued_generation_count = line.split(":", 1)[1].strip()

    if saw_plan_result and saw_queue_result and lane and policy_pack_id and queued_generation_count:
        return CheckResult(
            name="story planner smoke",
            status="PASS",
            summary=(
                f"lane={lane} policy={policy_pack_id} "
                f"queued={queued_generation_count}"
            ),
            details=stdout,
            duration_sec=duration_sec,
        )

    missing_parts: list[str] = []
    if not saw_plan_result:
        missing_parts.append("plan_result:")
    if lane is None:
        missing_parts.append("lane:")
    if policy_pack_id is None:
        missing_parts.append("policy_pack_id:")
    if not saw_queue_result:
        missing_parts.append("queue_result:")
    if queued_generation_count is None:
        missing_parts.append("queued_generation_count:")
    return CheckResult(
        name="story planner smoke",
        status="FAIL",
        summary="missing labels: " + ", ".join(missing_parts),
        details=stdout,
        duration_sec=duration_sec,
    )


def _build_check_specs(
    *,
    repo_root: Path,
    base_url: str,
    ui_base_url: str,
    story_prompt: str,
    lane: str,
    candidate_count: int,
) -> list[CheckSpec]:
    backend_dir = repo_root / "backend"
    frontend_dir = repo_root / "frontend"
    provider_resolution_code = "\n".join(
        [
            "from app.config import settings",
            (
                "print("
                f"\"{PROVIDER_PROMPT_LABEL}: \", "
                "end=\"\""
                ")"
            ),
            "print(settings.HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE)",
            (
                "print("
                f"\"{PROVIDER_RUNTIME_LABEL}: \", "
                "end=\"\""
                ")"
            ),
            "print(settings.HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE)",
        ]
    )
    return [
        CheckSpec(
            name="backend tests",
            command=[sys.executable, "-m", "pytest", *BACKEND_TEST_PATHS, "-q"],
            cwd=backend_dir,
            timeout_sec=BACKEND_TEST_TIMEOUT_SEC,
        ),
        CheckSpec(
            name="adult provider resolution",
            command=[sys.executable, "-c", provider_resolution_code],
            cwd=backend_dir,
            timeout_sec=PROVIDER_RESOLUTION_TIMEOUT_SEC,
            parser=_parse_provider_resolution_result,
        ),
        CheckSpec(
            name="story planner smoke",
            command=[
                sys.executable,
                "scripts/launch_story_planner_smoke.py",
                "--base-url",
                base_url,
                "--ui-base-url",
                ui_base_url,
                "--story-prompt",
                story_prompt,
                "--lane",
                lane,
                "--candidate-count",
                str(candidate_count),
            ],
            cwd=backend_dir,
            timeout_sec=STORY_PLANNER_SMOKE_TIMEOUT_SEC,
            parser=_parse_story_planner_smoke_result,
        ),
        CheckSpec(
            name="frontend tests",
            command=["npm", "test"],
            cwd=frontend_dir,
            timeout_sec=FRONTEND_TEST_TIMEOUT_SEC,
        ),
    ]


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

    if completed.returncode != 0:
        summary = stdout or f"exit {completed.returncode}"
        return CheckResult(spec.name, "FAIL", summary, details, duration_sec)

    if spec.parser is not None:
        return _call_parser(spec.parser, completed, duration_sec, fallback_name=spec.name)

    return CheckResult(spec.name, "PASS", stdout or "ok", details, duration_sec)


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--ui-base-url", default=DEFAULT_UI_BASE_URL)
    parser.add_argument("--story-prompt", default=DEFAULT_STORY_PROMPT)
    parser.add_argument("--lane", default=DEFAULT_LANE)
    parser.add_argument("--candidate-count", type=int, default=DEFAULT_CANDIDATE_COUNT)
    parser.add_argument("--log-path")
    args = parser.parse_args(list(argv) if argv is not None else None)

    repo_root = Path(__file__).resolve().parents[2]
    log_path = Path(args.log_path) if args.log_path else repo_root / DEFAULT_LOG_RELATIVE_PATH
    specs = _build_check_specs(
        repo_root=repo_root,
        base_url=args.base_url,
        ui_base_url=args.ui_base_url,
        story_prompt=args.story_prompt,
        lane=args.lane,
        candidate_count=args.candidate_count,
    )
    results = _run_checks(specs)

    for result in results:
        print(f"[{result.status}] {result.name}: {result.summary} ({result.duration_sec:.1f}s)")
        if result.status == "FAIL" and result.details:
            print(result.details)

    rendered_baseline = _render_baseline_section(results)
    written_baseline = _write_baseline_section(
        log_path=log_path,
        rendered_baseline=rendered_baseline,
        dry_run=args.dry_run,
    )

    print("")
    print(written_baseline.rstrip())
    return 0 if all(result.status == "PASS" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
