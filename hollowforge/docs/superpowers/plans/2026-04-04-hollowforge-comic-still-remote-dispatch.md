# HollowForge Comic Still Remote Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a remote production lane for comic panel still renders while preserving the current local one-panel verification flow and existing page-export lineage.

**Architecture:** Reuse `generations` as lineage shells, add a dedicated `comic_render_jobs` execution layer, and extend the existing worker envelope with a `comic_panel_still` job type. Keep `/api/v1/comic/panels/{panel_id}/queue-renders` as the canonical entry point, default it to local preview behavior, and stage `execution_mode=remote_worker` as a contract-only field until Task 2 enables remote dispatch/callback materialization.

**Tech Stack:** FastAPI, SQLite/aiosqlite migrations, Pydantic v2, existing `GenerationService`, React 19, TypeScript, TanStack Query, pytest, Vitest, `lab451-animation-worker`, ComfyUI

---

## Preconditions

- I'm using the writing-plans skill to create the implementation plan.
- Follow `@superpowers:test-driven-development` for each task.
- Follow `@superpowers:verification-before-completion` before claiming any checkpoint.
- Treat [2026-04-04-hollowforge-comic-still-remote-dispatch-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/docs/superpowers/specs/2026-04-04-hollowforge-comic-still-remote-dispatch-design.md) as the source spec.
- Do not remove or weaken the existing local one-panel verification lane.
- Do not merge comic still execution into the local generation worker loop.
- Keep animation remote execution behavior backward compatible.

## File Map

### Backend schema and models

- Create: `backend/migrations/032_comic_remote_render_jobs.sql`
  - adds `comic_render_jobs`
- Modify: `backend/app/models.py`
  - adds comic render job models and queue response fields
- Modify: `backend/app/routes/comic.py`
  - adds `execution_mode` to queue route, render-job list route, and callback route

### Backend services

- Modify: `backend/app/services/comic_render_service.py`
  - splits local preview vs remote production queue path
- Create: `backend/app/services/comic_render_dispatch_service.py`
  - builds remote comic still payloads and submits them to the worker
- Modify: `backend/app/services/generation_service.py`
  - add a minimal helper to create generation lineage shells without enqueuing local work

### Backend tests and scripts

- Modify: `backend/tests/test_comic_render_service.py`
- Modify: `backend/tests/test_comic_routes.py`
- Create: `backend/tests/test_comic_render_dispatch_service.py`
- Create: `backend/tests/test_comic_remote_render_callback.py`
- Create: `backend/tests/test_comic_remote_render_scripts.py`
- Create: `backend/scripts/check_comic_remote_render_preflight.py`
- Create: `backend/scripts/launch_comic_remote_render_smoke.py`

### Worker

- Modify: `lab451-animation-worker/app/models.py`
  - make `source_image_url` optional for still jobs and accept `comic_panel_still`
- Modify: `lab451-animation-worker/app/executors.py`
  - add text-to-image execution path for comic still jobs
- Modify: `lab451-animation-worker/app/main.py`
  - route still jobs through the new executor branch
- Create: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`
- Modify: `lab451-animation-worker/README.md`
  - document comic still payloads and runbook

### Frontend

- Modify: `frontend/src/api/client.ts`
  - add execution mode and comic render job types
- Modify: `frontend/src/pages/ComicStudio.tsx`
  - add local/remote queue selection and status polling
- Modify: `frontend/src/components/comic/ComicPanelBoard.tsx`
  - show execution lane, pending job counts, and remote failures
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

### Docs

- Modify: `docs/HOLLOWFORGE_COMIC_LOCAL_BENCHMARK_20260404.md`
  - point to the remote dispatch follow-up
- Modify: `README.md`
  - publish preflight and smoke commands
- Modify: `STATE.md`
  - update resume notes and current operating split

## Task 1: Add Comic Remote Render Persistence And Route Contracts

**Files:**
- Create: `backend/migrations/032_comic_remote_render_jobs.sql`
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/comic.py`
- Modify: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write the failing schema and route tests**

```python
def test_queue_comic_panel_renders_accepts_remote_execution_mode(client):
    response = client.post(
        f"/api/v1/comic/panels/{panel_id}/queue-renders",
        params={"candidate_count": 3, "execution_mode": "remote_worker"},
    )
    assert response.status_code == 501
    assert response.json()["detail"] == "Comic remote worker execution mode is not implemented yet"
```

```python
async def test_comic_remote_render_jobs_table_exists():
    await init_db()
    async with get_db() as db:
        columns = {
            row["name"]
            for row in await (
                await db.execute("PRAGMA table_info(comic_render_jobs)")
            ).fetchall()
        }
    assert {"id", "scene_panel_id", "render_asset_id", "generation_id", "status"} <= columns
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/backend
PYTHONPATH=. ./.venv/bin/pytest tests/test_comic_routes.py -q
```

Expected: FAIL because the migration, route enum, and response fields do not exist.

- [ ] **Step 3: Add the migration and contract models**

Required shape:

```sql
CREATE TABLE IF NOT EXISTS comic_render_jobs (
    id TEXT PRIMARY KEY,
    scene_panel_id TEXT NOT NULL REFERENCES comic_scene_panels(id) ON DELETE CASCADE,
    render_asset_id TEXT NOT NULL REFERENCES comic_panel_render_assets(id) ON DELETE CASCADE,
    generation_id TEXT NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    request_index INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    target_tool TEXT NOT NULL,
    executor_mode TEXT NOT NULL,
    executor_key TEXT NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT,
    external_job_id TEXT,
    external_job_url TEXT,
    output_path TEXT,
    error_message TEXT,
    submitted_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Model additions:

- `ComicRenderExecutionMode = Literal["local_preview", "remote_worker"]`
- `ComicRenderJobResponse`
- extend `ComicPanelRenderQueueResponse` with:
  - `execution_mode`
  - `materialized_asset_count`
  - `pending_render_job_count`
  - `remote_job_count`

- [ ] **Step 4: Run the route test again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/backend
PYTHONPATH=. ./.venv/bin/pytest tests/test_comic_routes.py -q
```

Expected: PASS for the local preview contract surface, while `remote_worker` remains rejected with `501`.

- [ ] **Step 5: Commit the persistence and route contract**

```bash
git add backend/migrations/032_comic_remote_render_jobs.sql \
  backend/app/models.py \
  backend/app/routes/comic.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): add comic remote render job contracts"
```

## Task 2: Implement Remote Queueing With Generation Lineage Shells

**Files:**
- Modify: `backend/app/services/comic_render_service.py`
- Create: `backend/app/services/comic_render_dispatch_service.py`
- Modify: `backend/app/services/generation_service.py`
- Modify: `backend/tests/test_comic_render_service.py`
- Create: `backend/tests/test_comic_render_dispatch_service.py`

- [ ] **Step 1: Write the failing service tests**

```python
async def test_queue_panel_render_candidates_remote_creates_generation_shells_and_jobs():
    response = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="remote_worker",
    )
    assert response.execution_mode == "remote_worker"
    assert response.remote_job_count == 3
    assert response.pending_render_job_count == 3
    assert response.materialized_asset_count == 0
```

```python
async def test_dispatch_comic_render_jobs_builds_worker_payload():
    payload = build_comic_remote_worker_payload(job, generation, render_asset, panel_context)
    assert payload["target_tool"] == "comic_panel_still"
    assert payload["generation_id"] == generation["id"]
    assert payload["request_json"]["comic"]["render_asset_id"] == render_asset["id"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/backend
PYTHONPATH=. ./.venv/bin/pytest tests/test_comic_render_service.py tests/test_comic_render_dispatch_service.py -q
```

Expected: FAIL because remote queueing and dispatch do not exist.

- [ ] **Step 3: Add generation shell creation without local worker enqueue**

Required behavior:

- add a `GenerationService` helper that inserts `generations` rows with:
  - `status="queued"`
  - `source_id=<comic render source id derived from _render_request_source_id(panel_id, candidate_count, execution_mode)>`
  - full prompt/checkpoint/size lineage fields
- do not enqueue these rows onto the local background worker

- [ ] **Step 4: Add remote queue branch**

Required behavior:

- `queue_panel_render_candidates(..., execution_mode="remote_worker")` must:
  - reuse `_build_generation_request()`
  - create generation shells
  - create `comic_panel_render_assets`
  - create `comic_render_jobs`
  - dispatch the jobs to the remote worker
  - return placeholder assets plus remote job counts
- local preview branch must remain unchanged

- [ ] **Step 5: Run the service tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/backend
PYTHONPATH=. ./.venv/bin/pytest tests/test_comic_render_service.py tests/test_comic_render_dispatch_service.py -q
```

Expected: PASS with both local and remote queue branches covered.

- [ ] **Step 6: Commit the remote queue implementation**

```bash
git add backend/app/services/comic_render_service.py \
  backend/app/services/comic_render_dispatch_service.py \
  backend/app/services/generation_service.py \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_dispatch_service.py
git commit -m "feat(hollowforge): queue comic still renders remotely"
```

## Task 3: Add Remote Callback Materialization

**Files:**
- Modify: `backend/app/routes/comic.py`
- Modify: `backend/app/services/comic_render_service.py`
- Create: `backend/tests/test_comic_remote_render_callback.py`
- Modify: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write the failing callback tests**

```python
def test_comic_render_job_callback_materializes_generation_and_asset(client):
    response = client.post(
        f"/api/v1/comic/render-jobs/{job_id}/callback",
        headers={"Authorization": "Bearer test-token"},
        json={
            "status": "completed",
            "external_job_id": "worker-123",
            "external_job_url": "https://worker/jobs/worker-123",
            "output_path": "images/remote/panel-01.png",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
```

```python
async def test_completed_callback_updates_generation_image_path_and_asset_storage():
    job = await get_comic_render_job(job_id)
    assert job["output_path"] == "images/remote/panel-01.png"
    generation = await get_generation(job["generation_id"])
    assert generation["image_path"] == "images/remote/panel-01.png"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/backend
PYTHONPATH=. ./.venv/bin/pytest tests/test_comic_remote_render_callback.py tests/test_comic_routes.py -q
```

Expected: FAIL because the callback route and transactional updates do not exist.

- [ ] **Step 3: Implement callback handling**

Required behavior:

- add `POST /api/v1/comic/render-jobs/{job_id}/callback`
- enforce bearer-token auth
- update `comic_render_jobs` and `generations` in one transaction
- on `completed`, set:
  - `comic_render_jobs.output_path`
  - `generations.image_path`
  - `comic_panel_render_assets.storage_path`
- on `failed` or `cancelled`, preserve the placeholder asset row and write the error

- [ ] **Step 4: Add `GET /api/v1/comic/panels/{panel_id}/render-jobs`**

Required behavior:

- list jobs by panel ordered newest-first
- expose job status, external job URL, output path, and errors
- let `/comic` poll a selected panel without reloading the entire episode

- [ ] **Step 5: Run the callback and route tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/backend
PYTHONPATH=. ./.venv/bin/pytest tests/test_comic_remote_render_callback.py tests/test_comic_routes.py -q
```

Expected: PASS with callback-driven materialization and panel job listing.

- [ ] **Step 6: Commit the callback flow**

```bash
git add backend/app/routes/comic.py \
  backend/app/services/comic_render_service.py \
  backend/tests/test_comic_remote_render_callback.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): materialize remote comic renders via callback"
```

## Task 4: Extend The Worker For `comic_panel_still`

**Files:**
- Modify: `lab451-animation-worker/app/models.py`
- Modify: `lab451-animation-worker/app/executors.py`
- Modify: `lab451-animation-worker/app/main.py`
- Create: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`
- Modify: `lab451-animation-worker/README.md`

- [ ] **Step 1: Write the failing worker tests or minimal verification harness**

If no worker test suite exists yet, create a focused verification module:

```python
def test_worker_accepts_comic_panel_still_payload():
    payload = WorkerJobCreate(
        hollowforge_job_id="job-1",
        generation_id="gen-1",
        target_tool="comic_panel_still",
        executor_mode="remote_worker",
        executor_key="comic_still_worker",
        request_json={"backend_family": "sdxl_still", "still_generation": {"prompt": "x"}},
    )
    assert payload.target_tool == "comic_panel_still"
```

- [ ] **Step 2: Run the worker verification to see it fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/lab451-animation-worker
python -m pytest tests/test_comic_panel_still_worker.py -q
```

Expected: FAIL or no coverage yet for comic still jobs.

- [ ] **Step 3: Add the still executor branch**

Required behavior:

- allow `source_image_url` to be optional for `comic_panel_still`
- accept `target_tool="comic_panel_still"`
- branch in the executor to a text-to-image workflow
- write a standard output image artifact into worker data outputs
- callback with `status`, `external_job_id/url`, and `output_path`

- [ ] **Step 4: Run the worker verification again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/lab451-animation-worker
python -m pytest tests/test_comic_panel_still_worker.py -q
```

Expected: PASS for the comic still payload acceptance and executor branch.

- [ ] **Step 5: Commit the worker extension**

```bash
git add lab451-animation-worker/app/models.py \
  lab451-animation-worker/app/executors.py \
  lab451-animation-worker/app/main.py \
  lab451-animation-worker/tests/test_comic_panel_still_worker.py \
  lab451-animation-worker/README.md
git commit -m "feat(worker): support comic panel still jobs"
```

## Task 5: Add `/comic` Remote Production Controls

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ComicStudio.tsx`
- Modify: `frontend/src/components/comic/ComicPanelBoard.tsx`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

- [ ] **Step 1: Write the failing frontend test**

```tsx
it('queues remote production renders for the selected panel', async () => {
  render(<ComicStudio />)
  await user.click(screen.getByRole('button', { name: /queue remote production renders/i }))
  expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
    candidate_count: 3,
    execution_mode: 'remote_worker',
  })
})
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx
```

Expected: FAIL because the UI only exposes one queue button and no remote status.

- [ ] **Step 3: Add UI mode split and job polling**

Required behavior:

- add local preview and remote production queue buttons
- thread `execution_mode` through `queueComicPanelRenders()`
- poll `GET /comic/panels/{panel_id}/render-jobs` for the selected panel when remote jobs exist
- show:
  - current execution lane
  - pending remote job count
  - latest failure message
  - external job link when present

- [ ] **Step 4: Run the frontend test, lint, and build**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx
npm run lint
npm run build
```

Expected: PASS, lint clean, build success.

- [ ] **Step 5: Commit the operator UI**

```bash
git add frontend/src/api/client.ts \
  frontend/src/pages/ComicStudio.tsx \
  frontend/src/components/comic/ComicPanelBoard.tsx \
  frontend/src/pages/ComicStudio.test.tsx
git commit -m "feat(hollowforge): add comic remote render controls"
```

## Task 6: Add Preflight, Smoke, And Doc Updates

**Files:**
- Create: `backend/tests/test_comic_remote_render_scripts.py`
- Create: `backend/scripts/check_comic_remote_render_preflight.py`
- Create: `backend/scripts/launch_comic_remote_render_smoke.py`
- Modify: `docs/HOLLOWFORGE_COMIC_LOCAL_BENCHMARK_20260404.md`
- Modify: `README.md`
- Modify: `STATE.md`

- [ ] **Step 1: Write the failing smoke-script test or minimal script assertions**

```python
def test_comic_remote_render_smoke_requires_local_backend_url():
    with pytest.raises(SystemExit):
        main(["--base-url", "https://remote.example.com"])
```

- [ ] **Step 2: Run the script tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/backend
PYTHONPATH=. ./.venv/bin/pytest tests/test_comic_remote_render_scripts.py -q
```

Expected: FAIL because the new preflight and smoke helpers do not exist yet.

- [ ] **Step 3: Implement preflight and smoke scripts**

Required behavior:

- preflight checks:
  - local backend reachable
  - worker reachable
  - callback base URL configured
  - required worker token configured when auth is enabled
- smoke flow:
  - import one short comic episode
  - queue remote still renders for one panel
  - poll callback-driven materialization
  - assert at least one real selected asset is materialized

- [ ] **Step 4: Run the canonical backend verification bundle**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/backend
PYTHONPATH=. ./.venv/bin/pytest tests/test_comic_render_service.py \
  tests/test_comic_render_dispatch_service.py \
  tests/test_comic_remote_render_callback.py \
  tests/test_comic_routes.py \
  tests/test_launch_comic_one_panel_verification.py \
  tests/test_launch_comic_four_panel_benchmark.py -q
```

Expected: PASS for the backend comic render boundary.

- [ ] **Step 5: Commit docs and scripts**

```bash
git add backend/scripts/check_comic_remote_render_preflight.py \
  backend/scripts/launch_comic_remote_render_smoke.py \
  backend/tests/test_comic_remote_render_scripts.py \
  docs/HOLLOWFORGE_COMIC_LOCAL_BENCHMARK_20260404.md \
  README.md \
  STATE.md
git commit -m "docs(hollowforge): publish comic remote render runbook"
```
