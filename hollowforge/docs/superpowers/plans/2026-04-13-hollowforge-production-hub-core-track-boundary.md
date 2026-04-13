# HollowForge Production Hub Core + Track Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a shared production-hub core for works/series/episodes, link the existing comic and sequence systems to that core, and make the `/comic` and animation surfaces read as handoff/review tools instead of final authoring tools.

**Architecture:** Add new shared core tables and a small production API without rewriting the existing comic and sequence stacks. Retrofit `comic_episodes` and `sequence_blueprints` with nullable production links plus explicit `content_mode`, then update backend and frontend wording so the product boundary is clear: HollowForge owns orchestration and handoff packaging, while CLIP STUDIO and the external editor own final finishing.

**Tech Stack:** FastAPI, Pydantic v2, SQLite/aiosqlite, React 19, TypeScript, TanStack Query, Vitest, pytest, Markdown docs

---

## Scope Boundary

This spec spans multiple subsystems. Do not try to implement Comic Handoff V2, Animation Handoff V1, and quality-engine refactors in one pass.

This plan covers only the first executable slice:

1. shared production-hub core records
2. comic and animation track linkage to the shared core
3. episode-level `content_mode` normalization
4. boundary-first API/UI copy fixes so operators stop reading `/comic` as a final manga editor

Follow-on plans must handle the rest:

- `Comic Handoff V2`: frame guides, SFX manifest hardening, PSD/CLIP STUDIO package quality
- `Animation Handoff V1`: `scene_shots`, `shot_anchor_assets`, clip package export, teaser migration
- still quality split: panel still vs shot-anchor still tuning

## Preconditions

- Follow `@superpowers:test-driven-development` while implementing each task.
- Follow `@superpowers:verification-before-completion` before claiming any checkpoint is complete.
- Treat `docs/superpowers/specs/2026-04-13-hollowforge-dual-track-production-hub-design.md` as the source spec for this plan.
- Do not implement native `.clip` generation or final NLE timeline export in this phase.
- Do not rewrite the existing favorite-informed quality layer in this phase.
- Do not revert or absorb the current unrelated dirty changes in the worktree.

## File Map

### Backend schema and shared core

- Create: `backend/migrations/035_production_hub_core.sql`
  - adds shared `works`, `series`, and `production_episodes` tables
  - adds nullable production-link columns to `comic_episodes` and `sequence_blueprints`
  - adds explicit `content_mode` to `comic_episodes`
- Modify: `backend/app/models.py`
  - adds production-hub request/response models and extends comic/sequence models with production-link fields

### Backend repositories and routes

- Create: `backend/app/services/production_hub_repository.py`
  - shared CRUD and detail loading for works/series/production episodes
- Create: `backend/app/routes/production.py`
  - production-hub endpoints for create/list/detail
- Modify: `backend/app/main.py`
  - mounts the new production router in both lightweight and full app modes
- Modify: `backend/app/services/comic_repository.py`
  - persists and reads `production_episode_id`, `series_id`, `work_id`, and `content_mode`
- Modify: `backend/app/routes/comic.py`
  - accepts the new fields and exposes boundary-correct response data
- Modify: `backend/app/services/comic_dialogue_service.py`
  - resolves dialogue provider/profile from comic `content_mode`
- Modify: `backend/app/services/sequence_repository.py`
  - persists and reads production links on sequence blueprints
- Modify: `backend/app/routes/sequences.py`
  - accepts and filters by `production_episode_id`

### Backend tests and scripts

- Create: `backend/tests/test_production_routes.py`
- Create: `backend/tests/test_launch_production_hub_smoke.py`
- Create: `backend/scripts/launch_production_hub_smoke.py`
- Modify: `backend/tests/test_comic_schema.py`
- Modify: `backend/tests/test_sequence_schema.py`
- Modify: `backend/tests/test_comic_repository.py`
- Modify: `backend/tests/test_comic_routes.py`
- Modify: `backend/tests/test_comic_dialogue_service.py`
- Modify: `backend/tests/test_sequence_routes.py`

### Frontend

- Create: `frontend/src/pages/ProductionHub.tsx`
  - production-hub landing page showing shared episodes and linked track state
- Create: `frontend/src/pages/ProductionHub.test.tsx`
- Modify: `frontend/src/api/client.ts`
  - adds production-hub types and route clients; extends comic/sequence types
- Modify: `frontend/src/App.tsx`
  - adds `/production` route and boundary-correct nav labels
- Modify: `frontend/src/pages/ComicStudio.tsx`
  - updates page copy to "Comic Handoff Workspace" semantics
- Modify: `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`
  - re-labels teaser controls as animation-track preview/review
- Modify: `frontend/src/pages/SequenceStudio.tsx`
  - updates page copy to animation-track planning/review semantics
- Modify: `frontend/src/pages/ComicStudio.test.tsx`
- Modify: `frontend/src/pages/SequenceStudio.test.tsx`

### Docs

- Modify: `README.md`
  - documents the production-hub boundary and smoke command
- Modify: `STATE.md`
  - records the new production-hub core slice and next resume point

## Task 1: Add Shared Production Hub Schema

**Files:**
- Create: `backend/migrations/035_production_hub_core.sql`
- Modify: `backend/tests/test_comic_schema.py`
- Modify: `backend/tests/test_sequence_schema.py`

- [ ] **Step 1: Write the failing schema contract tests**

```python
async def test_production_hub_core_tables_exist(temp_db) -> None:
    await init_db()
    with sqlite3.connect(temp_db) as conn:
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        table_names = {row[0] for row in table_rows}
    assert {"works", "series", "production_episodes"} <= table_names


async def test_comic_and_sequence_tables_expose_production_link_columns(temp_db) -> None:
    await init_db()
    with sqlite3.connect(temp_db) as conn:
        comic_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(comic_episodes)")
        }
        sequence_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(sequence_blueprints)")
        }
    assert {"content_mode", "work_id", "series_id", "production_episode_id"} <= comic_columns
    assert {"work_id", "series_id", "production_episode_id"} <= sequence_columns
```

- [ ] **Step 2: Run the schema tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_comic_schema.py tests/test_sequence_schema.py -q
```

Expected: FAIL because the shared core tables and production-link columns do not exist yet.

- [ ] **Step 3: Add the migration**

Migration shape:

```sql
CREATE TABLE IF NOT EXISTS works (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    format_family TEXT NOT NULL,
    default_content_mode TEXT NOT NULL CHECK (default_content_mode IN ('all_ages', 'adult_nsfw')),
    status TEXT NOT NULL DEFAULT 'draft',
    canon_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS series (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    delivery_mode TEXT NOT NULL,
    audience_mode TEXT NOT NULL,
    visual_identity_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_episodes (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    series_id TEXT REFERENCES series(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    synopsis TEXT NOT NULL,
    content_mode TEXT NOT NULL CHECK (content_mode IN ('all_ages', 'adult_nsfw')),
    target_outputs TEXT NOT NULL DEFAULT '[]',
    continuity_summary TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

ALTER TABLE comic_episodes ADD COLUMN content_mode TEXT NOT NULL DEFAULT 'all_ages';
ALTER TABLE comic_episodes ADD COLUMN work_id TEXT;
ALTER TABLE comic_episodes ADD COLUMN series_id TEXT;
ALTER TABLE comic_episodes ADD COLUMN production_episode_id TEXT;

ALTER TABLE sequence_blueprints ADD COLUMN work_id TEXT;
ALTER TABLE sequence_blueprints ADD COLUMN series_id TEXT;
ALTER TABLE sequence_blueprints ADD COLUMN production_episode_id TEXT;
```

- [ ] **Step 4: Re-run the schema tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_comic_schema.py tests/test_sequence_schema.py -q
```

Expected: PASS with the shared tables and link columns in place.

- [ ] **Step 5: Commit the schema foundation**

```bash
git add backend/migrations/035_production_hub_core.sql \
  backend/tests/test_comic_schema.py \
  backend/tests/test_sequence_schema.py
git commit -m "feat(hollowforge): add production hub core schema"
```

## Task 2: Add Production Hub Models, Repository, And Routes

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/app/services/production_hub_repository.py`
- Create: `backend/app/routes/production.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_production_routes.py`

- [ ] **Step 1: Write failing production route tests**

```python
def test_create_and_get_production_episode(client):
    work_response = client.post(
        "/api/v1/production/works",
        json={
            "id": "work_test",
            "title": "Camila Project",
            "format_family": "mixed",
            "default_content_mode": "adult_nsfw",
        },
    )
    assert work_response.status_code == 201

    series_response = client.post(
        "/api/v1/production/series",
        json={
            "id": "series_test",
            "work_id": "work_test",
            "title": "Season One",
            "delivery_mode": "serial",
            "audience_mode": "adult_nsfw",
        },
    )
    assert series_response.status_code == 201

    episode_response = client.post(
        "/api/v1/production/episodes",
        json={
            "work_id": "work_test",
            "series_id": "series_test",
            "title": "Episode 01",
            "synopsis": "Camila starts a new arc.",
            "content_mode": "adult_nsfw",
            "target_outputs": ["comic", "animation"],
        },
    )
    assert episode_response.status_code == 201
    payload = episode_response.json()
    assert payload["content_mode"] == "adult_nsfw"
    assert payload["comic_track"] is None
    assert payload["animation_track"] is None

    detail = client.get(f"/api/v1/production/episodes/{payload['id']}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Episode 01"
```

- [ ] **Step 2: Run the new route test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_production_routes.py -q
```

Expected: FAIL because the route module, repository, and models do not exist.

- [ ] **Step 3: Implement the production-hub API**

Model shape:

```python
class ProductionWorkCreate(BaseModel):
    id: str
    title: str
    format_family: Literal["comic", "animation", "mixed"]
    default_content_mode: SequenceContentMode


class ProductionSeriesCreate(BaseModel):
    id: str
    work_id: str
    title: str
    delivery_mode: Literal["oneshot", "serial", "anthology"]
    audience_mode: SequenceContentMode


class ProductionEpisodeCreate(BaseModel):
    work_id: str
    series_id: str | None = None
    title: str
    synopsis: str
    content_mode: SequenceContentMode
    target_outputs: list[Literal["comic", "animation"]] = Field(default_factory=list)


class ProductionEpisodeDetailResponse(BaseModel):
    id: str
    work_id: str
    series_id: str | None
    title: str
    synopsis: str
    content_mode: SequenceContentMode
    target_outputs: list[str]
    comic_track: dict[str, Any] | None = None
    animation_track: dict[str, Any] | None = None
```

Repository shape:

```python
async def create_work(payload: ProductionWorkCreate) -> ProductionWorkResponse: ...
async def create_series(payload: ProductionSeriesCreate) -> ProductionSeriesResponse: ...
async def create_production_episode(payload: ProductionEpisodeCreate) -> ProductionEpisodeDetailResponse: ...
async def list_production_episodes(*, work_id: str | None = None) -> list[ProductionEpisodeDetailResponse]: ...
async def get_production_episode_detail(production_episode_id: str) -> ProductionEpisodeDetailResponse | None: ...
```

Route shape:

```python
router = APIRouter(prefix="/api/v1/production", tags=["production"])

@router.post("/works", response_model=ProductionWorkResponse, status_code=201)
async def create_work_endpoint(payload: ProductionWorkCreate): ...

@router.post("/series", response_model=ProductionSeriesResponse, status_code=201)
async def create_series_endpoint(payload: ProductionSeriesCreate): ...

@router.post("/episodes", response_model=ProductionEpisodeDetailResponse, status_code=201)
async def create_production_episode_endpoint(payload: ProductionEpisodeCreate): ...

@router.get("/episodes", response_model=list[ProductionEpisodeDetailResponse])
async def list_production_episodes_endpoint(...): ...

@router.get("/episodes/{production_episode_id}", response_model=ProductionEpisodeDetailResponse)
async def get_production_episode_endpoint(...): ...
```

- [ ] **Step 4: Re-run the production route tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_production_routes.py -q
```

Expected: PASS with the new route mounted in lightweight and full app modes.

- [ ] **Step 5: Commit the production API layer**

```bash
git add backend/app/models.py \
  backend/app/services/production_hub_repository.py \
  backend/app/routes/production.py \
  backend/app/main.py \
  backend/tests/test_production_routes.py
git commit -m "feat(hollowforge): add production hub API"
```

## Task 3: Retrofit Comic Episodes To The Shared Core And Normalize Dialogue By Mode

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/comic_repository.py`
- Modify: `backend/app/routes/comic.py`
- Modify: `backend/app/services/comic_dialogue_service.py`
- Modify: `backend/tests/test_comic_repository.py`
- Modify: `backend/tests/test_comic_routes.py`
- Modify: `backend/tests/test_comic_dialogue_service.py`

- [ ] **Step 1: Write failing comic repository, route, and dialogue tests**

```python
async def test_create_comic_episode_persists_content_mode_and_production_link(temp_db):
    created = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Linked Comic Track",
            synopsis="Episode-level comic track test.",
            content_mode="adult_nsfw",
            production_episode_id="prod_ep_1",
            work_id="work_1",
            series_id="series_1",
        ),
        episode_id="comic_ep_linked_1",
    )
    assert created.content_mode == "adult_nsfw"
    assert created.production_episode_id == "prod_ep_1"


def test_import_story_plan_maps_lane_to_content_mode(client):
    response = client.post("/api/v1/comic/episodes/import-story-plan", json=payload)
    assert response.status_code == 201
    assert response.json()["episode"]["content_mode"] == "adult_nsfw"
```

```python
@pytest.mark.asyncio
async def test_generate_panel_dialogues_uses_safe_profile_for_all_ages(monkeypatch):
    recorder = {}

    def fake_get_prompt_provider_profile(profile_id: str):
        recorder["profile_id"] = profile_id
        return {"id": profile_id}

    monkeypatch.setattr(
        "app.services.comic_dialogue_service.get_prompt_provider_profile",
        fake_get_prompt_provider_profile,
    )

    await generate_panel_dialogues(panel_id="panel_safe_1")
    assert recorder["profile_id"] == "safe_hosted_grok"
```

- [ ] **Step 2: Run the comic-focused tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_comic_repository.py tests/test_comic_routes.py tests/test_comic_dialogue_service.py -q
```

Expected: FAIL because comic models, repository writes, and dialogue routing do not know about the shared core fields or mode-aware profiles.

- [ ] **Step 3: Implement the comic-track retrofit**

Required behavior:

- `ComicEpisodeBase` gains:
  - `content_mode: SequenceContentMode = "all_ages"`
  - `work_id: str | None = None`
  - `series_id: str | None = None`
  - `production_episode_id: str | None = None`
- `create_comic_episode()` persists the new fields
- `get_comic_episode_detail()` returns the new fields
- `/api/v1/comic/episodes/import-story-plan` maps:
  - `lane="adult_nsfw"` -> `content_mode="adult_nsfw"`
  - everything else -> `content_mode="all_ages"`
- `_fetch_panel_context()` joins `comic_scene_panels -> comic_episode_scenes -> comic_episodes`
- `generate_panel_dialogues()` chooses the provider profile from episode `content_mode` instead of hardcoding adult wording

Dialogue helper shape:

```python
def _resolve_dialogue_profile_id(content_mode: SequenceContentMode) -> str:
    return "adult_local_llm" if content_mode == "adult_nsfw" else "safe_hosted_grok"
```

- [ ] **Step 4: Re-run the comic tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_comic_repository.py tests/test_comic_routes.py tests/test_comic_dialogue_service.py -q
```

Expected: PASS with comic episodes linked to the shared core and dialogue generation following episode mode.

- [ ] **Step 5: Commit the comic-track retrofit**

```bash
git add backend/app/models.py \
  backend/app/services/comic_repository.py \
  backend/app/routes/comic.py \
  backend/app/services/comic_dialogue_service.py \
  backend/tests/test_comic_repository.py \
  backend/tests/test_comic_routes.py \
  backend/tests/test_comic_dialogue_service.py
git commit -m "feat(hollowforge): link comic track to production hub"
```

## Task 4: Retrofit Sequence Blueprints To The Shared Core And Fix Track Vocabulary

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/sequence_repository.py`
- Modify: `backend/app/routes/sequences.py`
- Modify: `backend/tests/test_sequence_routes.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ComicStudio.tsx`
- Modify: `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`
- Modify: `frontend/src/pages/SequenceStudio.tsx`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`
- Modify: `frontend/src/pages/SequenceStudio.test.tsx`

- [ ] **Step 1: Write failing sequence and UI tests**

```python
def test_create_sequence_blueprint_accepts_production_episode_id(client):
    response = client.post(
        "/api/v1/sequences/blueprints",
        json={
            "production_episode_id": "prod_ep_1",
            "work_id": "work_1",
            "series_id": "series_1",
            "content_mode": "all_ages",
            "policy_profile_id": "safe_stage1_v1",
            "character_id": "char_1",
            "location_id": "location_1",
            "beat_grammar_id": "stage1_single_location_v1",
            "target_duration_sec": 36,
            "shot_count": 6,
            "executor_policy": "safe_remote_prod",
        },
    )
    assert response.status_code == 201
    assert response.json()["blueprint"]["production_episode_id"] == "prod_ep_1"
```

```tsx
expect(await screen.findByRole('heading', { name: /Animation Track Studio/i })).toBeInTheDocument()
expect(screen.getByText(/Comic Handoff Workspace/i)).toBeInTheDocument()
expect(screen.getByText(/Animation Track Preview/i)).toBeInTheDocument()
```

- [ ] **Step 2: Run the sequence and frontend tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_sequence_routes.py -q

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/SequenceStudio.test.tsx src/pages/ComicStudio.test.tsx
```

Expected: FAIL because sequence blueprints ignore production links and the UI still uses legacy "Sequence Studio" and "Teaser Ops" wording.

- [ ] **Step 3: Implement the sequence-track retrofit and wording fixes**

Required behavior:

- `SequenceBlueprintBase` gains:
  - `work_id: str | None = None`
  - `series_id: str | None = None`
  - `production_episode_id: str | None = None`
- `create_blueprint()` persists those fields
- `list_blueprints()` optionally filters by `production_episode_id`
- `frontend/src/api/client.ts` exposes the new fields on sequence types
- `/comic` headings and helper copy use "Comic Handoff Workspace"
- `ComicTeaserOpsPanel` uses:
  - badge: `Animation Track Preview`
  - headings and button text that describe preview/review, not teaser-only logic
- `/sequences` uses:
  - heading: `Animation Track Studio`
  - copy that describes shot planning and track review, not generic sequence MVP wording

Minimal UI copy shape:

```tsx
<h1 className="text-2xl font-bold text-gray-100">Animation Track Studio</h1>
<h2 className="text-lg font-semibold text-gray-100">Comic Handoff Workspace</h2>
```

- [ ] **Step 4: Re-run the sequence and frontend tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_sequence_routes.py -q

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/SequenceStudio.test.tsx src/pages/ComicStudio.test.tsx
```

Expected: PASS with shared-core-linked blueprints and boundary-correct operator copy.

- [ ] **Step 5: Commit the sequence-track retrofit**

```bash
git add backend/app/models.py \
  backend/app/services/sequence_repository.py \
  backend/app/routes/sequences.py \
  backend/tests/test_sequence_routes.py \
  frontend/src/api/client.ts \
  frontend/src/pages/ComicStudio.tsx \
  frontend/src/components/comic/ComicTeaserOpsPanel.tsx \
  frontend/src/pages/SequenceStudio.tsx \
  frontend/src/pages/ComicStudio.test.tsx \
  frontend/src/pages/SequenceStudio.test.tsx
git commit -m "feat(hollowforge): add animation track boundary semantics"
```

## Task 5: Add An End-To-End Production Hub Smoke Script

**Files:**
- Create: `backend/scripts/launch_production_hub_smoke.py`
- Create: `backend/tests/test_launch_production_hub_smoke.py`

- [ ] **Step 1: Write the failing smoke-script test**

```python
def test_main_prints_linked_track_success_markers(capsys, monkeypatch):
    # fake the repository calls so the script can run without network or UI
    main()
    captured = capsys.readouterr().out
    assert "PRODUCTION_HUB_OK" in captured
    assert "COMIC_TRACK_OK" in captured
    assert "ANIMATION_TRACK_OK" in captured
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_launch_production_hub_smoke.py -q
```

Expected: FAIL because the smoke script does not exist yet.

- [ ] **Step 3: Implement the smoke script**

Script behavior:

- create or reuse a work
- create or reuse a series
- create a production episode
- create a linked comic episode
- create a linked sequence blueprint
- print stable success markers and the created IDs

Output shape:

```text
PRODUCTION_HUB_OK work=work_demo series=series_demo production_episode=prod_ep_demo
COMIC_TRACK_OK comic_episode=comic_ep_demo content_mode=all_ages
ANIMATION_TRACK_OK sequence_blueprint=bp_demo content_mode=all_ages
```

- [ ] **Step 4: Re-run the smoke test**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest tests/test_launch_production_hub_smoke.py -q
```

Expected: PASS with stable output markers that make end-to-end verification obvious.

- [ ] **Step 5: Commit the smoke verification helper**

```bash
git add backend/scripts/launch_production_hub_smoke.py \
  backend/tests/test_launch_production_hub_smoke.py
git commit -m "test(hollowforge): add production hub smoke verification"
```

## Task 6: Add The Production Hub Landing Page And Update Repo Docs

**Files:**
- Create: `frontend/src/pages/ProductionHub.tsx`
- Create: `frontend/src/pages/ProductionHub.test.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `README.md`
- Modify: `STATE.md`

- [ ] **Step 1: Write the failing frontend page test**

```tsx
test('production hub lists shared episodes and linked tracks', async () => {
  renderWithProviders(<ProductionHub />)
  expect(await screen.findByRole('heading', { name: /Production Hub/i })).toBeInTheDocument()
  expect(screen.getByText(/Comic Track/i)).toBeInTheDocument()
  expect(screen.getByText(/Animation Track/i)).toBeInTheDocument()
  expect(screen.getByText(/adult_nsfw/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the frontend page test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ProductionHub.test.tsx
```

Expected: FAIL because the page, client types, and route do not exist yet.

- [ ] **Step 3: Implement the production landing page and docs updates**

Page responsibilities:

- fetch `/api/v1/production/episodes`
- render content-mode badges
- show whether each episode has:
  - comic track link
  - animation track link
- link operators into `/comic` and `/sequences`
- explain that HollowForge is the production hub, not the final authoring tool

Nav update shape:

```tsx
{ to: '/production', label: 'Production Hub', icon: 'grid' }
{ to: '/sequences', label: 'Animation Track', icon: 'layers' }
{ to: '/comic', label: 'Comic Handoff', icon: 'book' }
```

Docs update requirements:

- `README.md` explains the boundary in one concise section
- `STATE.md` records that Phase A is "production hub core + boundary-first UI"
- add the smoke command to both docs

- [ ] **Step 4: Re-run the frontend test and targeted repo checks**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ProductionHub.test.tsx

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge
git diff -- README.md STATE.md
```

Expected: the frontend test passes and the docs diff clearly shows the new boundary language plus smoke command.

- [ ] **Step 5: Commit the production hub surface**

```bash
git add frontend/src/pages/ProductionHub.tsx \
  frontend/src/pages/ProductionHub.test.tsx \
  frontend/src/api/client.ts \
  frontend/src/App.tsx \
  README.md \
  STATE.md
git commit -m "feat(hollowforge): add production hub landing surface"
```

## Final Verification

- Run backend targeted tests:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 -m pytest \
  tests/test_comic_schema.py \
  tests/test_sequence_schema.py \
  tests/test_production_routes.py \
  tests/test_comic_repository.py \
  tests/test_comic_routes.py \
  tests/test_comic_dialogue_service.py \
  tests/test_sequence_routes.py \
  tests/test_launch_production_hub_smoke.py -q
```

- Run frontend targeted tests:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- \
  src/pages/ProductionHub.test.tsx \
  src/pages/ComicStudio.test.tsx \
  src/pages/SequenceStudio.test.tsx
```

- Run the smoke script:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
python3 scripts/launch_production_hub_smoke.py
```

Expected final state:

- one shared production episode can exist independently of any final editor
- that production episode can point to a comic track and an animation track
- comic dialogue routing follows episode `content_mode`
- `/comic` reads as a handoff workspace
- animation surfaces read as animation-track planning/review surfaces
- repo docs explain the product boundary clearly
