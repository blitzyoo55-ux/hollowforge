# HollowForge Comic Production Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the existing Comic MVP so one canonical one-shot can be completed as a repeatable production dry run and exported as a Japanese manuscript handoff package.

**Architecture:** Reuse the existing comic episode/panel/page stack and extend it with a persisted `manuscript_profile_id`, richer handoff artifacts, and a dry-run reporting surface. Keep HollowForge as the creative source of truth, keep CLIP STUDIO EX as the manual finishing master, and avoid native `.clip` generation or new duplicate asset systems.

**Tech Stack:** FastAPI, Pydantic, SQLite/aiosqlite, React 19, TypeScript, TanStack Query, Vitest, pytest, Pillow, Markdown docs

---

## Preconditions

- Follow `@superpowers:test-driven-development` while implementing each task.
- Follow `@superpowers:verification-before-completion` before claiming any task or checkpoint is complete.
- Treat [2026-04-04-hollowforge-comic-production-handoff-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-os-comic-mvp/hollowforge/docs/superpowers/specs/2026-04-04-hollowforge-comic-production-handoff-design.md) as the source spec for this plan.
- Do not add native `.clip` or `.cmc` generation in this phase.
- Do not move teaser rendering into this plan; preserve teaser identity only.
- Keep `/comic` scoped to the freshly imported in-session episode; do not add an episode picker or reload-resume surface in this phase.
- Treat `launch_comic_mvp_smoke.py` as smoke-only; the new production dry-run helper must fail if synthetic placeholder fallback is involved.

## File Map

### Backend persistence and models

- Create: `backend/migrations/031_comic_manuscript_profile.sql`
  - adds `manuscript_profile_id` to `comic_page_assemblies`
- Modify: `backend/app/config.py`
  - adds `DATA_DIR/comics/reports` for local dry-run report output
- Modify: `backend/app/models.py`
  - adds manuscript profile literals and response payloads
- Modify: `backend/app/routes/comic.py`
  - adds manuscript profile read API and profile-aware assemble/export inputs

### Backend handoff generation

- Modify: `backend/app/services/comic_page_assembly_service.py`
  - stores manuscript profile selection, writes handoff profile/readme/checklist artifacts, and returns them in assembly/export responses
- Modify: `backend/app/services/comic_repository.py`
  - reads/writes persisted `manuscript_profile_id` on page assemblies

### Backend tests and scripts

- Modify: `backend/tests/test_comic_schema.py`
- Modify: `backend/tests/test_comic_routes.py`
- Modify: `backend/tests/test_comic_page_assembly_service.py`
- Create: `backend/tests/test_launch_comic_production_dry_run.py`
- Create: `backend/scripts/launch_comic_production_dry_run.py`

### Frontend

- Modify: `frontend/src/api/client.ts`
  - adds manuscript profile types and profile-aware assemble/export signatures
- Modify: `frontend/src/pages/ComicStudio.tsx`
  - threads manuscript profile selection and production-handoff readiness through the page
- Modify: `frontend/src/components/comic/ComicPageAssemblyPanel.tsx`
  - shows manuscript profile, export contents, and next-step guidance
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

### Docs

- Create: `docs/HOLLOWFORGE_COMIC_PRODUCTION_DRY_RUN_20260404.md`
  - canonical operator runbook for the first one-shot
- Modify: `README.md`
  - publishes production dry-run and handoff verification commands
- Modify: `STATE.md`
  - updates the repo snapshot and resume notes for Phase 1.5

## Task 1: Persist Manuscript Profile State

**Files:**
- Create: `backend/migrations/031_comic_manuscript_profile.sql`
- Modify: `backend/app/config.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/comic.py`
- Modify: `backend/tests/test_comic_schema.py`
- Modify: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write failing schema and route tests**

```python
async def test_comic_page_assemblies_store_manuscript_profile_id():
    await init_db()
    async with get_db() as db:
        columns = {
            row["name"]
            for row in await (
                await db.execute("PRAGMA table_info(comic_page_assemblies)")
            ).fetchall()
        }
    assert "manuscript_profile_id" in columns


def test_list_comic_manuscript_profiles(client):
    response = client.get("/api/v1/comic/manuscript-profiles")
    assert response.status_code == 200
    assert response.json()[0]["id"] == "jp_manga_rightbound_v1"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_schema.py tests/test_comic_routes.py -q
```

Expected: FAIL because the migration, models, and read route do not exist.

- [ ] **Step 3: Add the migration, types, and read route**

Migration shape:

```sql
ALTER TABLE comic_page_assemblies
ADD COLUMN manuscript_profile_id TEXT NOT NULL DEFAULT 'jp_manga_rightbound_v1';
```

Model shape:

```python
ComicManuscriptProfileId = Literal["jp_manga_rightbound_v1"]


class ComicManuscriptProfileResponse(BaseModel):
    id: ComicManuscriptProfileId
    label: str
    binding_direction: Literal["right_to_left"]
    finishing_tool: Literal["clip_studio_ex"]
    print_intent: Literal["japanese_manga"]
    trim_reference: str
    bleed_reference: str
    safe_area_reference: str
    naming_pattern: str
```

Route shape:

```python
@router.get("/manuscript-profiles", response_model=list[ComicManuscriptProfileResponse])
async def get_comic_manuscript_profiles() -> list[ComicManuscriptProfileResponse]:
    return list_comic_manuscript_profiles()
```

- [ ] **Step 4: Run the schema and route tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_schema.py tests/test_comic_routes.py -q
```

Expected: PASS with the new profile schema and route in place.

- [ ] **Step 5: Commit the persisted profile foundation**

```bash
git add backend/migrations/031_comic_manuscript_profile.sql \
  backend/app/config.py \
  backend/app/models.py \
  backend/app/routes/comic.py \
  backend/tests/test_comic_schema.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): persist comic manuscript profiles"
```

## Task 2: Upgrade Assembly And Export To Handoff Package V2

**Files:**
- Modify: `backend/app/services/comic_page_assembly_service.py`
- Modify: `backend/app/services/comic_repository.py`
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_comic_page_assembly_service.py`
- Modify: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write failing service and route tests**

```python
async def test_export_episode_pages_writes_manuscript_profile_artifacts():
    result = await export_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
        manuscript_profile_id="jp_manga_rightbound_v1",
    )
    assert result.manuscript_profile["id"] == "jp_manga_rightbound_v1"
    assert result.manuscript_profile_manifest_path.endswith("_manuscript_profile.json")
    assert result.handoff_readme_path.endswith("_handoff_readme.md")
    assert result.production_checklist_path.endswith("_production_checklist.json")
```

```python
def test_export_route_accepts_manuscript_profile_id(client):
    response = client.post(
        f"/api/v1/comic/episodes/{episode_id}/pages/export",
        params={
            "layout_template_id": "jp_2x2_v1",
            "manuscript_profile_id": "jp_manga_rightbound_v1",
        },
    )
    assert response.status_code == 201
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
```

Expected: FAIL because assembly/export responses do not yet include the new handoff artifacts.

- [ ] **Step 3: Implement the V2 handoff package**

Required behavior:

- `assemble_episode_pages()` and `export_episode_pages()` must accept `manuscript_profile_id`
- the selected profile must be persisted on every assembled/exported page row
- handoff artifacts must be written under `data/comics/manifests/`
- export must write:
  - `*_manuscript_profile.json`
  - `*_handoff_readme.md`
  - `*_production_checklist.json`
- ZIP export must include those files alongside the existing manifests, previews, and selected asset files
- assembly/export API responses must expose the new artifact paths so `/comic` can render them without opening raw JSON

Suggested helper shape:

```python
def _resolve_manuscript_profile(profile_id: ComicManuscriptProfileId) -> dict[str, Any]: ...
def _write_handoff_readme(... ) -> str: ...
def _write_production_checklist(... ) -> str: ...
```

- [ ] **Step 4: Run the service and route tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
```

Expected: PASS with the new artifact files and response payloads present.

- [ ] **Step 5: Commit the handoff package upgrade**

```bash
git add backend/app/services/comic_page_assembly_service.py \
  backend/app/services/comic_repository.py \
  backend/app/models.py \
  backend/tests/test_comic_page_assembly_service.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): upgrade comic handoff package"
```

## Task 3: Surface Handoff Readiness In Comic Studio

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ComicStudio.tsx`
- Modify: `frontend/src/components/comic/ComicPageAssemblyPanel.tsx`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

```tsx
it('shows the manuscript profile selector and sends it on export', async () => {
  render(<ComicStudio />)
  // ...load episode...
  await user.selectOptions(screen.getByLabelText(/manuscript profile/i), 'jp_manga_rightbound_v1')
  await user.click(screen.getByRole('button', { name: /Export Handoff ZIP/i }))
  expect(exportComicEpisodePages).toHaveBeenCalledWith(
    'ep-1',
    'jp_2x2_v1',
    'jp_manga_rightbound_v1',
  )
})
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx
```

Expected: FAIL because the UI and client do not yet carry manuscript profile state.

- [ ] **Step 3: Implement the profile-aware UI**

UI requirements:

- show `Manuscript Profile` separately from `Layout Template`
- keep the page scoped to the current imported episode only; no episode reload selector in this phase
- keep readiness copy explicit:
  - layout template = page composition
  - manuscript profile = print/handoff intent
- show latest export summary with:
  - export zip path
  - manuscript profile id
  - handoff readme path
  - production checklist path

Client signature target:

```ts
export async function assembleComicEpisodePages(
  episodeId: string,
  layoutTemplateId: ComicPageLayoutTemplateId,
  manuscriptProfileId: ComicManuscriptProfileId,
): Promise<ComicPageAssemblyBatchResponse> { ... }
```

- [ ] **Step 4: Run the targeted frontend test again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx
```

Expected: PASS with the new selector and export behavior.

- [ ] **Step 5: Commit the frontend handoff UX**

```bash
git add frontend/src/api/client.ts \
  frontend/src/pages/ComicStudio.tsx \
  frontend/src/components/comic/ComicPageAssemblyPanel.tsx \
  frontend/src/pages/ComicStudio.test.tsx
git commit -m "feat(hollowforge): expose comic manuscript handoff state"
```

## Task 4: Add The Production Dry-Run Helper And Runbook

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/scripts/launch_comic_production_dry_run.py`
- Create: `backend/tests/test_launch_comic_production_dry_run.py`
- Create: `docs/HOLLOWFORGE_COMIC_PRODUCTION_DRY_RUN_20260404.md`

- [ ] **Step 1: Write the failing dry-run script test**

```python
def test_dry_run_script_prints_report_markers(tmp_path):
    result = subprocess.run([...], capture_output=True, text=True)
    assert "dry_run_success: true" in result.stdout
    assert "report_path:" in result.stdout
    assert "manuscript_profile_id: jp_manga_rightbound_v1" in result.stdout
```

- [ ] **Step 2: Run the dry-run test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_launch_comic_production_dry_run.py -q
```

Expected: FAIL because the helper script does not exist yet.

- [ ] **Step 3: Implement the helper script and runbook**

Script behavior:

- accepts `--base-url`, `--episode-id`, `--layout-template-id`, `--manuscript-profile-id`
- calls assemble/export if needed
- fetches episode/export detail
- writes a local JSON report under `data/comics/reports/`
- refuses synthetic placeholder fallback; this helper is for production validation, not smoke fallback
- prints markers for:
  - `dry_run_success`
  - `episode_id`
  - `panel_count`
  - `selected_panel_asset_count`
  - `page_count`
  - `manuscript_profile_id`
  - `report_path`

Runbook requirements:

- canonical operator order
- what must be selected before handoff
- what to inspect inside the ZIP
- what to do next in CLIP STUDIO EX

- [ ] **Step 4: Run the dry-run script test again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_launch_comic_production_dry_run.py -q
```

Expected: PASS with the report markers and report file path present.

- [ ] **Step 5: Commit the dry-run tooling**

```bash
git add backend/scripts/launch_comic_production_dry_run.py \
  backend/app/config.py \
  backend/tests/test_launch_comic_production_dry_run.py \
  docs/HOLLOWFORGE_COMIC_PRODUCTION_DRY_RUN_20260404.md
git commit -m "feat(hollowforge): add comic production dry-run tooling"
```

## Task 5: Update Repo Docs And Re-Run Full Verification

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`
- Test: `backend/tests/test_comic_schema.py`
- Test: `backend/tests/test_comic_routes.py`
- Test: `backend/tests/test_comic_page_assembly_service.py`
- Test: `backend/tests/test_launch_comic_production_dry_run.py`
- Test: `frontend/src/pages/ComicStudio.test.tsx`

- [ ] **Step 1: Update repo docs for Phase 1.5**

README must include:

- manuscript profile route/API mention
- production dry-run command
- handoff export verification commands

STATE must include:

- current phase is production dry run + Japanese handoff hardening
- `/comic` now carries manuscript profile selection
- dry-run helper script entry point

- [ ] **Step 2: Run backend verification**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_schema.py tests/test_comic_routes.py tests/test_comic_page_assembly_service.py tests/test_launch_comic_production_dry_run.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm test -- src/pages/ComicStudio.test.tsx
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 4: Run the live dry-run helper against a local API**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
HOLLOWFORGE_PUBLIC_API_BASE_URL=http://127.0.0.1:8010 ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
./.venv/bin/python scripts/launch_comic_mvp_smoke.py --base-url http://127.0.0.1:8010
./.venv/bin/python scripts/launch_comic_production_dry_run.py --base-url http://127.0.0.1:8010 --episode-id <episode_id>
```

Expected: both scripts exit 0, and the dry-run helper prints `dry_run_success: true`.

- [ ] **Step 5: Commit the repo docs and verification pass**

```bash
git add README.md STATE.md
git commit -m "docs(hollowforge): publish comic production handoff flow"
```
