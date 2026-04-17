# HollowForge Comic Verification Suite Operator Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single operator-facing CLI entrypoint that runs the approved comic verification flow in the recommended order while preserving the existing script-level behavior and markers.

**Architecture:** Keep the current verification scripts as the source of truth for runtime behavior, and add one thin Python suite runner that validates stage selection, shells out to the existing scripts in order, and prints an additional suite-level summary for operators and automation.

**Tech Stack:** Python CLI scripts, subprocess orchestration, pytest, existing HollowForge comic verification entrypoints

---

## Scope Boundary

This plan implements the approved spec at:

- `docs/superpowers/specs/2026-04-17-hollowforge-comic-verification-suite-operator-entry-design.md`

This slice includes:

1. a new `run_comic_verification_suite.py` operator entrypoint
2. default stage order `smoke -> full -> remote`
3. single-stage flags `--smoke-only`, `--full-only`, `--remote-only`
4. default fail-fast behavior plus `--continue-on-failure`
5. suite-level summary markers for overall result and stage timings

This slice does **not** include:

- changing the internal verification logic of the existing smoke/full/remote scripts
- adding new render profiles or queue recipes
- storing suite results in the database
- merging the suite into `/production` or other operator surfaces
- animation verification orchestration

## Preconditions

- Follow `@superpowers:test-driven-development` while implementing each task.
- Follow `@superpowers:verification-before-completion` before claiming any checkpoint is complete.
- Keep reads/writes inside this HollowForge worktree.
- Do not touch the existing runtime artifacts under `data/`.

## File Structure

### New files

- `backend/scripts/run_comic_verification_suite.py`
  Thin operator-facing suite runner that shells out to the existing verification scripts and prints suite markers.
- `backend/tests/test_run_comic_verification_suite.py`
  Focused CLI regression tests for stage selection, fail-fast behavior, continue-on-failure, and summary markers.

### Existing files intentionally reused as subprocess targets

- `backend/scripts/launch_comic_one_panel_smoke.py`
- `backend/scripts/launch_comic_one_panel_verification.py`
- `backend/scripts/launch_comic_remote_render_smoke.py`

## Task 1: Lock the Suite Runner Contract with Failing Tests

**Files:**
- Create: `backend/tests/test_run_comic_verification_suite.py`

- [ ] **Step 1: Write a failing test for default stage order**

Create a test that loads the new runner module and monkeypatches its subprocess invocation helper so the suite can be asserted without launching real child processes.

The test should prove:

```python
assert exit_code == 0
assert calls == ["smoke", "full", "remote"]
assert "stages_requested: smoke,full,remote" in captured.out
assert "stages_completed: smoke,full,remote" in captured.out
assert "overall_success: true" in captured.out
```

- [ ] **Step 2: Write failing tests for single-stage selection flags**

Add coverage for:

```python
assert calls == ["smoke"]
assert calls == ["full"]
assert calls == ["remote"]
```

Also add a validation failure when multiple `--*-only` flags are combined:

```python
assert exit_code == 2
assert "choose only one stage selection flag" in captured.err
```

- [ ] **Step 3: Write failing tests for fail-fast and continue-on-failure**

Add one test where the `full` stage returns non-zero and confirm default fail-fast behavior:

```python
assert exit_code == 1
assert calls == ["smoke", "full"]
assert "failed_stage: full" in captured.out
assert "overall_success: false" in captured.out
```

Add another with `--continue-on-failure`:

```python
assert exit_code == 1
assert calls == ["smoke", "full", "remote"]
assert "continue_on_failure: true" in captured.out
assert "stages_completed: smoke,full,remote" in captured.out
```

- [ ] **Step 4: Write a failing test for missing child script paths**

Monkeypatch the script resolver so one target path does not exist and assert:

```python
assert exit_code == 1
assert "missing_stage_script: full" in captured.out
```

- [ ] **Step 5: Run the targeted test file and confirm it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge
python3 -m pytest backend/tests/test_run_comic_verification_suite.py -q
```

Expected: FAIL because the suite runner does not exist yet.

## Task 2: Implement the Operator Suite Runner

**Files:**
- Create: `backend/scripts/run_comic_verification_suite.py`
- Test: `backend/tests/test_run_comic_verification_suite.py`

- [ ] **Step 1: Implement stage metadata and selection parsing**

Create a small internal contract like:

```python
STAGE_ORDER = ("smoke", "full", "remote")
STAGE_SCRIPTS = {
    "smoke": "launch_comic_one_panel_smoke.py",
    "full": "launch_comic_one_panel_verification.py",
    "remote": "launch_comic_remote_render_smoke.py",
}
```

Add CLI parsing for:

- `--base-url` (required)
- `--smoke-only`
- `--full-only`
- `--remote-only`
- `--continue-on-failure`

Reject multiple `--*-only` flags together.

- [ ] **Step 2: Add a testable child-process invocation helper**

Implement a small helper that resolves the target script path relative to the current file and invokes:

```python
subprocess.run(
    [sys.executable, str(script_path), "--base-url", base_url],
    check=False,
)
```

Keep this helper isolated so tests can monkeypatch it cleanly.

- [ ] **Step 3: Add suite-level timing and summary markers**

For each requested stage, capture:

- exit code
- duration in seconds

Print suite markers including:

```python
suite_mode: comic_verification
base_url: ...
stages_requested: ...
stages_completed: ...
failed_stage: ...
continue_on_failure: true|false
stage_smoke_exit_code: ...
stage_smoke_duration_sec: ...
overall_success: true|false
total_duration_sec: ...
```

Requirements:

- default behavior is fail-fast
- `--continue-on-failure` keeps running after failures
- final process exit code is `0` only when all requested stages succeed

- [ ] **Step 4: Handle missing child scripts explicitly**

Before running a stage, resolve the script path and check `exists()`. If missing:

- report the stage as failed in suite markers
- set `failed_stage`
- stop immediately unless `--continue-on-failure` is enabled

- [ ] **Step 5: Run the targeted suite tests and confirm they pass**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge
python3 -m pytest backend/tests/test_run_comic_verification_suite.py -q
```

Expected: PASS.

## Task 3: Verify the Runner Against the Existing Verification Stack

**Files:**
- Modify if needed: `backend/scripts/run_comic_verification_suite.py`

- [ ] **Step 1: Run the focused verification regression cluster**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge
python3 -m pytest \
  backend/tests/test_launch_comic_one_panel_smoke.py \
  backend/tests/test_launch_comic_one_panel_verification.py \
  backend/tests/test_launch_comic_remote_render_smoke.py \
  backend/tests/test_run_comic_verification_suite.py -q
```

Expected: PASS. This proves the new suite entrypoint did not regress the existing verification contracts.

- [ ] **Step 2: Run the real CLI suite against the active local stack**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge
python3 backend/scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8012
```

Expected:

- smoke passes first
- full verification passes second
- remote render smoke passes last
- suite summary prints `overall_success: true`

- [ ] **Step 3: Record any environment-specific blockers instead of weakening the runner**

If the live suite run fails because the local stack is not available, record the exact blocking layer and keep the suite contract intact. Do not silently convert live failures into green test outcomes.

## Completion Criteria

This implementation is complete when:

1. `backend/scripts/run_comic_verification_suite.py` exists and is operator-usable.
2. Default execution order is `smoke -> full -> remote`.
3. Single-stage flags and `--continue-on-failure` behave as designed.
4. Suite-level summary markers are printed deterministically.
5. Focused pytest coverage passes.
6. A live CLI run is executed successfully against the current local stack, or a precise environment blocker is documented.
