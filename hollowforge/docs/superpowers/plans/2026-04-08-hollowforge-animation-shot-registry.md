# HollowForge Animation Shot Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a library-friendly shot registry for comic teaser derivatives so `/comic` can track the current selected render as one `animation_shot`, accumulate teaser `variants` under it, and keep launch/callback/reconcile behavior intact.

**Architecture:** Keep `selected_render_asset` as the source truth, add additive SQLite persistence for `animation_shots` and `animation_shot_variants`, and isolate linkage logic in a small registry service instead of growing `animation.py` further. Preserve the existing animation launch surface and stale-reconcile flow, then switch `/comic` from `generation_id -> animation_jobs` history to `current shot + recent variants` for the selected render.

**Tech Stack:** SQLite migrations, FastAPI, Pydantic, existing animation/comic services, pytest, React 19, TypeScript, TanStack Query, Vitest, Testing Library

---

## Preconditions

- I'm using the writing-plans skill to create the implementation plan.
- Follow `@superpowers:test-driven-development` for each behavior change.
- Follow `@superpowers:verification-before-completion` before claiming any checkpoint.
- Treat [2026-04-08-hollowforge-animation-shot-registry-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/docs/superpowers/specs/2026-04-08-hollowforge-animation-shot-registry-design.md) as the source spec.
- Preserve current `/comic` teaser ops UX; no new route/page in this phase.
- Preserve `fail then rerun`; do not introduce resume semantics.
- New launches only populate the registry. Historical teaser jobs are out of scope for backfill in this phase.
- Do not touch unrelated dirty files already present in the repo.

## File Map

### Schema and backend persistence

- Create: `backend/migrations/033_animation_shot_registry.sql`
  - add `animation_shots`
  - add `animation_shot_variants`
  - add indexes and uniqueness constraints
- Create: `backend/app/services/animation_shot_registry.py`
  - resolve/create current shot
  - create shot variants
  - synchronize variant state from animation job terminal updates
  - query current shot with recent variants
- Modify: `backend/app/models.py`
  - add Pydantic response models for shot and shot variants
- Modify: `backend/tests/test_comic_schema.py`
  - add schema contract coverage for the new tables
- Create: `backend/tests/test_animation_shot_registry.py`
  - repository/service coverage for shot resolution and variant lifecycle

### Animation launch / callback / reconcile integration

- Modify: `backend/app/routes/animation.py`
  - attach shot/variant linkage to preset launch
  - expose a current-shot read route
  - update callback path to sync linked variants
- Modify: `backend/app/services/animation_reconciliation_service.py`
  - update linked variants when stale jobs are failed/completed/cancelled
- Modify: `backend/tests/test_animation_reconciliation.py`
  - add shot-variant synchronization assertions
- Modify: `backend/tests/test_launch_comic_teaser_animation_smoke.py`
  - extend helper expectations to include shot/variant markers
- Modify: `backend/scripts/launch_comic_teaser_animation_smoke.py`
  - print resolved `animation_shot_id` / `animation_shot_variant_id`

### Frontend client and `/comic` UI

- Modify: `frontend/src/api/client.ts`
  - add shot registry response types
  - add `getCurrentAnimationShot()` client helper
- Modify: `frontend/src/pages/ComicStudio.tsx`
  - replace generation-id-only teaser history query with current-shot query
  - keep reconcile/rerun mutations
  - wire latest success/failure/variant list from the shot response
- Modify: `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`
  - render current shot summary and recent variants
- Modify: `frontend/src/pages/ComicStudio.test.tsx`
  - assert current shot rendering, variant history, and rerun refresh behavior

### Docs

- Modify: `README.md`
  - note that `/comic` teaser ops now tracks `Current Teaser Shot` plus variants
- Modify: `STATE.md`
  - replace the “next bounded extension” note with the landed registry scope once complete
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`
  - change teaser ops terminology from job history to shot/variant history

## Task 1: Add The Additive Shot Registry Schema

**Files:**
- Create: `backend/migrations/033_animation_shot_registry.sql`
- Modify: `backend/tests/test_comic_schema.py`

- [ ] **Step 1: Write the failing schema assertions**

Add failing coverage to `backend/tests/test_comic_schema.py`.

Required assertions:

```python
assert "animation_shots" in table_names
assert "animation_shot_variants" in table_names
```

```python
assert {"id", "selected_render_asset_id", "generation_id", "is_current"} <= set(shot_columns)
assert {"id", "animation_shot_id", "animation_job_id", "preset_id", "status"} <= set(variant_columns)
```

- [ ] **Step 2: Run the schema test to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_schema.py -k "animation_shot"
```

Expected: FAIL because the migration has not been added.

- [ ] **Step 3: Add the migration**

Create `backend/migrations/033_animation_shot_registry.sql`.

Required SQL skeleton:

```sql
CREATE TABLE IF NOT EXISTS animation_shots (
    id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    episode_id TEXT NOT NULL REFERENCES comic_episodes(id) ON DELETE CASCADE,
    scene_panel_id TEXT NOT NULL REFERENCES comic_scene_panels(id) ON DELETE CASCADE,
    selected_render_asset_id TEXT NOT NULL REFERENCES comic_panel_render_assets(id) ON DELETE CASCADE,
    generation_id TEXT NOT NULL REFERENCES generations(id) ON DELETE SET NULL,
    is_current INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS animation_shot_variants (
    id TEXT PRIMARY KEY,
    animation_shot_id TEXT NOT NULL REFERENCES animation_shots(id) ON DELETE CASCADE,
    animation_job_id TEXT NOT NULL REFERENCES animation_jobs(id) ON DELETE CASCADE,
    preset_id TEXT NOT NULL,
    launch_reason TEXT NOT NULL,
    status TEXT NOT NULL,
    output_path TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
```

Required indexes:

- unique on `animation_shots(selected_render_asset_id)`
- unique on `animation_shot_variants(animation_job_id)`
- recent-lookup index on `animation_shot_variants(animation_shot_id, created_at DESC)`

- [ ] **Step 4: Re-run the schema tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_schema.py -k "animation_shot"
```

Expected: PASS.

- [ ] **Step 5: Commit the migration**

```bash
git add backend/migrations/033_animation_shot_registry.sql \
  backend/tests/test_comic_schema.py
git commit -m "feat(hollowforge): add animation shot registry schema"
```

## Task 2: Implement Shot Resolution And Variant Persistence

**Files:**
- Create: `backend/app/services/animation_shot_registry.py`
- Modify: `backend/app/models.py`
- Create: `backend/tests/test_animation_shot_registry.py`

- [ ] **Step 1: Write the failing service tests**

Create `backend/tests/test_animation_shot_registry.py`.

Required coverage:

```python
async def test_resolve_current_shot_reuses_same_selected_render(...):
    first = await resolve_or_create_current_animation_shot(...)
    second = await resolve_or_create_current_animation_shot(...)
    assert second.id == first.id
```

```python
async def test_resolve_current_shot_creates_new_row_when_selected_render_changes(...):
    first = await resolve_or_create_current_animation_shot(selected_render_asset_id="asset-a", ...)
    second = await resolve_or_create_current_animation_shot(selected_render_asset_id="asset-b", ...)
    assert second.id != first.id
```

```python
async def test_create_variant_links_job_and_preset(...):
    variant = await create_animation_shot_variant(...)
    assert variant.animation_job_id == "job-1"
    assert variant.preset_id == "sdxl_ipadapter_microanim_v2"
```

- [ ] **Step 2: Run the service tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_shot_registry.py
```

Expected: FAIL because the service and models do not exist.

- [ ] **Step 3: Add minimal models and service**

In `backend/app/models.py`, add:

- `AnimationShotResponse`
- `AnimationShotVariantResponse`
- `AnimationCurrentShotResponse`

Minimal response shapes:

```python
class AnimationShotVariantResponse(BaseModel):
    id: str
    animation_shot_id: str
    animation_job_id: str
    preset_id: str
    launch_reason: str
    status: str
    output_path: str | None = None
    error_message: str | None = None
    created_at: str
    completed_at: str | None = None
```

In `backend/app/services/animation_shot_registry.py`, implement:

- `resolve_or_create_current_animation_shot(...)`
- `create_animation_shot_variant(...)`
- `update_animation_shot_variant_from_job(...)`
- `get_current_animation_shot(...)`

Use `selected_render_asset_id` as the identity key.

- [ ] **Step 4: Re-run the service tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_shot_registry.py
```

Expected: PASS.

- [ ] **Step 5: Commit the registry service layer**

```bash
git add backend/app/models.py \
  backend/app/services/animation_shot_registry.py \
  backend/tests/test_animation_shot_registry.py
git commit -m "feat(hollowforge): add animation shot registry service"
```

## Task 3: Link Launch, Callback, Reconcile, And Teaser Smoke To The Registry

**Files:**
- Modify: `backend/app/routes/animation.py`
- Modify: `backend/app/services/animation_reconciliation_service.py`
- Modify: `backend/scripts/launch_comic_teaser_animation_smoke.py`
- Modify: `backend/tests/test_animation_reconciliation.py`
- Modify: `backend/tests/test_launch_comic_teaser_animation_smoke.py`

- [ ] **Step 1: Write failing linkage tests**

Add route/service assertions that a teaser launch creates a shot variant and terminal updates sync it.

Required tests:

```python
async def test_launch_animation_preset_creates_shot_variant_for_selected_render(...):
    response = await client.post("/api/v1/animation/presets/sdxl_ipadapter_microanim_v2/launch", json=payload)
    assert response.status_code == 200
    assert variant_row["animation_job_id"] == response.json()["animation_job"]["id"]
```

```python
async def test_reconcile_stale_animation_jobs_marks_linked_variant_failed(...):
    ...
    assert variant_row["status"] == "failed"
    assert variant_row["error_message"] == "Worker restarted"
```

```python
def test_teaser_smoke_prints_shot_registry_markers(...):
    assert "animation_shot_id:" in output
    assert "animation_shot_variant_id:" in output
```

- [ ] **Step 2: Run the targeted backend tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_animation_reconciliation.py \
  tests/test_launch_comic_teaser_animation_smoke.py \
  -k "shot_variant or shot_registry or teaser_smoke"
```

Expected: FAIL because launch/callback/reconcile do not update the registry yet.

- [ ] **Step 3: Add minimal linkage**

In `backend/app/routes/animation.py`:

- after animation preset launch succeeds, resolve/create the current shot using:
  - `scene_panel_id`
  - `selected_render_asset_id`
  - `generation_id`
  - `episode_id`
- create one variant row linked to the new `animation_job`
- add `current_shot_id` and `current_shot_variant_id` to the launch response only if needed for helper/UI wiring

In `backend/app/services/animation_reconciliation_service.py`:

- after `_update_animation_job(...)`, sync the linked shot variant status/output/error

In callback handling:

- update linked variant on `completed`, `failed`, or `cancelled`
- do not mutate variants on non-terminal callback no-ops

In `backend/scripts/launch_comic_teaser_animation_smoke.py`:

- include `animation_shot_id`
- include `animation_shot_variant_id`

- [ ] **Step 4: Re-run the targeted backend tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_animation_reconciliation.py \
  tests/test_launch_comic_teaser_animation_smoke.py \
  -k "shot_variant or shot_registry or teaser_smoke"
```

Expected: PASS.

- [ ] **Step 5: Commit the backend linkage**

```bash
git add backend/app/routes/animation.py \
  backend/app/services/animation_reconciliation_service.py \
  backend/scripts/launch_comic_teaser_animation_smoke.py \
  backend/tests/test_animation_reconciliation.py \
  backend/tests/test_launch_comic_teaser_animation_smoke.py
git commit -m "feat(hollowforge): link teaser jobs to animation shots"
```

## Task 4: Expose A Current-Shot Read Surface

**Files:**
- Modify: `backend/app/routes/animation.py`
- Modify: `backend/tests/test_animation_reconciliation.py`
- Modify: `backend/app/models.py`

- [ ] **Step 1: Write the failing route test**

Add coverage for a bounded current-shot query.

Required test:

```python
async def test_get_current_animation_shot_returns_recent_variants_for_selected_render(...):
    response = await client.get(
        "/api/v1/animation/shots/current",
        params={
            "scene_panel_id": "panel-1",
            "selected_render_asset_id": "asset-1",
        },
    )
    assert response.status_code == 200
    assert response.json()["shot"]["selected_render_asset_id"] == "asset-1"
    assert len(response.json()["variants"]) == 2
```

- [ ] **Step 2: Run the targeted route test to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py -k "current_animation_shot"
```

Expected: FAIL because the route does not exist.

- [ ] **Step 3: Add the bounded route**

Add to `backend/app/routes/animation.py`:

```python
@router.get("/shots/current", response_model=AnimationCurrentShotResponse)
async def get_current_animation_shot(
    scene_panel_id: str,
    selected_render_asset_id: str,
    limit: int = Query(default=8, ge=1, le=20),
):
    ...
```

Behavior:

- resolve by `selected_render_asset_id`
- verify the row belongs to the requested `scene_panel_id`
- return one current shot plus bounded recent variants
- return `404` when no registry row exists for the current selected render

- [ ] **Step 4: Re-run the targeted route test to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_animation_reconciliation.py -k "current_animation_shot"
```

Expected: PASS.

- [ ] **Step 5: Commit the read surface**

```bash
git add backend/app/routes/animation.py \
  backend/app/models.py \
  backend/tests/test_animation_reconciliation.py
git commit -m "feat(hollowforge): add current animation shot route"
```

## Task 5: Switch `/comic` Teaser Ops To Current Shot + Variants

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ComicStudio.tsx`
- Modify: `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

Extend `frontend/src/pages/ComicStudio.test.tsx`.

Required coverage:

```tsx
test('teaser ops renders current shot and recent variants for the selected render', async () => {
  expect(await screen.findByText(/Current Teaser Shot/i)).toBeInTheDocument()
  expect(screen.getByText(/Recent Variants For Selected Render/i)).toBeInTheDocument()
  expect(screen.getByText(/sdxl_ipadapter_microanim_v2/i)).toBeInTheDocument()
})
```

```tsx
test('teaser rerun refreshes the current shot query rather than raw animation job history', async () => {
  ...
  expect(getCurrentAnimationShot).toHaveBeenCalled()
})
```

- [ ] **Step 2: Run the targeted frontend test to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
```

Expected: FAIL because the client helper and shot-aware UI do not exist.

- [ ] **Step 3: Add the client and UI wiring**

In `frontend/src/api/client.ts`, add:

- `AnimationShotResponse`
- `AnimationShotVariantResponse`
- `AnimationCurrentShotResponse`
- `getCurrentAnimationShot()`

Minimal client shape:

```ts
export async function getCurrentAnimationShot(query: {
  scene_panel_id: string
  selected_render_asset_id: string
  limit?: number
}): Promise<AnimationCurrentShotResponse> {
  const res = await api.get<AnimationCurrentShotResponse>('/animation/shots/current', { params: query })
  return res.data
}
```

In `frontend/src/pages/ComicStudio.tsx`:

- replace the `listAnimationJobs({ generation_id })` query with `getCurrentAnimationShot({ scene_panel_id, selected_render_asset_id })`
- keep readiness gating unchanged
- compute latest success/failure from `variants`
- on rerun/reconcile success, invalidate the current-shot query key

In `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`:

- add `Current Teaser Shot` summary
- show recent variants
- keep latest success mp4 / latest failure card
- do not add a new page or browsing surface

- [ ] **Step 4: Re-run the frontend test suite to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 5: Commit the UI switch**

```bash
git add frontend/src/api/client.ts \
  frontend/src/pages/ComicStudio.tsx \
  frontend/src/components/comic/ComicTeaserOpsPanel.tsx \
  frontend/src/pages/ComicStudio.test.tsx
git commit -m "feat(hollowforge): show current teaser shot variants in comic studio"
```

## Task 6: Update Docs And Run End-To-End Verification

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 1: Write the minimal doc changes**

Update docs so they reflect:

- teaser ops now tracks `Current Teaser Shot`
- recent entries are `variants` under the current selected render
- stale reconcile still follows `fail then rerun`

Required phrasing change in the SOP:

- replace `inspect recent teaser history` with `inspect current teaser shot and recent variants`

- [ ] **Step 2: Run the full targeted verification bundle**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_comic_schema.py \
  tests/test_animation_shot_registry.py \
  tests/test_animation_reconciliation.py \
  tests/test_launch_comic_teaser_animation_smoke.py

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx --runInBand
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 3: Run one live teaser verification against stable runtime**

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

Expected success markers:

- `animation_shot_id: <non-empty>`
- `animation_shot_variant_id: <non-empty>`
- `animation_job_id: <non-empty>`
- `output_path: ...mp4`
- `teaser_success: true`
- `overall_success: true`

- [ ] **Step 4: Verify `/comic` manually**

Check:

- `Current Teaser Shot` summary appears for a selected materialized render
- recent variants update after rerun
- latest success mp4 opens
- reconcile leaves the shot summary intact and only updates failed variants

- [ ] **Step 5: Commit docs and final verification state**

```bash
git add README.md \
  STATE.md \
  docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): document teaser shot registry ops"
```
