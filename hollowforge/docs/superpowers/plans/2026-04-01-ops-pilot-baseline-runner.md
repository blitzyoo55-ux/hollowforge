# HollowForge Ops Pilot Baseline Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a check-only baseline runner that executes the HollowForge ops pilot startup checks, prints a full PASS/FAIL summary, and updates only the `## Baseline` section of the pilot log unless `--dry-run` is used.

**Architecture:** Implement one backend script with a small result model, command-runner helpers, and Markdown section renderer. Keep the boundaries explicit: backend pytest, adult provider resolution, story planner smoke, and frontend `npm test` are separate checks; the runner aggregates them, continues after failures, and writes only the baseline section.

**Tech Stack:** Python 3.12, existing backend `.venv`, pytest, subprocess, argparse, existing smoke scripts, Markdown text replacement

---

## Scope Notes

- Repo root for this plan is `hollowforge/`.
- Backend implementation and tests live under `backend/`.
- Frontend command execution happens from `frontend/`, but no frontend code should change.
- Canonical backend command format is `cd backend && ./.venv/bin/python ...`.
- If implementation happens from a worktree without a local backend `.venv`, run the same commands with the shared repo backend interpreter path, but keep production code interpreter resolution based on `sys.executable`.
- Do not add process start/recovery logic.
- Do not widen this plan into Ready Queue or Publishing automation.

## File Structure Map

### Create

- `backend/scripts/run_ops_pilot_baseline.py`
- `backend/tests/test_run_ops_pilot_baseline.py`

### Modify

- `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`

### Verify Only

- `backend/scripts/launch_story_planner_smoke.py`
- `frontend/package.json`
- `docs/superpowers/specs/2026-04-01-ops-pilot-baseline-runner-design.md`

## Task 1: Add the Runner Skeleton, Result Model, and Baseline Section Renderer

**Files:**
- Create: `backend/tests/test_run_ops_pilot_baseline.py`
- Create: `backend/scripts/run_ops_pilot_baseline.py`
- Modify: `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`

- [ ] **Step 1: Write the failing renderer and dry-run tests**

Add initial tests in `backend/tests/test_run_ops_pilot_baseline.py` that load the script module with `importlib.util.spec_from_file_location(...)` and assert:

```python
def test_render_baseline_section_includes_all_expected_lines() -> None:
    results = [
        module.CheckResult(name="backend tests", status="PASS", summary="5 files / 62 passed", details="", duration_sec=3.5),
        module.CheckResult(name="frontend tests", status="PASS", summary="vitest ok", details="", duration_sec=8.2),
        module.CheckResult(name="adult provider resolution", status="PASS", summary="prompt=adult_openrouter_grok runtime=adult_local_llm", details="", duration_sec=0.1),
        module.CheckResult(name="story planner smoke", status="FAIL", summary="lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=0", details="connection refused", duration_sec=1.2),
    ]

    rendered = module._render_baseline_section(results)

    assert "## Baseline" in rendered
    assert "- backend tests: PASS - 5 files / 62 passed" in rendered
    assert "- frontend tests: PASS - vitest ok" in rendered
    assert "- adult provider resolution: PASS - prompt=adult_openrouter_grok runtime=adult_local_llm" in rendered
    assert "- story planner smoke: FAIL - lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=0" in rendered


def test_write_baseline_section_dry_run_does_not_modify_file(tmp_path: Path) -> None:
    log_path = tmp_path / "pilot-log.md"
    log_path.write_text("# HollowForge Ops Pilot Log\\n\\n## Baseline\\n- backend tests:\\n- frontend tests:\\n- story planner smoke:\\n", encoding="utf-8")

    original = log_path.read_text(encoding="utf-8")
    preview = module._write_baseline_section(log_path=log_path, rendered_baseline="## Baseline\\n- backend tests: PASS - ok\\n", dry_run=True)

    assert "PASS - ok" in preview
    assert log_path.read_text(encoding="utf-8") == original


def test_write_baseline_section_preserves_other_sections(tmp_path: Path) -> None:
    log_path = tmp_path / "pilot-log.md"
    log_path.write_text(
        "# HollowForge Ops Pilot Log\\n\\n"
        "## Baseline\\n"
        "- backend tests:\\n"
        "- frontend tests:\\n"
        "- story planner smoke:\\n\\n"
        "## Episode Runs\\n"
        "- episode:\\n"
        "  - premise: keep-me\\n\\n"
        "## Ready Queue\\n"
        "- selected generation ids: keep-me\\n\\n"
        "## Publishing Pilot\\n"
        "- generation id: keep-me\\n",
        encoding="utf-8",
    )

    module._write_baseline_section(
        log_path=log_path,
        rendered_baseline="## Baseline\\n- backend tests: PASS - ok\\n- frontend tests: PASS - ok\\n- adult provider resolution: PASS - ok\\n- story planner smoke: FAIL - offline\\n",
        dry_run=False,
    )

    updated = log_path.read_text(encoding="utf-8")
    assert "- backend tests: PASS - ok" in updated
    assert "premise: keep-me" in updated
    assert "selected generation ids: keep-me" in updated
    assert "generation id: keep-me" in updated
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_run_ops_pilot_baseline.py -q -k "render_baseline_section or dry_run"
```

Expected: FAIL because `run_ops_pilot_baseline.py` and its helpers do not exist yet.

- [ ] **Step 3: Implement the smallest viable runner skeleton**

Create `backend/scripts/run_ops_pilot_baseline.py` with:

```python
@dataclass(slots=True)
class CheckResult:
    name: str
    status: str
    summary: str
    details: str
    duration_sec: float


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
        summary = result.summary if result is not None else ""
        status = result.status if result is not None else ""
        lines.append(f"- {check_name}: {status} - {summary}".rstrip(" -"))
    return "\\n".join(lines) + "\\n"
```

Add a `_write_baseline_section(...)` helper that replaces only the `## Baseline` section in the Markdown file. In the same step, update `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md` so the template explicitly includes:

```md
## Baseline
- backend tests:
- frontend tests:
- adult provider resolution:
- story planner smoke:
```

- [ ] **Step 4: Run the tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_run_ops_pilot_baseline.py -q -k "render_baseline_section or dry_run"
```

Expected: PASS for the new render/write-path tests.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/run_ops_pilot_baseline.py backend/tests/test_run_ops_pilot_baseline.py docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md
git commit -m "feat(hollowforge): scaffold ops pilot baseline runner"
```

## Task 2: Add Command Execution, Timeout Handling, and Continue-After-Failure Orchestration

**Files:**
- Modify: `backend/tests/test_run_ops_pilot_baseline.py`
- Modify: `backend/scripts/run_ops_pilot_baseline.py`

- [ ] **Step 1: Write the failing orchestration tests**

Extend `backend/tests/test_run_ops_pilot_baseline.py` with focused tests for timeout and continue-after-failure behavior:

```python
def test_run_checks_continues_after_failure() -> None:
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_run_ops_pilot_baseline.py -q -k "continues_after_failure or timeout"
```

Expected: FAIL because `CheckSpec`, `_run_checks`, and `_execute_command_check` do not exist yet.

- [ ] **Step 3: Implement the execution core**

Add to `backend/scripts/run_ops_pilot_baseline.py`:

```python
@dataclass(slots=True)
class CheckSpec:
    name: str
    command: list[str]
    cwd: Path
    timeout_sec: int
    parser: Callable[[subprocess.CompletedProcess[str]], CheckResult] | None = None


def _execute_command_check(
    spec: CheckSpec,
    *,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> CheckResult:
    started = time.monotonic()
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
        return CheckResult(spec.name, "FAIL", f"timeout after {spec.timeout_sec}s", "", time.monotonic() - started)
```

Finish the helper so:

- non-zero exit becomes `FAIL`
- zero exit becomes `PASS`
- optional `parser` can build a custom summary from stdout
- `_run_checks(...)` always iterates through every `CheckSpec`

- [ ] **Step 4: Run the tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_run_ops_pilot_baseline.py -q -k "continues_after_failure or timeout"
```

Expected: PASS for the orchestration tests.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/run_ops_pilot_baseline.py backend/tests/test_run_ops_pilot_baseline.py
git commit -m "feat(hollowforge): add baseline runner execution core"
```

## Task 3: Wire the Real Baseline Checks, CLI, and Final Verification Path

**Files:**
- Modify: `backend/tests/test_run_ops_pilot_baseline.py`
- Modify: `backend/scripts/run_ops_pilot_baseline.py`

- [ ] **Step 1: Write the failing command-spec and parser tests**

Add tests that lock the real check definitions and smoke parsing contract:

```python
def test_build_check_specs_uses_expected_commands_and_workdirs() -> None:
    repo_root = Path("/repo/hollowforge")
    specs = module._build_check_specs(
        repo_root=repo_root,
        base_url="http://127.0.0.1:8000",
        ui_base_url="http://localhost:5173",
        story_prompt="adult pilot story",
        lane="adult_nsfw",
        candidate_count=2,
    )

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
    completed = subprocess.CompletedProcess(
        args=["python"],
        returncode=0,
        stdout="plan_result:\\nlane: adult_nsfw\\npolicy_pack_id: canon_adult_nsfw_v1\\nqueue_result:\\nqueued_generation_count: 8\\n",
        stderr="",
    )

    result = module._parse_story_planner_smoke_result(completed, duration_sec=2.4)

    assert result.status == "PASS"
    assert result.summary == "lane=adult_nsfw policy=canon_adult_nsfw_v1 queued=8"


def test_parse_provider_resolution_summary_extracts_both_defaults() -> None:
    completed = subprocess.CompletedProcess(
        args=["python"],
        returncode=0,
        stdout="prompt_factory_adult_default: adult_openrouter_grok\\nsequence_runtime_adult_default: adult_local_llm\\n",
        stderr="",
    )

    result = module._parse_provider_resolution_result(completed, duration_sec=0.2)

    assert result.status == "PASS"
    assert result.summary == "prompt=adult_openrouter_grok runtime=adult_local_llm"
```

Also add a test that `main([...,"--dry-run"])` prints rendered baseline content and leaves a temporary log file unchanged.

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_run_ops_pilot_baseline.py -q -k "build_check_specs or parse_story_planner_smoke_summary or dry_run_main"
```

Expected: FAIL because the real check builders, provider parser, smoke parser, and CLI entrypoint are not implemented yet.

- [ ] **Step 3: Implement the real checks and CLI**

Complete `backend/scripts/run_ops_pilot_baseline.py` with:

- `_build_check_specs(...)` that creates exactly four checks
- backend pytest command using `sys.executable -m pytest` and the pinned file list from the spec
- adult provider resolution command using `sys.executable -c "..."` with an explicit stdout contract:

```text
prompt_factory_adult_default: adult_openrouter_grok
sequence_runtime_adult_default: adult_local_llm
```

The inline Python should import the existing settings and print those exact labels by reading:

- `settings.HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE`
- `settings.HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE`

- `_parse_provider_resolution_result(...)` that consumes only those two labels and fails if either is missing or mismatched
- story planner smoke command using `sys.executable scripts/launch_story_planner_smoke.py ...`
- frontend check command `["npm", "test"]`
- timeout constants:

```python
BACKEND_TEST_TIMEOUT_SEC = 120
PROVIDER_RESOLUTION_TIMEOUT_SEC = 15
STORY_PLANNER_SMOKE_TIMEOUT_SEC = 60
FRONTEND_TEST_TIMEOUT_SEC = 180
```

- `_parse_story_planner_smoke_result(...)` that only consumes these labels:

```text
plan_result:
lane:
policy_pack_id:
queue_result:
queued_generation_count:
```

- `main()` that:
  - parses CLI flags
  - resolves repo root from `Path(__file__).resolve().parents[2]`
  - runs all checks
  - prints per-check PASS/FAIL summaries
  - writes the baseline section unless `--dry-run`
  - returns `0` only if all checks pass, otherwise `1`

- [ ] **Step 4: Run the new unit tests**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_run_ops_pilot_baseline.py -q
```

Expected: PASS for the new baseline runner tests.

- [ ] **Step 5: Run the broader verification slice**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest \
  tests/test_run_ops_pilot_baseline.py \
  tests/test_sequence_registry.py \
  tests/test_story_planner_catalog.py \
  tests/test_story_planner_routes.py \
  tests/test_marketing_routes.py \
  tests/test_sequence_run_service.py \
  -q
```

Expected: PASS for the runner tests and the pinned backend baseline slice.

- [ ] **Step 6: Optional dry-run smoke verification**

If local backend and frontend are already running, run:

```bash
cd backend && ./.venv/bin/python scripts/run_ops_pilot_baseline.py --dry-run --lane adult_nsfw
```

Expected: the script prints all four check results and echoes the rendered `## Baseline` preview without modifying `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`.

If local services are not running, skip this step and note that live story planner smoke failure is expected outside the unit tests.

- [ ] **Step 7: Commit**

```bash
git add backend/scripts/run_ops_pilot_baseline.py backend/tests/test_run_ops_pilot_baseline.py
git commit -m "feat(hollowforge): wire ops pilot baseline checks"
```

## Final Verification Checklist

- [ ] `backend/scripts/run_ops_pilot_baseline.py` exists and is documented by its CLI help text.
- [ ] The pilot log template includes `adult provider resolution:`.
- [ ] `--dry-run` leaves the pilot log untouched.
- [ ] Timeout behavior is covered by unit tests.
- [ ] The runner continues after a failed check and reports all results.
- [ ] The story planner smoke summary is derived only from the stable labels named in the spec.
