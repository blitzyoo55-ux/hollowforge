# HollowForge Layered Comic Handoff Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade HollowForge comic export from a preview-plus-manifest ZIP into a layered handoff package with art/frame/balloon/text-draft contracts, review-time validation, and a stricter export gate that still preserves the existing API and artifact surface additively.

**Architecture:** Keep the existing `/comic -> assemble -> export` flow and extend it additively. Backend assembly/export remains the source of truth and writes new layered artifacts plus validation output without removing legacy manifests. Frontend keeps the current episode-scoped workspace but splits the handoff stage into `Pages` and `Handoff` surfaces so operators can review geometry and validation before export.

**Tech Stack:** FastAPI, Pydantic, SQLite/aiosqlite, Python filesystem packaging helpers, React 19, TypeScript, TanStack Query, Vitest, pytest, Markdown docs

---

## Preconditions

- Follow `@superpowers:test-driven-development` while implementing each task.
- Follow `@superpowers:verification-before-completion` before claiming any task or checkpoint is complete.
- Treat [2026-04-14-hollowforge-layered-comic-handoff-package-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/docs/superpowers/specs/2026-04-14-hollowforge-layered-comic-handoff-package-design.md) as the source spec for this plan.
- Do not add native `.clip` or `.cmc` generation in this phase.
- Do not add freeform anchor-edit UI in this phase.
- Keep all existing `ComicPageAssemblyBatchResponse` and `ComicPageExportResponse` fields stable; additive-only changes only.
- Keep all legacy manifest filenames and ZIP artifact names stable; new layered files must be added alongside them.
- Keep `/comic` scoped to the currently loaded episode; do not add a new episode picker or long-term persisted export-history system in this phase.

## File Map

### Backend models and response contract

- Modify: `backend/app/models.py`
  - add typed layered package metadata, validation summary, page summary, and additive response fields
- Modify: `backend/app/routes/comic.py`
  - keep existing routes, but ensure updated response models flow through assemble/export endpoints

### Backend assembly/export generation

- Modify: `backend/app/services/comic_page_assembly_service.py`
  - write root layered manifest, page-scoped layer files, panel manifests, validation artifact, and upgraded ZIP contents
- Modify: `backend/app/services/comic_repository.py`
  - only if needed to expose newly returned page/export metadata consistently through existing episode detail flows

### Backend tests and smoke scripts

- Modify: `backend/tests/test_comic_page_assembly_service.py`
- Modify: `backend/tests/test_comic_routes.py`
- Modify: `backend/tests/test_launch_comic_production_dry_run.py`
- Modify: `backend/tests/test_launch_comic_remote_one_shot_dry_run.py`
- Modify: `backend/scripts/launch_comic_production_dry_run.py`
- Modify: `backend/scripts/launch_comic_remote_one_shot_dry_run.py`

### Frontend API and handoff review UI

- Modify: `frontend/src/api/client.ts`
  - add layered manifest and validation response types
- Modify: `frontend/src/pages/ComicStudio.tsx`
  - track active handoff surface, validation state, and stricter export gating
- Modify: `frontend/src/components/comic/ComicPageAssemblyPanel.tsx`
  - keep page assembly focused on `Pages` review and additive package metadata
- Create: `frontend/src/components/comic/ComicHandoffReviewPanel.tsx`
  - render layer readiness, validation summary, and export checklist
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

### Docs

- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`
  - insert `Handoff Review` stage and layered-package expectations
- Modify: `README.md`
  - publish the layered handoff contract and updated smoke expectations
- Modify: `STATE.md`
  - update snapshot and resume guidance for layered package / handoff review

## Task 1: Lock The Backend Response Contract

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/comic.py`
- Modify: `backend/tests/test_comic_page_assembly_service.py`
- Modify: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write failing backend contract tests**

```python
async def test_assemble_episode_pages_returns_layered_manifest_metadata():
    result = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
        manuscript_profile_id="jp_manga_rightbound_v1",
    )
    assert result.layered_manifest_path.endswith("/manifest.json")
    assert result.handoff_validation_path.endswith("/handoff_validation.json")
    assert result.page_summaries[0].frame_layer_status == "complete"


def test_export_route_preserves_legacy_fields_and_adds_layered_fields(client):
    response = client.post(f"/api/v1/comic/episodes/{episode_id}/pages/export")
    body = response.json()
    assert "page_assembly_manifest_path" in body
    assert "layered_manifest_path" in body
    assert "handoff_validation_path" in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
```

Expected: FAIL because the assemble/export responses do not yet expose layered package metadata or page summaries.

- [ ] **Step 3: Add additive response models**

Model shape to add:

```python
class ComicHandoffPageSummaryResponse(BaseModel):
    page_id: str
    page_no: int
    art_layer_status: Literal["complete", "warning", "blocked"]
    frame_layer_status: Literal["complete", "warning", "blocked"]
    balloon_layer_status: Literal["complete", "warning", "blocked"]
    text_draft_layer_status: Literal["complete", "warning", "blocked"]
    hard_block_count: int
    soft_warning_count: int


class ComicHandoffValidationResponse(BaseModel):
    episode_id: str
    hard_blocks: list[dict[str, Any]]
    soft_warnings: list[dict[str, Any]]
    page_summaries: list[ComicHandoffPageSummaryResponse]
    generated_at: str
```

Additive response fields to expose on both assembly/export responses:

```python
layered_manifest_path: str
handoff_validation_path: str
page_summaries: list[ComicHandoffPageSummaryResponse]
latest_export_summary: dict[str, Any] | None = None
```

- [ ] **Step 4: Re-run the backend contract tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
```

Expected: PASS with additive response fields present and legacy fields unchanged.

- [ ] **Step 5: Commit the response-contract slice**

```bash
git add backend/app/models.py \
  backend/app/routes/comic.py \
  backend/tests/test_comic_page_assembly_service.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): expose layered handoff response contract"
```

## Task 2: Generate The Layered Handoff Package

**Files:**
- Modify: `backend/app/services/comic_page_assembly_service.py`
- Modify: `backend/tests/test_comic_page_assembly_service.py`
- Modify: `backend/tests/test_comic_routes.py`

- [ ] **Step 1: Write failing service-level artifact tests**

```python
async def test_export_episode_pages_writes_layered_package_files():
    result = await export_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
        manuscript_profile_id="jp_manga_rightbound_v1",
    )
    assert (settings.DATA_DIR / result.layered_manifest_path).is_file()
    assert (settings.DATA_DIR / result.handoff_validation_path).is_file()
    assert zip_contains(result.export_zip_path, "pages/page_001/frame_layer.json")
    assert zip_contains(result.export_zip_path, "pages/page_001/balloon_layer.json")
    assert zip_contains(result.export_zip_path, "pages/page_001/text_draft_layer.json")
```

```python
async def test_assemble_episode_pages_keeps_legacy_manifest_outputs():
    result = await assemble_episode_pages(episode_id=episode_id)
    assert result.page_assembly_manifest_path.endswith("_pages.json")
    assert result.dialogue_json_path.endswith("_dialogues.json")
    assert result.layered_manifest_path.endswith("/manifest.json")
```

- [ ] **Step 2: Run the service tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
```

Expected: FAIL because the layered file tree, validation artifact, and additive ZIP contents do not yet exist.

- [ ] **Step 3: Implement layered package generation**

Required helper shape:

```python
def _build_page_manifest(... ) -> dict[str, Any]: ...
def _build_frame_layer(... ) -> dict[str, Any]: ...
def _build_balloon_layer(... ) -> dict[str, Any]: ...
def _build_text_draft_layer(... ) -> dict[str, Any]: ...
def _build_handoff_validation(... ) -> dict[str, Any]: ...
def _write_layered_package(... ) -> tuple[str, str, list[ComicHandoffPageSummaryResponse]]: ...
```

Required behavior:

- preserve all current legacy manifest writes
- add `pages/page_###/page_manifest.json`
- add `pages/page_###/frame_layer.json`
- add `pages/page_###/balloon_layer.json`
- add `pages/page_###/text_draft_layer.json`
- add `panels/panel_<panel_id>/panel_manifest.json`
- add `manifest.json` at package root
- add `handoff_validation.json` at package root
- treat existing page previews and selected render assets as the `art layer`
- mark layer status with `complete | warning | blocked`
- do not add subjective heuristics beyond the spec’s explicit soft warnings

- [ ] **Step 4: Update ZIP packaging**

ZIP behavior to enforce:

```python
artifact_paths = [
    page_response.dialogue_json_path,
    page_response.panel_asset_manifest_path,
    page_response.page_assembly_manifest_path,
    page_response.teaser_handoff_manifest_path,
    page_response.manuscript_profile_manifest_path,
    page_response.handoff_readme_path,
    page_response.production_checklist_path,
    page_response.layered_manifest_path,
    page_response.handoff_validation_path,
]
```

Also include:

- `pages/...` subtree files
- `panels/...` subtree files
- existing preview PNGs
- existing selected render assets

- [ ] **Step 5: Re-run the service and route tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
```

Expected: PASS with layered package files and additive legacy artifacts both present.

- [ ] **Step 6: Commit the backend package generator**

```bash
git add backend/app/services/comic_page_assembly_service.py \
  backend/tests/test_comic_page_assembly_service.py \
  backend/tests/test_comic_routes.py
git commit -m "feat(hollowforge): generate layered comic handoff package"
```

## Task 3: Upgrade Dry-Run Verification To The New Package

**Files:**
- Modify: `backend/scripts/launch_comic_production_dry_run.py`
- Modify: `backend/scripts/launch_comic_remote_one_shot_dry_run.py`
- Modify: `backend/tests/test_launch_comic_production_dry_run.py`
- Modify: `backend/tests/test_launch_comic_remote_one_shot_dry_run.py`

- [ ] **Step 1: Write failing dry-run checks**

```python
def test_launch_comic_production_dry_run_requires_layered_manifest():
    summary = run_dry_run(...)
    assert summary["layered_manifest_path"].endswith("/manifest.json")
    assert summary["handoff_validation_path"].endswith("/handoff_validation.json")
    assert summary["hard_block_count"] == 0
```

```python
def test_launch_comic_remote_one_shot_dry_run_validates_layered_zip_contents():
    summary = run_remote_one_shot(...)
    assert summary["page_count"] >= 1
    assert summary["layered_package_verified"] is True
```

- [ ] **Step 2: Run the dry-run tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
./.venv/bin/python -m pytest tests/test_launch_comic_production_dry_run.py tests/test_launch_comic_remote_one_shot_dry_run.py -q
```

Expected: FAIL because the scripts do not yet validate or report layered package artifacts.

- [ ] **Step 3: Extend the scripts**

Required behavior:

- check `layered_manifest_path`
- check `handoff_validation_path`
- fail on `hard_block_count > 0`
- confirm ZIP contains at least:
  - root `manifest.json`
  - root `handoff_validation.json`
  - one `pages/.../frame_layer.json`
  - one `pages/.../balloon_layer.json`
  - one `pages/.../text_draft_layer.json`

- [ ] **Step 4: Re-run the dry-run tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
./.venv/bin/python -m pytest tests/test_launch_comic_production_dry_run.py tests/test_launch_comic_remote_one_shot_dry_run.py -q
```

Expected: PASS with layered package validation added to both bounded operator scripts.

- [ ] **Step 5: Commit the dry-run verification slice**

```bash
git add backend/scripts/launch_comic_production_dry_run.py \
  backend/scripts/launch_comic_remote_one_shot_dry_run.py \
  backend/tests/test_launch_comic_production_dry_run.py \
  backend/tests/test_launch_comic_remote_one_shot_dry_run.py
git commit -m "feat(hollowforge): verify layered handoff package in dry runs"
```

## Task 4: Add `Pages` And `Handoff` Review Surfaces

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ComicStudio.tsx`
- Modify: `frontend/src/components/comic/ComicPageAssemblyPanel.tsx`
- Create: `frontend/src/components/comic/ComicHandoffReviewPanel.tsx`
- Modify: `frontend/src/pages/ComicStudio.test.tsx`

- [ ] **Step 1: Write failing frontend behavior tests**

```tsx
it('shows layered page readiness after assembly', async () => {
  render(<ComicStudio />)
  await user.click(screen.getByRole('button', { name: /Assemble Pages/i }))
  expect(await screen.findByText(/art layer readiness/i)).toBeInTheDocument()
  expect(screen.getByText(/frame layer readiness/i)).toBeInTheDocument()
})

it('blocks export when handoff validation has hard blocks', async () => {
  mockAssembleResponse({ page_summaries: [...], hard_block_count: 1 })
  render(<ComicStudio />)
  expect(screen.getByRole('button', { name: /Export Handoff ZIP/i })).toBeDisabled()
})

it('shows latest export summary with layered manifest and validation paths', async () => {
  mockExportResponse({ layered_manifest_path: 'comics/exports/.../manifest.json' })
  render(<ComicStudio />)
  expect(await screen.findByText(/handoff_validation/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ComicStudio.test.tsx
```

Expected: FAIL because the UI does not yet expose a dedicated handoff review surface or layered validation gating.

- [ ] **Step 3: Add frontend types and state**

Client shape to add:

```ts
export interface ComicHandoffPageSummaryResponse {
  page_id: string
  page_no: number
  art_layer_status: 'complete' | 'warning' | 'blocked'
  frame_layer_status: 'complete' | 'warning' | 'blocked'
  balloon_layer_status: 'complete' | 'warning' | 'blocked'
  text_draft_layer_status: 'complete' | 'warning' | 'blocked'
  hard_block_count: number
  soft_warning_count: number
}
```

`ComicStudio.tsx` state to add:

```ts
const [handoffSurface, setHandoffSurface] = useState<'pages' | 'handoff'>('pages')
const hardBlockCount = exportOrAssemblySummary?.hard_blocks.length ?? 0
const canExport = baseCanExport && hardBlockCount === 0
```

- [ ] **Step 4: Split `Pages` and `Handoff` rendering**

Required UI behavior:

- `ComicPageAssemblyPanel` becomes the `Pages` surface
- new `ComicHandoffReviewPanel` renders:
  - art/frame/balloon/text draft readiness
  - hard block / soft warning summary
  - latest export summary
  - export checklist
- export button disabled when `hard_block_count > 0`
- warning-only state still allows export

- [ ] **Step 5: Re-run the frontend test and build**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ComicStudio.test.tsx
npm run build
```

Expected: PASS with the new review surfaces and stricter export gate.

- [ ] **Step 6: Commit the frontend handoff review slice**

```bash
git add frontend/src/api/client.ts \
  frontend/src/pages/ComicStudio.tsx \
  frontend/src/components/comic/ComicPageAssemblyPanel.tsx \
  frontend/src/components/comic/ComicHandoffReviewPanel.tsx \
  frontend/src/pages/ComicStudio.test.tsx
git commit -m "feat(hollowforge): add layered handoff review UI"
```

## Task 5: Publish The Updated Operator Contract

**Files:**
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`
- Modify: `README.md`
- Modify: `STATE.md`

- [ ] **Step 1: Write the doc updates**

Required changes:

- add explicit `Handoff Review` stage between `Assemble Pages` and `Export Handoff ZIP`
- define layered artifact expectations in operator-facing language
- publish dry-run success criteria:
  - root layered manifest exists
  - handoff validation exists
  - hard block count is zero
- update repo snapshot/resume notes to mention `Pages` / `Handoff` surfaces

- [ ] **Step 2: Run the bounded verification commands**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_page_assembly_service.py tests/test_comic_routes.py tests/test_launch_comic_production_dry_run.py tests/test_launch_comic_remote_one_shot_dry_run.py -q

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ComicStudio.test.tsx
npm run build
```

Expected: PASS across the touched backend, frontend, and dry-run verification surfaces.

- [ ] **Step 3: Commit the published contract**

```bash
git add docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md README.md STATE.md
git commit -m "docs(hollowforge): publish layered handoff workflow"
```

## Final Verification

- [ ] Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
./.venv/bin/python -m pytest tests/test_comic_page_assembly_service.py tests/test_comic_routes.py tests/test_launch_comic_production_dry_run.py tests/test_launch_comic_remote_one_shot_dry_run.py -q

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/frontend
npm run test -- src/pages/ComicStudio.test.tsx
npm run build
```

- [ ] Confirm the final implementation preserves:
  - additive-only response compatibility
  - additive-only ZIP artifact compatibility
  - no manual anchor-edit UI
  - no native `.clip` generation

- [ ] Record final outcomes in `STATE.md` only after the verification output is real and passing.
