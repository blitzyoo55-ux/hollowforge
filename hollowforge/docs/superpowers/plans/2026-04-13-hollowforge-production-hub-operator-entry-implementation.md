# HollowForge Production Hub Operator Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/production` into the real operator entry point by adding shared-core creation UI plus episode-aware handoff into `/comic` and `/sequences`.

**Architecture:** Keep the shared production core as the source of truth, extend the production API just enough for operator creation and ambiguity-safe linking, and pass episode context into downstream surfaces through URL query parameters rather than a new global store. The implementation should preserve the existing comic and sequence stacks while adding a thin orchestration layer on top.

**Tech Stack:** FastAPI, Pydantic v2, SQLite/aiosqlite, React 19, TypeScript, TanStack Query, Vitest, pytest, Markdown docs

---

## Scope Boundary

This plan executes the approved spec at:

- `docs/superpowers/specs/2026-04-13-hollowforge-production-hub-operator-entry-design.md`

This slice includes:

1. production work/series/episode creation from `/production`
2. production API support for listable operator choices
3. ambiguity-safe current-track metadata for operator entry links
4. `/sequences` support for `open_current` and `create_from_production`
5. `/comic` support for `open_current` and `create_from_production`

This slice does **not** include:

- DB-level enforcement of one current comic track / one current animation track
- production episode edit/delete
- history-management UI
- CLIP STUDIO or external animation editor export upgrades
- a cross-surface mega-wizard

## Preconditions

- Follow `@superpowers:test-driven-development` while implementing each task.
- Follow `@superpowers:verification-before-completion` before claiming any checkpoint is complete.
- Do not revert or absorb the unrelated dirty backend/worker files already present in the worktree.
- Keep reads/writes inside this HollowForge worktree.

## File Map

### Backend production contract

- Modify: `backend/app/models.py`
  - make work/series create IDs optional for operator UX
  - extend production detail responses with track-count metadata
- Modify: `backend/app/services/production_hub_repository.py`
  - add work/series list helpers
  - generate IDs server-side when omitted
  - compute comic/animation track counts per production episode
- Modify: `backend/app/routes/production.py`
  - add `GET /works`
  - add `GET /series?work_id=...`
- Modify: `backend/tests/test_production_routes.py`
  - cover operator-entry backend contract

### Backend comic filter/import contract

- Modify: `backend/app/models.py`
  - extend `ComicStoryPlanImportRequest` with nullable production-link fields
- Modify: `backend/app/services/comic_repository.py`
  - add `production_episode_id` filtering to comic episode listing
- Modify: `backend/app/routes/comic.py`
  - accept `production_episode_id` on episode list route
  - pass production-link fields through import-story-plan
- Modify: `backend/tests/test_comic_repository.py`
  - cover production-linked listing behavior
- Modify: `backend/tests/test_comic_routes.py`
  - cover route filtering + import propagation

### Frontend production hub UI

- Modify: `frontend/src/api/client.ts`
  - add production create/list clients
  - add production detail track-count fields
  - add comic episode list client
- Create: `frontend/src/components/production/ProductionWorkForm.tsx`
- Create: `frontend/src/components/production/ProductionSeriesForm.tsx`
- Create: `frontend/src/components/production/ProductionEpisodeForm.tsx`
- Create: `frontend/src/lib/productionEntry.ts`
  - centralize `open_current | create_from_production` link decisions
- Modify: `frontend/src/pages/ProductionHub.tsx`
- Modify: `frontend/src/pages/ProductionHub.test.tsx`

### Frontend downstream handoff behavior

- Modify: `frontend/src/components/SequenceBlueprintForm.tsx`
  - accept production-prefill defaults
- Modify: `frontend/src/pages/SequenceStudio.tsx`
- Modify: `frontend/src/pages/SequenceStudio.test.tsx`
- Modify: `frontend/src/components/comic/ComicEpisodeDraftPanel.tsx`
  - expose production-context hints in the intake UI
- Modify: `frontend/src/pages/ComicStudio.tsx`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

### Docs

- Modify: `README.md`
  - document `/production` as creation + resume entry
- Modify: `STATE.md`
  - update resume notes for query-based handoff behavior

## Task 1: Add Production Operator Entry Backend Contract

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/production_hub_repository.py`
- Modify: `backend/app/routes/production.py`
- Modify: `backend/tests/test_production_routes.py`

- [ ] **Step 1: Write failing production route tests for operator listing and server-generated IDs**

Add tests to `backend/tests/test_production_routes.py` similar to:

```python
def test_create_and_list_production_works_and_series_without_client_ids(temp_db) -> None:
    client = _build_client()

    work_response = client.post(
        "/api/v1/production/works",
        json={
            "title": "Camila Project",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
        },
    )
    assert work_response.status_code == 201
    work_id = work_response.json()["id"]
    assert work_id

    series_response = client.post(
        "/api/v1/production/series",
        json={
            "work_id": work_id,
            "title": "Season One",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
        },
    )
    assert series_response.status_code == 201

    works_response = client.get("/api/v1/production/works")
    assert works_response.status_code == 200
    assert [row["id"] for row in works_response.json()] == [work_id]

    series_list_response = client.get("/api/v1/production/series", params={"work_id": work_id})
    assert series_list_response.status_code == 200
    assert [row["work_id"] for row in series_list_response.json()] == [work_id]
```

- [ ] **Step 2: Write a failing production episode detail test for track counts**

Add a test to `backend/tests/test_production_routes.py` that proves the response shape includes:

```python
assert payload["comic_track_count"] == 0
assert payload["animation_track_count"] == 0
```

Then create two linked sequence blueprints for the same production episode and assert:

```python
assert refreshed_payload["animation_track_count"] == 2
```

- [ ] **Step 3: Run the backend production tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_production_routes.py -q
```

Expected: FAIL because work/series list endpoints, optional IDs, and track counts do not exist yet.

- [ ] **Step 4: Update the production models for operator UX**

Modify `backend/app/models.py` so that:

- `ProductionWorkCreate.id` becomes `Optional[str] = None`
- `ProductionSeriesCreate.id` becomes `Optional[str] = None`
- `ProductionEpisodeDetailResponse` adds:

```python
comic_track_count: int = 0
animation_track_count: int = 0
```

- [ ] **Step 5: Implement repository support**

Modify `backend/app/services/production_hub_repository.py` to:

- generate `uuid4()` IDs for works/series when `payload.id` is missing
- add:

```python
async def list_works() -> list[ProductionWorkResponse]: ...
async def list_series(*, work_id: Optional[str] = None) -> list[ProductionSeriesResponse]: ...
```

- add internal count helpers:

```python
async def _count_comic_tracks(production_episode_id: str) -> int: ...
async def _count_animation_tracks(production_episode_id: str) -> int: ...
```

- populate `comic_track_count` and `animation_track_count` in both `get_production_episode_detail()` and `list_production_episodes()`

- [ ] **Step 6: Implement production list routes**

Modify `backend/app/routes/production.py` to add:

```python
@router.get("/works", response_model=list[ProductionWorkResponse])
async def list_works_endpoint() -> list[ProductionWorkResponse]: ...

@router.get("/series", response_model=list[ProductionSeriesResponse])
async def list_series_endpoint(work_id: Optional[str] = Query(default=None)) -> list[ProductionSeriesResponse]: ...
```

- [ ] **Step 7: Re-run the backend production tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_production_routes.py -q
```

Expected: PASS

- [ ] **Step 8: Commit the production operator contract**

```bash
git add backend/app/models.py \
  backend/app/services/production_hub_repository.py \
  backend/app/routes/production.py \
  backend/tests/test_production_routes.py
git commit -m "feat(hollowforge): add production operator entry contract"
```

## Task 2: Add Comic Production-Link Listing And Import Propagation

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/comic_repository.py`
- Modify: `backend/app/routes/comic.py`
- Modify: `backend/tests/test_comic_repository.py`
- Modify: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write the failing repository test for production-linked comic listing**

Add a repository-level test in `backend/tests/test_comic_repository.py`:

```python
@pytest.mark.asyncio
async def test_list_comic_episodes_filters_by_production_episode_id(temp_db) -> None:
    await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Linked A",
            synopsis="A",
            production_episode_id="prod_ep_a",
        ),
        episode_id="comic_ep_prod_a",
    )
    await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Linked B",
            synopsis="B",
            production_episode_id="prod_ep_b",
        ),
        episode_id="comic_ep_prod_b",
    )

    summaries = await list_comic_episodes(production_episode_id="prod_ep_a")
    assert [row.episode.id for row in summaries] == ["comic_ep_prod_a"]
```

- [ ] **Step 2: Write the failing route test for import propagation**

Add a route test in `backend/tests/test_comic_routes.py` that posts to:

```python
"/api/v1/comic/episodes/import-story-plan"
```

with:

```python
{
    "approved_plan": approved_plan.model_dump(mode="json"),
    "character_version_id": "charver_kaede_ren_still_v1",
    "title": "Linked Import",
    "work_id": "work_demo",
    "series_id": "series_demo",
    "production_episode_id": "prod_ep_demo",
}
```

and asserts:

```python
assert body["episode"]["work_id"] == "work_demo"
assert body["episode"]["series_id"] == "series_demo"
assert body["episode"]["production_episode_id"] == "prod_ep_demo"
```

- [ ] **Step 3: Run the comic backend tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_comic_repository.py tests/test_comic_routes.py -q
```

Expected: FAIL because the list filter and import propagation do not exist yet.

- [ ] **Step 4: Extend the import request model**

Modify `backend/app/models.py` so `ComicStoryPlanImportRequest` includes:

```python
work_id: Optional[str] = Field(default=None, max_length=120)
series_id: Optional[str] = Field(default=None, max_length=120)
production_episode_id: Optional[str] = Field(default=None, max_length=120)
```

- [ ] **Step 5: Implement comic episode filtering**

Modify `backend/app/services/comic_repository.py`:

- extend `list_comic_episodes()` to accept:

```python
production_episode_id: str | None = None
```

- add the corresponding SQL clause:

```python
if production_episode_id is not None:
    clauses.append("e.production_episode_id = ?")
    params.append(production_episode_id)
```

- [ ] **Step 6: Wire the new route behavior**

Modify `backend/app/routes/comic.py` so:

- `GET /episodes` accepts `production_episode_id` as a query parameter
- `import_story_plan()` copies `work_id`, `series_id`, and `production_episode_id` into the `draft.model_copy(update=...)` payload before `create_comic_episode_from_draft(...)`

- [ ] **Step 7: Re-run the comic backend tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_comic_repository.py tests/test_comic_routes.py -q
```

Expected: PASS

- [ ] **Step 8: Commit the comic production-link contract**

```bash
git add backend/app/models.py \
  backend/app/services/comic_repository.py \
  backend/app/routes/comic.py \
  backend/tests/test_comic_repository.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): link comic intake to production episodes"
```

## Task 3: Add Production Hub Creation UI And Link Rules

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/components/production/ProductionWorkForm.tsx`
- Create: `frontend/src/components/production/ProductionSeriesForm.tsx`
- Create: `frontend/src/components/production/ProductionEpisodeForm.tsx`
- Create: `frontend/src/lib/productionEntry.ts`
- Modify: `frontend/src/pages/ProductionHub.tsx`
- Modify: `frontend/src/pages/ProductionHub.test.tsx`

- [ ] **Step 1: Write the failing frontend tests for creation panels**

Add tests to `frontend/src/pages/ProductionHub.test.tsx` for:

1. rendering all three creation panels
2. submitting a work without an ID field
3. filtering series options by selected work
4. building `Open Comic Handoff` and `Open Animation Track` links with:
   - `mode=create_from_production` when track count is `0`
   - `mode=open_current` when track count is `1`

Example expectations:

```tsx
expect(screen.getByRole('heading', { name: /Create Production Episode/i })).toBeInTheDocument()
expect(screen.getByRole('link', { name: /Open Comic Handoff/i })).toHaveAttribute(
  'href',
  '/comic?production_episode_id=prod-ep-1&mode=create_from_production',
)
```

- [ ] **Step 2: Run the Production Hub frontend tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ProductionHub.test.tsx
```

Expected: FAIL because the forms and link rules do not exist yet.

- [ ] **Step 3: Add production client functions**

Modify `frontend/src/api/client.ts` to add:

```ts
export interface ProductionWorkCreate { ... }
export interface ProductionSeriesCreate { ... }
export interface ProductionEpisodeCreate { ... }

export async function listProductionWorks(): Promise<ProductionWorkResponse[]> { ... }
export async function listProductionSeries(query?: { work_id?: string }): Promise<ProductionSeriesResponse[]> { ... }
export async function createProductionWork(data: ProductionWorkCreate): Promise<ProductionWorkResponse> { ... }
export async function createProductionSeries(data: ProductionSeriesCreate): Promise<ProductionSeriesResponse> { ... }
export async function createProductionEpisode(data: ProductionEpisodeCreate): Promise<ProductionEpisodeDetailResponse> { ... }
export async function listComicEpisodes(query?: { production_episode_id?: string }): Promise<ComicEpisodeSummaryResponse[]> { ... }
```

Also extend `ProductionEpisodeDetailResponse` with:

```ts
comic_track_count: number
animation_track_count: number
```

- [ ] **Step 4: Add a focused production entry helper**

Create `frontend/src/lib/productionEntry.ts` with a helper like:

```ts
export function buildProductionTrackHref(
  track: 'comic' | 'animation',
  episode: ProductionEpisodeDetailResponse,
): string { ... }
```

Rules:

- count `0` -> `mode=create_from_production`
- count `1` -> `mode=open_current`
- count `>1` -> `mode=open_current` plus downstream filter-only behavior remains possible because the target page sees count ambiguity via the linked list result

- [ ] **Step 5: Split the creation UI into focused components**

Create:

- `frontend/src/components/production/ProductionWorkForm.tsx`
- `frontend/src/components/production/ProductionSeriesForm.tsx`
- `frontend/src/components/production/ProductionEpisodeForm.tsx`

Each form should:

- own only its input fields
- receive submit handlers and option lists from the page
- avoid asking for raw ID entry

Use operator-facing defaults:

- work format default: `mixed`
- series delivery default: `serial`
- episode target outputs default: `comic + animation`

- [ ] **Step 6: Implement the page orchestration**

Modify `frontend/src/pages/ProductionHub.tsx` to:

- fetch works, series, and episodes
- render the three creation forms above the registry
- invalidate the relevant queries after each successful create
- build episode entry links through `buildProductionTrackHref()`
- show track count warnings when counts are greater than `1`

- [ ] **Step 7: Re-run the Production Hub frontend tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ProductionHub.test.tsx
```

Expected: PASS

- [ ] **Step 8: Commit the Production Hub UI**

```bash
git add frontend/src/api/client.ts \
  frontend/src/components/production/ProductionWorkForm.tsx \
  frontend/src/components/production/ProductionSeriesForm.tsx \
  frontend/src/components/production/ProductionEpisodeForm.tsx \
  frontend/src/lib/productionEntry.ts \
  frontend/src/pages/ProductionHub.tsx \
  frontend/src/pages/ProductionHub.test.tsx
git commit -m "feat(hollowforge): add production hub creation entry UI"
```

## Task 4: Add Animation Track URL Prefill And Auto-Open

**Files:**
- Modify: `frontend/src/components/SequenceBlueprintForm.tsx`
- Modify: `frontend/src/pages/SequenceStudio.tsx`
- Modify: `frontend/src/pages/SequenceStudio.test.tsx`

- [ ] **Step 1: Write failing Sequence Studio tests for URL-driven behavior**

Add tests in `frontend/src/pages/SequenceStudio.test.tsx` using `MemoryRouter` `initialEntries`:

1. `?production_episode_id=prod-ep-1&mode=create_from_production`
   - the form should show a production-context hint
   - the form should use prefilled `content_mode`, `work_id`, `series_id`, `production_episode_id`
2. `?production_episode_id=prod-ep-1&mode=open_current`
   - when the filtered blueprint list contains exactly one row, it becomes selected automatically

Example test shape:

```tsx
renderPage('/sequences?production_episode_id=prod-ep-1&mode=create_from_production')
expect(await screen.findByText(/Production Episode Context/i)).toBeInTheDocument()
expect(screen.getByText(/prod-ep-1/i)).toBeInTheDocument()
```

- [ ] **Step 2: Run the Sequence Studio tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/SequenceStudio.test.tsx
```

Expected: FAIL because the page ignores URL production context today.

- [ ] **Step 3: Extend the blueprint form for prefills**

Modify `frontend/src/components/SequenceBlueprintForm.tsx` to accept props like:

```ts
initialValues?: Partial<SequenceBlueprintCreate>
productionContextLabel?: string | null
```

The form should:

- seed local state from initial values
- preserve required hidden link fields on submit
- show a small operator-facing context panel when a production episode is present

- [ ] **Step 4: Implement URL handling in Sequence Studio**

Modify `frontend/src/pages/SequenceStudio.tsx` to:

- read `production_episode_id` and `mode` via `useSearchParams`
- call `listSequenceBlueprints({ production_episode_id })` when context is present
- for `open_current`, auto-select the single linked blueprint if exactly one exists
- for `create_from_production`, fetch the production episode detail and pass form defaults into `SequenceBlueprintForm`

- [ ] **Step 5: Re-run the Sequence Studio tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/SequenceStudio.test.tsx
```

Expected: PASS

- [ ] **Step 6: Commit the animation-track handoff behavior**

```bash
git add frontend/src/components/SequenceBlueprintForm.tsx \
  frontend/src/pages/SequenceStudio.tsx \
  frontend/src/pages/SequenceStudio.test.tsx
git commit -m "feat(hollowforge): add animation track production handoff"
```

## Task 5: Add Comic Handoff URL Prefill And Auto-Open

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/comic/ComicEpisodeDraftPanel.tsx`
- Modify: `frontend/src/pages/ComicStudio.tsx`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

- [ ] **Step 1: Write failing Comic Studio tests for production-context intake**

Add tests in `frontend/src/pages/ComicStudio.test.tsx` for:

1. `?production_episode_id=prod-ep-1&mode=create_from_production`
   - the intake panel shows the linked production context
   - import submission forwards `work_id`, `series_id`, `production_episode_id`
   - episode title is prefilled from the production episode
2. `?production_episode_id=prod-ep-1&mode=open_current`
   - when `listComicEpisodes({ production_episode_id })` returns exactly one linked episode, the page loads that episode detail automatically

- [ ] **Step 2: Run the Comic Studio tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ComicStudio.test.tsx
```

Expected: FAIL because the page currently has no production-aware URL contract.

- [ ] **Step 3: Add production-aware comic client helpers**

In `frontend/src/api/client.ts`, ensure the client exposes:

```ts
export async function getProductionEpisode(productionEpisodeId: string): Promise<ProductionEpisodeDetailResponse> { ... }
export async function listComicEpisodes(query?: { production_episode_id?: string }): Promise<ComicEpisodeSummaryResponse[]> { ... }
```

and extend `ComicStoryPlanImportRequest` with:

```ts
work_id?: string | null
series_id?: string | null
production_episode_id?: string | null
```

- [ ] **Step 4: Expose production context in the draft panel**

Modify `frontend/src/components/comic/ComicEpisodeDraftPanel.tsx` to accept:

```ts
productionContext?: {
  productionEpisodeId: string
  workId: string
  seriesId: string | null
  contentMode: string
} | null
```

Render a compact intake hint so operators can see which production episode they are importing into.

- [ ] **Step 5: Implement Comic Studio URL handling**

Modify `frontend/src/pages/ComicStudio.tsx` to:

- read `production_episode_id` and `mode` via `useSearchParams`
- for `create_from_production`:
  - fetch the production episode detail
  - prefill the title
  - retain the production-link fields for the import mutation payload
- for `open_current`:
  - call `listComicEpisodes({ production_episode_id })`
  - if exactly one summary exists, fetch/load that episode detail automatically

Also update the import mutation payload:

```ts
return importComicStoryPlan({
  approved_plan: approvedPlanDraft.parsed,
  character_version_id: effectiveCharacterVersionId,
  title,
  panel_multiplier: panelMultiplier,
  work_id: productionContext?.workId ?? null,
  series_id: productionContext?.seriesId ?? null,
  production_episode_id: productionContext?.productionEpisodeId ?? null,
})
```

- [ ] **Step 6: Re-run the Comic Studio tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ComicStudio.test.tsx
```

Expected: PASS

- [ ] **Step 7: Commit the comic handoff behavior**

```bash
git add frontend/src/api/client.ts \
  frontend/src/components/comic/ComicEpisodeDraftPanel.tsx \
  frontend/src/pages/ComicStudio.tsx \
  frontend/src/pages/ComicStudio.test.tsx
git commit -m "feat(hollowforge): add comic production handoff"
```

## Task 6: Verify The Full Operator Entry Slice And Refresh Docs

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`

- [ ] **Step 1: Update the repo docs for the new operator flow**

In `README.md` and `STATE.md`, document that:

- `/production` now owns shared-core creation plus episode-aware resume
- `/comic` and `/sequences` accept query-based production context
- the fallback behavior is `create_from_production` vs `open_current`

- [ ] **Step 2: Run the exact frontend verification suite**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ProductionHub.test.tsx src/pages/SequenceStudio.test.tsx src/pages/ComicStudio.test.tsx
npm run build
```

Expected:

- `22+` tests passing with the new operator-entry coverage
- Vite build exits `0`

- [ ] **Step 3: Run the backend verification suite for touched contracts**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_production_routes.py tests/test_comic_repository.py tests/test_comic_routes.py -q
```

Expected: PASS

- [ ] **Step 4: Commit the docs + final verification slice**

```bash
git add README.md STATE.md
git commit -m "docs(hollowforge): document production operator entry"
```

- [ ] **Step 5: Record the final verification evidence in the session handoff**

Capture the exact passing command outputs in the final implementation summary before offering merge/PR options.
