# HollowForge Animation Stale Job Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically fail stale animation jobs after worker/backend restarts and preserve a clean fail-then-rerun operator flow for teaser jobs.

**Architecture:** Add stale cleanup at the worker startup boundary, add a backend reconciliation service that can mirror terminal worker state back into `animation_jobs`, and harden the backend animation callback so terminal states stay sticky. Keep operator recovery small by reusing the existing teaser helper and adding only a bounded reconciliation surface/script needed for ops verification.

**Tech Stack:** Python 3.12, FastAPI, SQLite, aiosqlite, httpx, pytest, existing HollowForge animation routes, existing lab451 animation worker

---

## Preconditions

- I'm using the writing-plans skill to create the implementation plan.
- Follow `@superpowers:test-driven-development` for every behavior change.
- Follow `@superpowers:verification-before-completion` before claiming any checkpoint.
- Treat [2026-04-05-hollowforge-animation-stale-job-reconciliation-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/docs/superpowers/specs/2026-04-05-hollowforge-animation-stale-job-reconciliation-design.md) as the source spec.
- Keep the recovery rule as `fail then rerun`; do not introduce resume-on-startup logic.
- Preserve the existing `animation_jobs.external_job_id == worker job UUID` contract.
- Do not touch unrelated dirty files in the repo.

## File Map

### Worker runtime

- Modify: `lab451-animation-worker/app/main.py`
  - add startup stale cleanup for `worker_jobs`
  - emit best-effort failed callbacks for stale rows
- Modify: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`
  - add worker startup cleanup tests and callback assertions

### Backend reconciliation

- Create: `backend/app/services/animation_reconciliation_service.py`
  - load stale backend animation jobs
  - query worker job state
  - normalize worker `output_url -> output_path`
  - apply terminal-state sync rules
- Modify: `backend/app/routes/animation.py`
  - make terminal animation states sticky in callback/update paths
  - optionally expose a bounded reconciliation route if needed by ops scripts
- Modify: `backend/app/main.py`
  - invoke the backend stale reconciliation pass during startup
- Create: `backend/tests/test_animation_reconciliation.py`
  - cover worker-state mirroring, 404 handling, unreachable-worker skip, and callback terminal guards

### Ops helper

- Create: `backend/scripts/reconcile_stale_animation_jobs.py`
  - bounded operator helper to invoke the backend reconciliation pass against a local backend
- Modify: `backend/tests/test_launch_comic_teaser_animation_smoke.py`
  - pin the rerun contract after stale failure if the helper needs a preflight reconcile hook

### Minimal docs

- Modify: `README.md`
  - add the bounded stale-reconcile command only if the runtime surface changes
- Modify: `STATE.md`
  - add the recovery note only if a new operator step or route is introduced

## Task 1: Add Worker Startup Stale Cleanup

**Files:**
- Modify: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`
- Modify: `lab451-animation-worker/app/main.py`

- [ ] **Step 1: Write the failing worker cleanup tests**

Add focused tests to `lab451-animation-worker/tests/test_comic_panel_still_worker.py`.

Required coverage:

```python
async def test_cleanup_stale_worker_jobs_marks_non_terminal_rows_failed(...):
    ...
    assert stale_row["status"] == "failed"
    assert stale_row["error_message"] == "Worker restarted"
    assert stale_row["completed_at"] is not None
```

```python
async def test_cleanup_stale_worker_jobs_sends_failed_callback_for_rows_with_callback(...):
    ...
    assert callback_payload["status"] == "failed"
    assert callback_payload["error_message"] == "Worker restarted"
```

- [ ] **Step 2: Run the worker tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/lab451-animation-worker
../backend/.venv/bin/python -m pytest -q tests/test_comic_panel_still_worker.py -k "cleanup_stale_worker_jobs"
```

Expected: FAIL because startup stale cleanup is not implemented yet.

- [ ] **Step 3: Implement minimal worker stale cleanup**

Add a helper in `lab451-animation-worker/app/main.py` with this shape:

```python
async def _cleanup_stale_worker_jobs() -> int:
    ...
```

Required behavior:

- select `worker_jobs` where `status IN ('queued', 'submitted', 'processing')`
- update each to:
  - `status = 'failed'`
  - `error_message = 'Worker restarted'`
  - `completed_at = now`
  - `updated_at = now`
- call `_notify_hollowforge(...)` best-effort for rows that have `callback_url`

Call this helper from `lifespan()` immediately after `init_db()`.

- [ ] **Step 4: Run the worker tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/lab451-animation-worker
../backend/.venv/bin/python -m pytest -q tests/test_comic_panel_still_worker.py -k "cleanup_stale_worker_jobs"
```

Expected: PASS.

- [ ] **Step 5: Commit the worker cleanup**

```bash
git add lab451-animation-worker/app/main.py \
  lab451-animation-worker/tests/test_comic_panel_still_worker.py
git commit -m "fix(worker): fail stale animation jobs on startup"
```

## Task 2: Add Backend Animation Reconciliation Service

**Files:**
- Create: `backend/tests/test_animation_reconciliation.py`
- Create: `backend/app/services/animation_reconciliation_service.py`

- [ ] **Step 1: Write the failing backend reconciliation tests**

Create `backend/tests/test_animation_reconciliation.py`.

Required coverage:

```python
async def test_reconcile_stale_animation_jobs_marks_failed_worker_rows_failed(...):
    ...
    assert job_row["status"] == "failed"
    assert job_row["error_message"] == "Worker restarted"
```

```python
async def test_reconcile_stale_animation_jobs_mirrors_completed_worker_output_path(...):
    ...
    assert job_row["status"] == "completed"
    assert job_row["output_path"] == "outputs/example.mp4"
```

```python
async def test_reconcile_stale_animation_jobs_skips_unreachable_worker(...):
    ...
    assert job_row["status"] == "processing"
```

```python
async def test_reconcile_stale_animation_jobs_treats_missing_worker_job_as_failed_restart(...):
    ...
    assert job_row["status"] == "failed"
    assert job_row["error_message"] == "Worker restarted"
```

- [ ] **Step 2: Run the backend reconciliation tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py
```

Expected: FAIL because the service file does not exist yet.

- [ ] **Step 3: Implement the reconciliation service**

Create `backend/app/services/animation_reconciliation_service.py`.

Required responsibilities:

- load backend `animation_jobs` where:
  - `executor_mode = 'remote_worker'`
  - `status IN ('queued', 'submitted', 'processing')`
  - `external_job_id` is not empty
- fetch worker state from `GET /api/v1/jobs/{external_job_id}`
- normalize worker terminal states into backend updates
- normalize worker `output_url` using the same path logic as callback updates:

```python
def _normalize_worker_output_path(output_url: str | None) -> str | None:
    ...
```

- return a summary object like:

```python
{
    "checked": ...,
    "updated": ...,
    "failed_restart": ...,
    "completed": ...,
    "cancelled": ...,
    "skipped_unreachable": ...,
}
```

Keep this file focused. Do not add generic orchestration abstractions.

- [ ] **Step 4: Run the backend reconciliation tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py
```

Expected: PASS.

- [ ] **Step 5: Commit the reconciliation service**

```bash
git add backend/app/services/animation_reconciliation_service.py \
  backend/tests/test_animation_reconciliation.py
git commit -m "fix(hollowforge): reconcile stale animation jobs"
```

## Task 3: Harden Backend Animation Terminal-State Guards

**Files:**
- Modify: `backend/tests/test_animation_reconciliation.py`
- Modify: `backend/app/routes/animation.py`

- [ ] **Step 1: Write the failing terminal-guard tests**

Extend `backend/tests/test_animation_reconciliation.py` with route-level or helper-level coverage.

Required cases:

```python
def test_animation_callback_failed_job_ignores_late_processing(...):
    ...
    assert response.json()["status"] == "failed"
```

```python
def test_animation_callback_completed_job_ignores_late_failed(...):
    ...
    assert response.json()["status"] == "completed"
```

```python
def test_animation_callback_cancelled_job_ignores_late_completed(...):
    ...
    assert response.json()["status"] == "cancelled"
```

- [ ] **Step 2: Run the guard tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py -k "late_"
```

Expected: FAIL because terminal-state precedence is not hardened yet.

- [ ] **Step 3: Implement sticky terminal-state behavior**

Modify `_apply_animation_job_update(...)` in `backend/app/routes/animation.py`.

Required rules:

- if current status is `completed`, ignore incoming `failed`, `queued`, `submitted`, `processing`, `cancelled`
- if current status is `failed`, ignore incoming `queued`, `submitted`, `processing`, `completed`
- if current status is `cancelled`, ignore incoming `queued`, `submitted`, `processing`, `completed`

Use a small helper instead of sprinkling branches inline, for example:

```python
def _should_preserve_terminal_animation_status(current_status: str, next_status: str) -> bool:
    ...
```

- [ ] **Step 4: Run the backend tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py
```

Expected: PASS.

- [ ] **Step 5: Commit the callback guard**

```bash
git add backend/app/routes/animation.py \
  backend/tests/test_animation_reconciliation.py
git commit -m "fix(hollowforge): keep terminal animation states sticky"
```

## Task 4: Wire Reconciliation Into Backend Startup And Ops Surface

**Files:**
- Modify: `backend/tests/test_animation_reconciliation.py`
- Modify: `backend/app/main.py`
- Create: `backend/scripts/reconcile_stale_animation_jobs.py`

- [ ] **Step 1: Write the failing startup/helper tests**

Add coverage for:

```python
async def test_backend_startup_invokes_animation_reconciliation(...):
    ...
```

```python
def test_reconcile_stale_animation_jobs_script_prints_summary(...):
    ...
```

- [ ] **Step 2: Run the tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py
```

Expected: FAIL because startup does not call the reconciliation service and the script does not exist.

- [ ] **Step 3: Implement backend startup hook and bounded ops helper**

Modify `backend/app/main.py`:

- import the reconciliation service
- call it during `lifespan()` after `init_db()` and before yielding
- log the summary in the same spirit as generation stale cleanup

Create `backend/scripts/reconcile_stale_animation_jobs.py`:

- local-backend-only guard
- call a small backend route if you introduced one, or directly reuse the existing route/service surface through HTTP
- print a bounded summary with:
  - checked
  - updated
  - failed_restart
  - completed
  - cancelled
  - skipped_unreachable

Do not create a broad admin surface.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py
```

Expected: PASS.

- [ ] **Step 5: Commit the startup/helper wiring**

```bash
git add backend/app/main.py \
  backend/scripts/reconcile_stale_animation_jobs.py \
  backend/tests/test_animation_reconciliation.py
git commit -m "fix(hollowforge): reconcile stale animation jobs on startup"
```

## Task 5: Prove The Operator Rerun Contract

**Files:**
- Modify: `backend/tests/test_launch_comic_teaser_animation_smoke.py`
- Modify: `README.md`
- Modify: `STATE.md`

- [ ] **Step 1: Write the failing rerun-contract test**

Add a bounded test to `backend/tests/test_launch_comic_teaser_animation_smoke.py` that proves a stale-failed job does not require a new helper surface and that rerun still returns a new animation job id.

Example shape:

```python
def test_main_succeeds_after_stale_failure_with_new_animation_job_id(...):
    ...
    assert "teaser_success: true" in captured.out
    assert "animation_job_id: anim-job-rerun" in captured.out
```

- [ ] **Step 2: Run the helper test to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py -k "stale_failure"
```

Expected: FAIL because the rerun contract is not pinned yet.

- [ ] **Step 3: Add only the minimal docs/runtime notes needed**

If the implementation added a new operator-facing command, document only that:

- `README.md`
  - add the bounded reconcile command near the teaser helper commands
- `STATE.md`
  - add one recovery note explaining `fail then rerun`

Do not widen docs beyond this bugfix.

- [ ] **Step 4: Run the helper tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
```

Expected: PASS.

- [ ] **Step 5: Commit the rerun contract/docs**

```bash
git add backend/tests/test_launch_comic_teaser_animation_smoke.py \
  README.md \
  STATE.md
git commit -m "docs(hollowforge): document fail-then-rerun animation recovery"
```

## Task 6: Live Verification Of Stale Failure And Clean Rerun

**Files:**
- No new tracked files required unless a verification note is explicitly requested

- [ ] **Step 1: Verify focused test suites are green**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/lab451-animation-worker
../backend/.venv/bin/python -m pytest -q tests/test_comic_panel_still_worker.py

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py tests/test_launch_comic_teaser_animation_smoke.py
```

Expected: all PASS.

- [ ] **Step 2: Reproduce stale cleanup against the known stale job**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python scripts/reconcile_stale_animation_jobs.py --base-url http://127.0.0.1:8000
```

Expected:

- stale backend job `267a0a8d-8ed2-42e6-a359-d61f8542bd0c` becomes terminal
- stale worker job `05c8901a-775a-4836-9b2e-77b4d8194080` is no longer the active truth

- [ ] **Step 3: Verify the stale job is failed**

Run:

```bash
curl -s http://127.0.0.1:8000/api/v1/animation/jobs/267a0a8d-8ed2-42e6-a359-d61f8542bd0c
curl -s http://127.0.0.1:8600/api/v1/jobs/05c8901a-775a-4836-9b2e-77b4d8194080
```

Expected:

- backend status is `failed`
- error mentions `Worker restarted` (or the equivalent terminal stale reason)

- [ ] **Step 4: Rerun the canonical teaser helper**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id 2d696b08-4899-4a3b-b499-adc37dbaa9f5 \
  --panel-index 0 \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --poll-sec 5 \
  --timeout-sec 1800
```

Expected:

- `teaser_success: true`
- `overall_success: true`
- a new `animation_job_id`
- a non-empty `.mp4` `output_path`

- [ ] **Step 5: Commit only if tracked docs/tests/code changed during verification**

If verification required tracked follow-up edits:

```bash
git add <exact files>
git commit -m "test(hollowforge): verify stale animation recovery"
```

If no tracked files changed, do not create a no-op commit.
