# HollowForge Character OS Comic MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 0 + Phase 1 Character OS needed to produce one `adult_nsfw` one-shot manga inside HollowForge, with teaser-animation handoff metadata but without full remote animation implementation.

**Architecture:** Reuse the existing `characters`, `character_versions`, `Story Planner`, `Sequence`, and `GenerationService` surfaces instead of inventing parallel systems. Add comic-side tables and services that turn an approved story-planner plan into `episodes -> scenes -> panels -> dialogues -> page assemblies`, queue panel render candidates through the existing image-generation stack, and export a lightweight page handoff package for manual finishing or later CLIP STUDIO EX integration.

**Tech Stack:** FastAPI, Pydantic, SQLite/aiosqlite, React 19, TypeScript, TanStack Query, Vitest, Pillow, ComfyUI, local LLM via OpenAI-compatible API

---

## Preconditions

- Follow `@superpowers:test-driven-development` while implementing each task.
- Follow `@superpowers:verification-before-completion` before claiming a task is done.
- The repo already contains `characters` and `character_versions` in [023_core_characters.sql](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/migrations/023_core_characters.sql). Do not create duplicate character tables.
- `GitNexus` currently fails outside the repo because the runtime install is broken. Treat that as an external ops follow-up; do not block in-repo Character OS work on it. Use `rg` locally until the tool is repaired, then rerun `gitnexus analyze` as a post-plan ops task.

## File Map

### Backend foundation

- Create: `backend/migrations/030_comic_character_os.sql`
  - Adds `comic_episodes`, `comic_episode_scenes`, `comic_scene_panels`, `comic_panel_dialogues`, `comic_panel_render_assets`, `comic_page_assemblies`
- Modify: `backend/app/config.py`
  - Adds comic data directories such as `DATA_DIR/comics/previews`, `DATA_DIR/comics/exports`, `DATA_DIR/comics/manifests`
- Modify: `backend/app/main.py`
  - Mounts new comic static directories and registers the comic router
- Modify: `backend/app/models.py`
  - Adds Pydantic request/response models for the new comic routes

### Backend comic services

- Create: `backend/app/services/comic_repository.py`
  - Thin CRUD/detail helpers for comic episode, scene, panel, dialogue, render asset, and page assembly state
- Create: `backend/app/services/comic_story_bridge_service.py`
  - Converts `StoryPlannerPlanResponse` into a comic episode draft with scenes/panels
- Create: `backend/app/services/comic_render_service.py`
  - Builds panel render prompts from `character_versions` + panel intent and queues candidate stills through `GenerationService`
- Create: `backend/app/services/comic_dialogue_service.py`
  - Generates `speech/thought/caption/sfx` drafts with the local LLM profile
- Create: `backend/app/services/comic_page_assembly_service.py`
  - Produces page preview PNGs plus JSON/ZIP handoff artifacts using fixed layout templates
- Create: `backend/app/routes/comic.py`
  - REST surface for character versions, comic episodes, story-plan import, panel render queueing, dialogue drafting, and page assembly/export

### Backend tests and smoke

- Create: `backend/tests/test_comic_schema.py`
- Create: `backend/tests/test_comic_repository.py`
- Create: `backend/tests/test_comic_story_bridge_service.py`
- Create: `backend/tests/test_comic_render_service.py`
- Create: `backend/tests/test_comic_dialogue_service.py`
- Create: `backend/tests/test_comic_page_assembly_service.py`
- Create: `backend/tests/test_comic_routes.py`
- Create: `backend/tests/test_launch_comic_mvp_smoke.py`
- Create: `backend/scripts/launch_comic_mvp_smoke.py`

### Frontend

- Modify: `frontend/src/api/client.ts`
  - Adds comic request/response types and API calls
- Modify: `frontend/src/App.tsx`
  - Adds `/comic` route and sidebar entry
- Create: `frontend/src/pages/ComicStudio.tsx`
  - Main operator page for the one-shot workflow
- Create: `frontend/src/pages/ComicStudio.test.tsx`
- Create: `frontend/src/components/comic/ComicEpisodeDraftPanel.tsx`
- Create: `frontend/src/components/comic/ComicPanelBoard.tsx`
- Create: `frontend/src/components/comic/ComicDialogueEditor.tsx`
- Create: `frontend/src/components/comic/ComicPageAssemblyPanel.tsx`

### Docs

- Modify: `README.md`
  - Adds Comic Studio entry points and verification commands
- Modify: `STATE.md`
  - Adds resume notes and current scope for Character OS Comic MVP

## Task 1: Add Comic Schema, Config, And API Models

**Files:**
- Create: `backend/migrations/030_comic_character_os.sql`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_comic_schema.py`

- [ ] **Step 1: Write the failing schema/model tests**

```python
async def test_comic_tables_are_created_by_init_db():
    await init_db()
    async with get_db() as db:
        names = {
            row["name"]
            for row in await (await db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )).fetchall()
        }
    assert "comic_episodes" in names
    assert "comic_scene_panels" in names
    assert "comic_page_assemblies" in names

def test_comic_episode_create_requires_character_version():
    with pytest.raises(ValidationError):
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            title="Night Intake",
            synopsis="...",
        )
```

- [ ] **Step 2: Run the schema/model tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_schema.py -q
```

Expected: FAIL because the migration, config dirs, and comic models do not exist yet.

- [ ] **Step 3: Add the migration, config paths, static mounts, and Pydantic models**

```sql
CREATE TABLE IF NOT EXISTS comic_episodes (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    character_version_id TEXT NOT NULL,
    title TEXT NOT NULL,
    synopsis TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    continuity_summary TEXT,
    canon_delta TEXT,
    target_output TEXT NOT NULL DEFAULT 'oneshot_manga',
    source_story_plan_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (character_version_id) REFERENCES character_versions(id) ON DELETE CASCADE
);
```

```python
class ComicEpisodeCreate(BaseModel):
    character_id: str = Field(min_length=1, max_length=120)
    character_version_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    synopsis: str = Field(min_length=1, max_length=4000)
    continuity_summary: Optional[str] = Field(default=None, max_length=4000)
```

```python
class Settings:
    COMICS_DIR: Path = DATA_DIR / "comics"
    COMICS_PREVIEWS_DIR: Path = COMICS_DIR / "previews"
    COMICS_EXPORTS_DIR: Path = COMICS_DIR / "exports"
    COMICS_MANIFESTS_DIR: Path = COMICS_DIR / "manifests"
```

- [ ] **Step 4: Run the schema/model tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_schema.py -q
./.venv/bin/python -m compileall app
```

Expected: PASS for `test_comic_schema.py`; `compileall` completes without syntax errors.

- [ ] **Step 5: Commit the foundation**

```bash
git add backend/migrations/030_comic_character_os.sql \
  backend/app/config.py \
  backend/app/main.py \
  backend/app/models.py \
  backend/tests/test_comic_schema.py
git commit -m "feat(hollowforge): add comic character os schema"
```

## Task 2: Build The Comic Repository And Core Read APIs

**Files:**
- Create: `backend/app/services/comic_repository.py`
- Create: `backend/app/routes/comic.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_comic_repository.py`
- Test: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write failing repository and route tests**

```python
async def test_create_episode_and_fetch_detail():
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Night Intake",
            synopsis="A controlled intake scene."
        )
    )
    detail = await get_comic_episode_detail(episode.id)
    assert detail.episode.id == episode.id
    assert detail.panels == []


def test_list_character_versions_returns_existing_seeded_versions(client):
    response = client.get("/api/v1/comic/character-versions")
    assert response.status_code == 200
    assert any(row["id"] == "charver_kaede_ren_still_v1" for row in response.json())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_repository.py tests/test_comic_routes.py -q
```

Expected: FAIL because the repository and routes do not exist.

- [ ] **Step 3: Implement the repository and core comic routes**

Core repository shape:

```python
async def create_comic_episode(payload: ComicEpisodeCreate, *, episode_id: str | None = None) -> ComicEpisodeResponse: ...
async def list_comic_character_versions(character_id: str | None = None) -> list[ComicCharacterVersionResponse]: ...
async def get_comic_episode_detail(episode_id: str) -> ComicEpisodeDetailResponse | None: ...
```

Core route surface:

```python
router = APIRouter(prefix="/api/v1/comic", tags=["comic"])

@router.get("/characters", response_model=list[ComicCharacterResponse])
@router.get("/character-versions", response_model=list[ComicCharacterVersionResponse])
@router.post("/episodes", response_model=ComicEpisodeDetailResponse, status_code=201)
@router.get("/episodes", response_model=list[ComicEpisodeSummaryResponse])
@router.get("/episodes/{episode_id}", response_model=ComicEpisodeDetailResponse)
```

- [ ] **Step 4: Run the repository and route tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_repository.py tests/test_comic_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the repository and API foundation**

```bash
git add backend/app/services/comic_repository.py \
  backend/app/routes/comic.py \
  backend/app/main.py \
  backend/tests/test_comic_repository.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): add comic repository and routes"
```

## Task 3: Bridge Story Planner Into Episode, Scene, And Panel Drafts

**Files:**
- Create: `backend/app/services/comic_story_bridge_service.py`
- Modify: `backend/app/routes/comic.py`
- Test: `backend/tests/test_comic_story_bridge_service.py`
- Test: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write failing bridge tests**

```python
def test_story_plan_bridge_expands_four_story_shots_into_eight_panels():
    detail = build_comic_draft_from_story_plan(
        approved_plan=story_plan_fixture(),
        character_version_id="charver_kaede_ren_still_v1",
        panel_multiplier=2,
    )
    assert len(detail.scenes) == 4
    assert len(detail.panels) == 8
    assert detail.panels[0].dialogue_intent


def test_import_story_plan_route_persists_episode(client):
    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": story_plan_fixture_payload(),
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "Night Intake"
        },
    )
    assert response.status_code == 201
    assert response.json()["episode"]["title"] == "Night Intake"
```

- [ ] **Step 2: Run the bridge tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_story_bridge_service.py tests/test_comic_routes.py -q
```

Expected: FAIL because the bridge service and import route are missing.

- [ ] **Step 3: Implement the bridge service and import endpoint**

Bridge shape:

```python
def build_comic_draft_from_story_plan(
    *,
    approved_plan: StoryPlannerPlanResponse,
    character_version_id: str,
    title: str,
    panel_multiplier: int = 2,
) -> ComicEpisodeDraft:
    ...
```

Import route shape:

```python
@router.post(
    "/episodes/import-story-plan",
    response_model=ComicEpisodeDetailResponse,
    status_code=201,
)
async def import_story_plan(payload: ComicStoryPlanImportRequest) -> ComicEpisodeDetailResponse:
    ...
```

Implementation rules:

- keep `Story Planner` deterministic and untouched
- persist the approved plan JSON on `comic_episodes.source_story_plan_json`
- create one scene per story-planner shot
- create `panel_multiplier` panels per scene with predictable reading order
- store `dialogue_intent` placeholders, not final text

- [ ] **Step 4: Run the bridge tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_story_bridge_service.py tests/test_comic_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the bridge**

```bash
git add backend/app/services/comic_story_bridge_service.py \
  backend/app/routes/comic.py \
  backend/tests/test_comic_story_bridge_service.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): import story planner plans into comic drafts"
```

## Task 4: Queue Panel Render Candidates And Select Winning Assets

**Files:**
- Create: `backend/app/services/comic_render_service.py`
- Modify: `backend/app/routes/comic.py`
- Test: `backend/tests/test_comic_render_service.py`
- Test: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write failing render-service tests**

```python
async def test_queue_panel_render_candidates_uses_character_version_defaults(fake_generation_service):
    queued = await queue_panel_render_candidates(
        panel=panel_fixture(),
        character_version=character_version_fixture(),
        generation_service=fake_generation_service,
        candidate_count=3,
    )
    assert queued.requested_count == 3
    assert queued.assets[0].generation_id.startswith("gen_")


def test_select_panel_render_asset_marks_one_asset_selected(client):
    response = client.post(
        f"/api/v1/comic/panels/{panel_id}/assets/{asset_id}/select"
    )
    assert response.status_code == 200
    assert response.json()["selected"] is True
```

- [ ] **Step 2: Run the render tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_render_service.py tests/test_comic_routes.py -q
```

Expected: FAIL because panel render queueing and asset selection do not exist yet.

- [ ] **Step 3: Implement the render queue service and routes**

Queue service shape:

```python
async def queue_panel_render_candidates(
    *,
    panel_id: str,
    generation_service: GenerationService,
    candidate_count: int = 3,
) -> ComicPanelRenderQueueResponse:
    ...
```

Prompt-building rule:

```python
prompt = ", ".join(
    [
        character_version.prompt_prefix,
        character.canonical_prompt_anchor,
        panel.action_intent,
        panel.expression_intent,
        panel.framing,
    ]
)
```

Route surface:

```python
@router.post("/panels/{panel_id}/queue-renders", response_model=ComicPanelRenderQueueResponse)
@router.post("/panels/{panel_id}/assets/{asset_id}/select", response_model=ComicPanelRenderAssetResponse)
```

Implementation rules:

- reuse `GenerationService.queue_generation_batch`
- store `generation_id` in `comic_panel_render_assets`
- keep one selected asset per panel
- keep prompt/negative/checkpoint snapshot for reproducibility

- [ ] **Step 4: Run the render tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_render_service.py tests/test_comic_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the panel render flow**

```bash
git add backend/app/services/comic_render_service.py \
  backend/app/routes/comic.py \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): queue comic panel render candidates"
```

## Task 5: Draft Dialogue And Produce Page Handoff Exports

**Files:**
- Create: `backend/app/services/comic_dialogue_service.py`
- Create: `backend/app/services/comic_page_assembly_service.py`
- Modify: `backend/app/routes/comic.py`
- Test: `backend/tests/test_comic_dialogue_service.py`
- Test: `backend/tests/test_comic_page_assembly_service.py`
- Test: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write failing dialogue and page-assembly tests**

```python
async def test_generate_panel_dialogues_returns_speech_caption_and_sfx(monkeypatch):
    result = await generate_panel_dialogues(
        panel=panel_fixture(),
        scene=scene_fixture(),
        episode=episode_fixture(),
        character=character_fixture(),
    )
    assert any(line.type == "speech" for line in result.lines)
    assert any(line.type == "sfx" for line in result.lines)


async def test_assemble_episode_pages_writes_preview_png_and_manifest(tmp_path):
    result = await assemble_episode_pages(
        episode_id="ep_123",
        layout_template_id="jp_2x2_v1",
    )
    assert result.pages[0].preview_path.endswith(".png")
    assert result.export_manifest_path.endswith(".json")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_dialogue_service.py tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
```

Expected: FAIL because dialogue drafting and page assembly are not implemented.

- [ ] **Step 3: Implement dialogue generation and page assembly/export**

Dialogue service shape:

```python
async def generate_panel_dialogues(
    *,
    panel_id: str,
    overwrite_existing: bool = False,
) -> ComicDialogueGenerationResponse:
    ...
```

Page assembly/export shape:

```python
async def assemble_episode_pages(
    *,
    episode_id: str,
    layout_template_id: str = "jp_2x2_v1",
) -> ComicPageAssemblyResponse:
    ...
```

Implementation rules:

- use the local LLM profile first for `adult_nsfw` dialogue drafting
- generate `speech`, `caption`, and `sfx` lines as separate rows
- use fixed Japanese-style page templates such as `jp_2x2_v1` and `jp_3row_v1`
- render simple preview text boxes with Pillow for MVP
- export a handoff ZIP containing:
  - page preview PNGs
  - dialogue JSON
  - panel asset manifest JSON
  - page assembly manifest JSON
- do not attempt polished speech-balloon vector drawing in MVP

Route surface:

```python
@router.post("/panels/{panel_id}/dialogues/generate", response_model=ComicDialogueGenerationResponse)
@router.post("/episodes/{episode_id}/pages/assemble", response_model=ComicPageAssemblyResponse)
@router.post("/episodes/{episode_id}/pages/export", response_model=ComicPageExportResponse)
```

- [ ] **Step 4: Run the dialogue and page-assembly tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_dialogue_service.py tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the dialogue/export layer**

```bash
git add backend/app/services/comic_dialogue_service.py \
  backend/app/services/comic_page_assembly_service.py \
  backend/app/routes/comic.py \
  backend/tests/test_comic_dialogue_service.py \
  backend/tests/test_comic_page_assembly_service.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): add comic dialogue and page export"
```

## Task 6: Build The Comic Studio Frontend

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/pages/ComicStudio.tsx`
- Create: `frontend/src/pages/ComicStudio.test.tsx`
- Create: `frontend/src/components/comic/ComicEpisodeDraftPanel.tsx`
- Create: `frontend/src/components/comic/ComicPanelBoard.tsx`
- Create: `frontend/src/components/comic/ComicDialogueEditor.tsx`
- Create: `frontend/src/components/comic/ComicPageAssemblyPanel.tsx`

- [ ] **Step 1: Write the failing frontend test**

```tsx
test('imports a story plan and walks through render, dialogue, and page assembly actions', async () => {
  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeEnabled()
  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()
})
```

- [ ] **Step 2: Run the frontend test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx
```

Expected: FAIL because the page, API client types, and route do not exist.

- [ ] **Step 3: Implement the Comic Studio page and API hooks**

Frontend responsibilities:

```tsx
<ComicEpisodeDraftPanel />
<ComicPanelBoard />
<ComicDialogueEditor />
<ComicPageAssemblyPanel />
```

API surface to add in `client.ts`:

```ts
export async function importComicStoryPlan(data: ComicStoryPlanImportRequest): Promise<ComicEpisodeDetailResponse> { ... }
export async function queueComicPanelRenders(panelId: string, data: ComicPanelRenderQueueRequest): Promise<ComicPanelRenderQueueResponse> { ... }
export async function generateComicPanelDialogues(panelId: string): Promise<ComicDialogueGenerationResponse> { ... }
export async function assembleComicEpisodePages(episodeId: string): Promise<ComicPageAssemblyResponse> { ... }
export async function exportComicEpisodePages(episodeId: string): Promise<ComicPageExportResponse> { ... }
```

UI rules:

- do not hide lineage; always show `character`, `character version`, `episode`, `scene`, `panel`
- show selected panel asset clearly
- keep the page focused on one episode at a time
- do not merge Comic Studio into Prompt Factory or Marketing in MVP

- [ ] **Step 4: Run the frontend test and production build**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx
npm run lint
npm run build
```

Expected: PASS for the targeted test; lint/build succeed.

- [ ] **Step 5: Commit the frontend**

```bash
git add frontend/src/api/client.ts \
  frontend/src/App.tsx \
  frontend/src/pages/ComicStudio.tsx \
  frontend/src/pages/ComicStudio.test.tsx \
  frontend/src/components/comic
git commit -m "feat(hollowforge): add comic studio frontend"
```

## Task 7: Add Smoke Coverage, Update Docs, And Run End-To-End Verification

**Files:**
- Create: `backend/scripts/launch_comic_mvp_smoke.py`
- Create: `backend/tests/test_launch_comic_mvp_smoke.py`
- Modify: `README.md`
- Modify: `STATE.md`
- Test: `backend/tests/test_launch_comic_mvp_smoke.py`
- Test: `frontend/src/pages/ComicStudio.test.tsx`

- [ ] **Step 1: Write the smoke-script expectation and doc assertions**

```python
def test_comic_smoke_script_can_import_episode_and_list_it():
    result = subprocess.run([...], capture_output=True, text=True)
    assert "import_success: true" in result.stdout
    assert "episode_id:" in result.stdout
```

Doc updates must include:

- backend route entry points
- frontend route `/comic`
- verification commands
- current MVP scope (`one character / one one-shot / one teaser derivative`)

- [ ] **Step 2: Run the docs/smoke tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_launch_comic_mvp_smoke.py -q
```

Expected: FAIL or missing-script errors until the smoke script and docs are in place.

- [ ] **Step 3: Implement the smoke script and docs**

Smoke script shape:

```python
"""
Launch a bounded Comic MVP smoke run:
1. import a story plan into a comic episode
2. queue panel renders for the first panel
3. draft dialogues
4. assemble pages
5. print episode/page/export ids
"""
```

Verification commands to add to docs:

```bash
cd backend
./.venv/bin/python -m pytest tests/test_comic_schema.py tests/test_comic_repository.py tests/test_comic_story_bridge_service.py tests/test_comic_render_service.py tests/test_comic_dialogue_service.py tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
./.venv/bin/python -m pytest tests/test_launch_comic_mvp_smoke.py -q

cd ../frontend
npm test -- src/pages/ComicStudio.test.tsx
npm run lint
npm run build
```

- [ ] **Step 4: Run the full bounded verification set**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_schema.py tests/test_comic_repository.py tests/test_comic_story_bridge_service.py tests/test_comic_render_service.py tests/test_comic_dialogue_service.py tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
./.venv/bin/python -m pytest tests/test_launch_comic_mvp_smoke.py -q
./.venv/bin/python scripts/launch_comic_mvp_smoke.py --base-url http://127.0.0.1:8000

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx
npm run lint
npm run build
```

Expected:

- backend comic tests PASS
- smoke script reports successful import/render/dialogue/assembly steps
- frontend test PASS
- lint PASS
- build PASS

- [ ] **Step 5: Commit the smoke/docs pass**

```bash
git add backend/scripts/launch_comic_mvp_smoke.py \
  backend/tests/test_launch_comic_mvp_smoke.py \
  README.md \
  STATE.md \
  frontend/src/pages/ComicStudio.test.tsx
git commit -m "docs(hollowforge): document comic mvp workflow"
```

## Post-Plan Ops Follow-Up

This item is intentionally outside the repo implementation scope:

- repair `GitNexus` runtime in the user environment
- rerun:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research
/Users/mori_arty/.npm/_npx/e46929201c1128dd/node_modules/.bin/gitnexus analyze
```

- if it still fails, document the exact runtime issue separately instead of mixing it into the Character OS feature branch
