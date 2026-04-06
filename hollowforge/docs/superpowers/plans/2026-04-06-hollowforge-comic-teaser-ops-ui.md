# HollowForge Comic Teaser Ops UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a teaser operations panel to `/comic` so operators can inspect recent teaser jobs, reconcile stale animation jobs, rerun teaser generation from the selected panel, and open the latest successful mp4 without leaving the workspace.

**Architecture:** Keep `/comic` as the operator hub and add one presentational `ComicTeaserOpsPanel` plus small state orchestration in `ComicStudio`. Reuse the existing animation job list and preset launch APIs, and add one bounded backend route that exposes the existing stale reconciliation service as a UI-safe action. Treat the panel as selected-asset-scoped within the selected panel context, and keep `fail then rerun` semantics unchanged.

**Tech Stack:** React 19, TanStack Query, TypeScript, FastAPI, existing animation/comic routes, pytest, Vitest, Testing Library

---

## Preconditions

- I'm using the writing-plans skill to create the implementation plan.
- Follow `@superpowers:test-driven-development` for each behavior change.
- Follow `@superpowers:verification-before-completion` before claiming any checkpoint.
- Treat [2026-04-06-hollowforge-comic-teaser-ops-ui-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/docs/superpowers/specs/2026-04-06-hollowforge-comic-teaser-ops-ui-design.md) as the source spec.
- Keep `/comic` as the only UI entry point in this phase; do not add a new route.
- Reuse existing animation APIs before adding any new backend persistence or new dashboards.
- Preserve `fail then rerun`; do not introduce resume semantics.
- Do not touch unrelated dirty files in the repo.

## File Map

### Backend

- Modify: `backend/app/models.py`
  - add a small typed response model for stale reconciliation summary
- Modify: `backend/app/routes/animation.py`
  - add `POST /api/v1/animation/reconcile-stale`
  - delegate to existing `reconcile_stale_animation_jobs()`
- Modify: `backend/tests/test_animation_reconciliation.py`
  - add route-level tests for the new reconcile endpoint

### Frontend API client

- Modify: `frontend/src/api/client.ts`
  - add `AnimationReconciliationResponse`
  - add `reconcileStaleAnimationJobs()`

### Frontend UI

- Create: `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`
  - present teaser jobs, failure summary, latest success link, reconcile/rerun buttons
- Modify: `frontend/src/pages/ComicStudio.tsx`
  - add teaser queries, mutations, derived selectors, and wire the new panel
- Modify: `frontend/src/pages/ComicStudio.test.tsx`
  - add UI tests for teaser jobs, reconcile action, rerun action, and latest mp4 link

### Docs

- Modify: `README.md`
  - add the new `/comic` teaser ops capability only if user-facing runtime behavior changes enough to merit mention
- Modify: `STATE.md`
  - add one concise note that `/comic` now exposes teaser reconcile/rerun ops if the implementation lands

## Task 1: Expose A Bounded Backend Reconcile Route

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/animation.py`
- Modify: `backend/tests/test_animation_reconciliation.py`

- [ ] **Step 1: Write the failing route tests**

Add route-level tests to `backend/tests/test_animation_reconciliation.py`.

Required coverage:

```python
async def test_reconcile_stale_animation_jobs_route_returns_summary(...):
    ...
    assert response.status_code == 200
    assert response.json() == {
        "checked": 1,
        "updated": 1,
        "failed_restart": 1,
        "completed": 0,
        "cancelled": 0,
        "skipped_unreachable": 0,
    }
```

```python
async def test_reconcile_stale_animation_jobs_route_maps_service_failure(...):
    ...
    assert response.status_code == 500
```

- [ ] **Step 2: Run the route tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py -k "reconcile_stale_animation_jobs_route"
```

Expected: FAIL because the route/model do not exist yet.

- [ ] **Step 3: Add the minimal backend surface**

Required implementation:

- add `AnimationReconciliationResponse` to `backend/app/models.py`
- add `POST /api/v1/animation/reconcile-stale` to `backend/app/routes/animation.py`
- route behavior:
  - call `reconcile_stale_animation_jobs()`
  - return the summary object directly
  - if the service raises, return `500`

Minimal model shape:

```python
class AnimationReconciliationResponse(BaseModel):
    checked: int
    updated: int
    failed_restart: int
    completed: int
    cancelled: int
    skipped_unreachable: int
```

- [ ] **Step 4: Run the route tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py -k "reconcile_stale_animation_jobs_route"
```

Expected: PASS.

- [ ] **Step 5: Commit the bounded reconcile route**

```bash
git add backend/app/models.py \
  backend/app/routes/animation.py \
  backend/tests/test_animation_reconciliation.py
git commit -m "feat(hollowforge): add animation reconcile route"
```

## Task 2: Add Frontend Animation Reconcile Client Surface

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Write the failing client usage test indirectly**

Do not add a separate client-only test file. Instead, add a minimal `ComicStudio.test.tsx` stub that will need the new client function:

```tsx
test('teaser ops reconcile action calls animation reconcile endpoint', async () => {
  ...
  expect(reconcileStaleAnimationJobs).toHaveBeenCalledTimes(1)
})
```

Mock import will fail until the client export exists.

- [ ] **Step 2: Run the targeted frontend test to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
```

Expected: FAIL because the new client export is missing.

- [ ] **Step 3: Add the client type and function**

Add to `frontend/src/api/client.ts`:

```ts
export interface AnimationReconciliationResponse {
  checked: number
  updated: number
  failed_restart: number
  completed: number
  cancelled: number
  skipped_unreachable: number
}

export async function reconcileStaleAnimationJobs(): Promise<AnimationReconciliationResponse> {
  const res = await api.post<AnimationReconciliationResponse>('/animation/reconcile-stale')
  return res.data
}
```

- [ ] **Step 4: Re-run the targeted frontend test**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
```

Expected: still FAIL, but now for the missing UI wiring rather than the client export.

- [ ] **Step 5: Commit the client surface once the UI test is green later**

Do not commit yet. This file should land with the UI wiring task.

## Task 3: Build The `ComicTeaserOpsPanel` Presentational Component

**Files:**
- Create: `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

- [ ] **Step 1: Write the failing panel rendering tests**

Add focused tests to `frontend/src/pages/ComicStudio.test.tsx`.

Required coverage:

```tsx
test('teaser ops shows latest failed job reason and latest successful mp4 link', async () => {
  ...
  expect(screen.getByText(/Teaser Ops For Selected Render/i)).toBeInTheDocument()
  expect(screen.getByText(/Worker restarted/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Open Latest MP4/i })).toHaveAttribute(
    'href',
    '/data/outputs/example.mp4',
  )
})
```

```tsx
test('teaser rerun action is disabled without a materialized selected asset', async () => {
  ...
  expect(screen.getByRole('button', { name: /Rerun Teaser From Selected Panel/i })).toBeDisabled()
})
```

- [ ] **Step 2: Run the frontend tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
```

Expected: FAIL because the panel/component does not exist yet.

- [ ] **Step 3: Create the presentational component**

Create `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`.

Required props:

- selected panel identity/context
- selected-asset-scoped animation jobs
- latest failed job
- latest successful job
- readiness message
- busy flags
- handlers:
  - `onReconcile()`
  - `onRerun()`

Required UI sections:

- title: `Teaser Ops For Selected Render`
- bounded recent jobs list
- latest failure summary
- latest success card with mp4 link
- `Reconcile Stale Animation Jobs` button
- `Rerun Teaser From Selected Panel` button

Keep this file presentational only. No query logic inside it.

- [ ] **Step 4: Re-run the frontend tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
```

Expected: still FAIL, but now for missing ComicStudio wiring/state.

- [ ] **Step 5: Commit later with ComicStudio wiring**

Do not commit yet. This component should land together with the page wiring.

## Task 4: Wire Teaser Ops Into `ComicStudio`

**Files:**
- Modify: `frontend/src/pages/ComicStudio.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`
- Create: `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`

- [ ] **Step 1: Finish the failing interaction tests**

Extend `frontend/src/pages/ComicStudio.test.tsx` with:

```tsx
test('teaser ops reconcile action shows summary after success', async () => {
  ...
  fireEvent.click(screen.getByRole('button', { name: /Reconcile Stale Animation Jobs/i }))
  await waitFor(() => expect(reconcileStaleAnimationJobs).toHaveBeenCalledTimes(1))
  expect(screen.getByText(/failed_restart/i)).toBeInTheDocument()
})
```

```tsx
test('teaser ops rerun launches a new animation job and refreshes selected render jobs', async () => {
  ...
  fireEvent.click(screen.getByRole('button', { name: /Rerun Teaser From Selected Panel/i }))
  await waitFor(() => expect(launchAnimationPreset).toHaveBeenCalledWith(
    'sdxl_ipadapter_microanim_v2',
    expect.objectContaining({
      generation_id: 'gen-selected',
      dispatch_immediately: true,
    }),
  ))
})
```

- [ ] **Step 2: Run the frontend tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
```

Expected: FAIL because the queries/mutations and derived teaser state are not wired yet.

- [ ] **Step 3: Add `ComicStudio` teaser state orchestration**

Required implementation in `frontend/src/pages/ComicStudio.tsx`:

- import and use:
  - `listAnimationJobs`
  - `launchAnimationPreset`
  - `reconcileStaleAnimationJobs`
  - `AnimationJobResponse`
- derive selected materialized asset + selected generation id
- add `selectedPanelTeaserJobsQuery`
  - enabled only when selected materialized asset exists
  - use `generation_id`
  - bounded recent list, e.g. `limit: 8`
- add `reconcileAnimationMutation`
- add `rerunTeaserMutation`
  - launch preset `sdxl_ipadapter_microanim_v2`
  - request:
    ```ts
    {
      generation_id: selectedGenerationId,
      dispatch_immediately: true,
      request_overrides: {},
    }
    ```
- derive:
  - latest failed job
  - latest successful job
  - latest mp4 URL (`/data/${output_path}` for relative paths)
  - readiness message
- render `ComicTeaserOpsPanel` in the right-side downstream operations area
- invalidate/refetch animation jobs after reconcile or rerun success

Do not add a preset selector or job-level rerun in this phase.

In the same task, update `frontend/src/pages/ComicStudio.test.tsx` mock wiring so
the page can load under test with the new imports. The existing
`vi.mock('../api/client')` factory must export:

- `listAnimationJobs`
- `launchAnimationPreset`
- `reconcileStaleAnimationJobs`

and the test file imports must include the same mocked functions.

- [ ] **Step 4: Run the frontend test file to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
```

Expected: PASS.

- [ ] **Step 5: Commit the teaser ops UI**

```bash
git add frontend/src/api/client.ts \
  frontend/src/components/comic/ComicTeaserOpsPanel.tsx \
  frontend/src/pages/ComicStudio.tsx \
  frontend/src/pages/ComicStudio.test.tsx
git commit -m "feat(hollowforge): add comic teaser ops panel"
```

## Task 5: Update Minimal Operator Docs

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`

- [ ] **Step 1: Write the failing docs assertions**

Add or extend an existing lightweight docs assertion in `frontend/src/pages/ComicStudio.test.tsx` or backend docs tests only if needed. If no good docs assertion point exists, skip a new docs-only test and keep this task documentation-only.

- [ ] **Step 2: Add minimal docs notes**

Update only the minimal operator-facing notes:

- `README.md`
  - mention that `/comic` now exposes teaser ops for selected render history, reconcile, and rerun
- `STATE.md`
  - add one concise resume note for `/comic` teaser ops

Do not broaden docs beyond this UI feature.

- [ ] **Step 3: Run a bounded verification sweep**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
npm run build

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py
```

Expected: all PASS.

- [ ] **Step 4: Commit the docs if changed**

```bash
git add README.md STATE.md
git commit -m "docs(hollowforge): document comic teaser ops ui"
```

## Task 6: Live UI-Safe Ops Verification

**Files:**
- No tracked files required unless a bug fix emerges

- [ ] **Step 1: Verify full targeted suites are green**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
npm run build

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py
```

Expected: PASS.

- [ ] **Step 2: Verify the bounded backend reconcile route live**

Run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/animation/reconcile-stale
```

Expected:

- response contains the six summary keys
- no route/runtime error

- [ ] **Step 3: Verify rerun route compatibility live**

Run the existing canonical teaser helper again as the live proof after the UI-safe route lands:

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
- non-empty `animation_job_id`
- non-empty `.mp4` `output_path`

- [ ] **Step 4: Commit only if tracked code changed during verification**
