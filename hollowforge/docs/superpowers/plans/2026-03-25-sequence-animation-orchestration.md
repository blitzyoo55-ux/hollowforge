# HollowForge Sequence Animation Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Stage 1 sequence-orchestration layer that turns HollowForge still generation into 30-40 second multi-shot rough-cut candidates while keeping `all_ages` and `adult_nsfw` lanes isolated and keeping still generation local-first.

**Architecture:** Add a sequence domain above the existing `generations` and `animation_jobs` stack. Keep HollowForge as the single control plane, store sequence state in new SQLite tables, reuse the current generation queue and animation dispatch paths, and add a small Sequence Studio UI for blueprint creation, run monitoring, and rough-cut review.

**Tech Stack:** FastAPI, aiosqlite migrations, Pydantic v2, React 19, TanStack Query, Vite, existing remote animation worker, local ComfyUI, system `ffmpeg`

---

## Scope Notes

This plan is one vertical slice, not multiple independent projects:

- Backend schema and orchestration
- Backend API surface
- Frontend review UI
- Local preflight and smoke verification

This first implementation intentionally defers worker-schema expansion. Sequence metadata should stay inside HollowForge tables and `animation_jobs.request_json` for slice 1. The existing worker contract stays stable unless a later implementation task proves a worker-side field is required.

## File Structure Map

### Backend

- Create: `backend/requirements-dev.txt`
- Create: `backend/migrations/029_sequence_orchestration.sql`
- Create: `backend/app/routes/sequences.py`
- Create: `backend/app/services/sequence_repository.py`
- Create: `backend/app/services/sequence_registry.py`
- Create: `backend/app/services/sequence_blueprint_service.py`
- Create: `backend/app/services/sequence_run_service.py`
- Create: `backend/app/services/rough_cut_service.py`
- Create: `backend/scripts/check_sequence_pipeline_preflight.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_sequence_schema.py`
- Create: `backend/tests/test_sequence_registry.py`
- Create: `backend/tests/test_sequence_blueprint_service.py`
- Create: `backend/tests/test_sequence_run_service.py`
- Create: `backend/tests/test_sequence_routes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/prompt_factory_service.py`
- Modify: `backend/app/services/animation_dispatch_service.py`

### Frontend

- Create: `frontend/src/pages/SequenceStudio.tsx`
- Create: `frontend/src/components/SequenceBlueprintForm.tsx`
- Create: `frontend/src/components/SequenceRunReview.tsx`
- Create: `frontend/src/components/RoughCutCandidateCard.tsx`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/pages/SequenceStudio.test.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`

### Docs

- Create: `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md`

## Task 1: Bootstrap Backend Test Harness and Sequence Schema

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_sequence_schema.py`
- Create: `backend/migrations/029_sequence_orchestration.sql`

- [ ] **Step 1: Add backend test dependencies**

Create `backend/requirements-dev.txt`:

```txt
-r requirements.txt
pytest>=8.3
pytest-asyncio>=0.24
```

- [ ] **Step 2: Add a temporary-database pytest fixture**

Create `backend/tests/conftest.py`:

```python
import asyncio
from pathlib import Path

import pytest

from app import config as app_config


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "test-hollowforge.db"
    monkeypatch.setattr(app_config.settings, "DATA_DIR", tmp_path)
    monkeypatch.setattr(app_config.settings, "DB_PATH", db_path)
    monkeypatch.setattr(app_config.settings, "LEAN_MODE", True)
    return db_path
```

- [ ] **Step 3: Write the failing schema test**

Create `backend/tests/test_sequence_schema.py`:

```python
import aiosqlite
import pytest

from app.db import init_db


@pytest.mark.asyncio
async def test_sequence_tables_exist(temp_db):
    await init_db()
    async with aiosqlite.connect(temp_db) as db:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?, ?, ?, ?, ?)",
            (
                "sequence_blueprints",
                "sequence_runs",
                "sequence_shots",
                "shot_anchor_candidates",
                "shot_clips",
                "rough_cuts",
            ),
        )
        names = {row[0] for row in await cursor.fetchall()}
    assert names == {
        "sequence_blueprints",
        "sequence_runs",
        "sequence_shots",
        "shot_anchor_candidates",
        "shot_clips",
        "rough_cuts",
    }
```

- [ ] **Step 4: Run the test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pip install -r requirements-dev.txt
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_schema.py -q
```

Expected: FAIL because the sequence migration and tables do not exist yet.

- [ ] **Step 5: Add the schema migration**

Create `backend/migrations/029_sequence_orchestration.sql` with:

- `sequence_blueprints`
- `sequence_runs`
- `sequence_shots`
- `shot_anchor_candidates`
- `shot_clips`
- `rough_cuts`
- `content_mode`, `policy_profile_id`, `prompt_provider_profile_id`, `execution_mode`
- foreign-key link from `shot_clips.selected_animation_job_id` to `animation_jobs(id)`

Example:

```sql
CREATE TABLE IF NOT EXISTS sequence_blueprints (
    id TEXT PRIMARY KEY,
    content_mode TEXT NOT NULL,
    policy_profile_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    beat_grammar_id TEXT NOT NULL,
    target_duration_sec INTEGER NOT NULL,
    shot_count INTEGER NOT NULL,
    tone TEXT,
    executor_policy TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

- [ ] **Step 6: Run the schema test again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_schema.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/requirements-dev.txt backend/tests/conftest.py backend/tests/test_sequence_schema.py backend/migrations/029_sequence_orchestration.sql
git commit -m "feat(hollowforge): add sequence orchestration schema"
```

## Task 2: Add Sequence Models and Registries

**Files:**
- Create: `backend/app/services/sequence_registry.py`
- Create: `backend/tests/test_sequence_registry.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/prompt_factory_service.py`

- [ ] **Step 1: Write the failing registry test**

Create `backend/tests/test_sequence_registry.py`:

```python
from app.services.sequence_registry import get_beat_grammar, get_prompt_provider_profile


def test_stage1_beat_grammar_has_expected_order():
    grammar = get_beat_grammar("stage1_single_location_v1")
    assert grammar["beats"] == [
        "establish",
        "attention",
        "approach",
        "contact_action",
        "close_reaction",
        "settle",
    ]


def test_adult_prompt_profile_defaults_to_local():
    profile = get_prompt_provider_profile("adult_local_llm")
    assert profile["provider_kind"] == "local_llm"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q
```

Expected: FAIL with import errors because the registry file does not exist yet.

- [ ] **Step 3: Add the registry module**

Create `backend/app/services/sequence_registry.py` with:

- beat grammar profiles
- prompt provider profiles
- animation executor profiles
- lane-safe lookup helpers that reject cross-lane mismatches

Example:

```python
BEAT_GRAMMARS = {
    "stage1_single_location_v1": {
        "shot_count": 6,
        "beats": ["establish", "attention", "approach", "contact_action", "close_reaction", "settle"],
    }
}
```

- [ ] **Step 4: Extend API models and config**

Modify `backend/app/models.py` to add:

- `SequenceContentMode = Literal["all_ages", "adult_nsfw"]`
- request/response models for blueprints, runs, shots, rough cuts
- `prompt_provider_profile_id` and `policy_profile_id` fields

Modify `backend/app/config.py` to add:

- `HOLLOWFORGE_SEQUENCE_FFMPEG_BIN`
- `HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE`
- `HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE`

Modify `backend/app/services/prompt_factory_service.py` to add profile-aware provider selection instead of one global provider lookup.

- [ ] **Step 5: Run the registry test again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/sequence_registry.py backend/tests/test_sequence_registry.py backend/app/models.py backend/app/config.py backend/app/services/prompt_factory_service.py
git commit -m "feat(hollowforge): add sequence registries and models"
```

## Task 3: Build Repository and Shot-Planning Services

**Files:**
- Create: `backend/app/services/sequence_repository.py`
- Create: `backend/app/services/sequence_blueprint_service.py`
- Create: `backend/tests/test_sequence_blueprint_service.py`
- Modify: `backend/app/services/generation_service.py`

- [ ] **Step 1: Write the failing planner test**

Create `backend/tests/test_sequence_blueprint_service.py`:

```python
from app.services.sequence_blueprint_service import expand_blueprint_into_shots


def test_expand_blueprint_emits_stage1_shots_in_order():
    shots = expand_blueprint_into_shots(
        beat_grammar_id="stage1_single_location_v1",
        target_duration_sec=36,
    )
    assert len(shots) == 6
    assert shots[0]["beat_type"] == "establish"
    assert shots[-1]["beat_type"] == "settle"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_blueprint_service.py -q
```

Expected: FAIL because the service does not exist yet.

- [ ] **Step 3: Implement the repository and planner**

Create `backend/app/services/sequence_repository.py` to hold all SQL for:

- blueprint CRUD
- run creation and status transitions
- shot insertion and lookup
- anchor candidate persistence
- shot clip persistence
- rough cut persistence

Create `backend/app/services/sequence_blueprint_service.py` to:

- expand fixed beat grammar into ordered shots
- allocate target duration across shots
- attach fixed continuity rules for Stage 1

Example:

```python
def expand_blueprint_into_shots(*, beat_grammar_id: str, target_duration_sec: int) -> list[dict[str, object]]:
    beats = get_beat_grammar(beat_grammar_id)["beats"]
    duration = max(4, target_duration_sec // len(beats))
    return [{"shot_no": idx + 1, "beat_type": beat, "target_duration_sec": duration} for idx, beat in enumerate(beats)]
```

- [ ] **Step 4: Extract generation-batch submission into a reusable service entry point**

Modify `backend/app/services/generation_service.py` so sequence orchestration can call a clear method such as:

```python
async def queue_generation_batch(self, gen: GenerationCreate, count: int, seed_increment: int) -> tuple[int, list[GenerationResponse]]:
    ...
```

If that method already exists, add a thin helper wrapper or docstring and reuse it directly in the future sequence service rather than re-implementing batch queue logic in routes.

- [ ] **Step 5: Run the planner test again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_blueprint_service.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/sequence_repository.py backend/app/services/sequence_blueprint_service.py backend/tests/test_sequence_blueprint_service.py backend/app/services/generation_service.py
git commit -m "feat(hollowforge): add sequence repository and shot planner"
```

## Task 4: Implement Sequence Run Orchestration and Rough-Cut Assembly

**Files:**
- Create: `backend/app/services/sequence_run_service.py`
- Create: `backend/app/services/rough_cut_service.py`
- Create: `backend/tests/test_sequence_run_service.py`
- Modify: `backend/app/services/animation_dispatch_service.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Write failing orchestration tests**

Create `backend/tests/test_sequence_run_service.py`:

```python
import pytest

from app.services.sequence_run_service import select_anchor_candidates, build_rough_cut_timeline


def test_anchor_selection_keeps_primary_and_backups():
    candidates = [
        {"id": "a", "identity_score": 9, "location_lock_score": 9, "beat_fit_score": 9, "quality_score": 9},
        {"id": "b", "identity_score": 8, "location_lock_score": 8, "beat_fit_score": 8, "quality_score": 8},
        {"id": "c", "identity_score": 7, "location_lock_score": 7, "beat_fit_score": 7, "quality_score": 7},
    ]
    selected = select_anchor_candidates(candidates)
    assert selected["primary"]["id"] == "a"
    assert len(selected["backups"]) == 2


def test_rough_cut_timeline_preserves_shot_order():
    timeline = build_rough_cut_timeline(
        [{"shot_no": 2, "clip_path": "b.mp4"}, {"shot_no": 1, "clip_path": "a.mp4"}]
    )
    assert [item["clip_path"] for item in timeline] == ["a.mp4", "b.mp4"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_run_service.py -q
```

Expected: FAIL because the orchestration service does not exist yet.

- [ ] **Step 3: Implement the run service**

Create `backend/app/services/sequence_run_service.py` to:

- create a run from a blueprint
- expand shots from the planner
- build shot prompt packets
- request local still batches through `GenerationService`
- rank candidates into primary and backups
- create `animation_jobs` for chosen anchors
- track per-shot retry state

Do not call the worker directly from routes. The route should call this service.

- [ ] **Step 4: Implement rough-cut assembly**

Create `backend/app/services/rough_cut_service.py` to:

- sort clips by `shot_no`
- build `timeline_json`
- create a deterministic concat manifest
- invoke `ffmpeg` through a configured binary
- persist `rough_cuts.output_path`

Example:

```python
def build_rough_cut_timeline(clips: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(clips, key=lambda clip: int(clip["shot_no"]))
```

Modify `backend/app/config.py` to expose the ffmpeg binary path if not already present.

- [ ] **Step 5: Pass sequence metadata through animation dispatch**

Modify `backend/app/services/animation_dispatch_service.py` so `request_json` always preserves:

- `sequence_run_id`
- `sequence_shot_id`
- `content_mode`
- `executor_profile_id`

Keep the worker contract backward-compatible by nesting these values inside `request_json` rather than changing the worker schema in this slice.

- [ ] **Step 6: Run the orchestration tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_run_service.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/sequence_run_service.py backend/app/services/rough_cut_service.py backend/tests/test_sequence_run_service.py backend/app/services/animation_dispatch_service.py backend/app/config.py
git commit -m "feat(hollowforge): add sequence run orchestration"
```

## Task 5: Expose the Sequence API Surface

**Files:**
- Create: `backend/app/routes/sequences.py`
- Create: `backend/tests/test_sequence_routes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models.py`

- [ ] **Step 1: Write the failing route test**

Create `backend/tests/test_sequence_routes.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_sequence_blueprint_create_route_exists():
    client = TestClient(app)
    response = client.post(
        "/api/v1/sequences/blueprints",
        json={
            "content_mode": "all_ages",
            "policy_profile_id": "safe_stage1_v1",
            "character_id": "char_1",
            "location_id": "room_1",
            "beat_grammar_id": "stage1_single_location_v1",
            "target_duration_sec": 36,
            "shot_count": 6,
            "executor_policy": "safe_remote_prod",
        },
    )
    assert response.status_code != 404
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_routes.py -q
```

Expected: FAIL because the route is not registered.

- [ ] **Step 3: Implement the sequence router**

Create `backend/app/routes/sequences.py` with endpoints for:

- `POST /api/v1/sequences/blueprints`
- `GET /api/v1/sequences/blueprints`
- `POST /api/v1/sequences/runs`
- `GET /api/v1/sequences/runs`
- `GET /api/v1/sequences/runs/{run_id}`
- `POST /api/v1/sequences/runs/{run_id}/start`

Use the sequence services instead of embedding SQL in the route file.

- [ ] **Step 4: Wire the router into the app**

Modify `backend/app/main.py` to import and include `app.routes.sequences.router`.

If needed, extend `backend/app/models.py` with route-facing request and response payloads for blueprints, shots, run summaries, and rough-cut candidates.

If route tests become flaky because the app startup spins background services, extract a `create_app()` factory from `backend/app/main.py` and let tests build the app with lightweight startup configuration.

- [ ] **Step 5: Run the route test and a broader backend pass**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_routes.py tests/test_sequence_schema.py tests/test_sequence_registry.py tests/test_sequence_blueprint_service.py tests/test_sequence_run_service.py -q
cd backend && ./.venv/bin/python -m compileall app
```

Expected: PASS and no compile errors

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/sequences.py backend/tests/test_sequence_routes.py backend/app/main.py backend/app/models.py
git commit -m "feat(hollowforge): add sequence orchestration api"
```

## Task 6: Add the Sequence Studio Frontend

**Files:**
- Create: `frontend/src/pages/SequenceStudio.tsx`
- Create: `frontend/src/components/SequenceBlueprintForm.tsx`
- Create: `frontend/src/components/SequenceRunReview.tsx`
- Create: `frontend/src/components/RoughCutCandidateCard.tsx`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/pages/SequenceStudio.test.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Add frontend test tooling**

Modify `frontend/package.json`:

```json
{
  "scripts": {
    "test": "vitest --run"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "...",
    "@testing-library/react": "...",
    "jsdom": "...",
    "vitest": "..."
  }
}
```

Modify `frontend/vite.config.ts` to add a `test` block using `jsdom`, and create `frontend/src/test/setup.ts` to load `@testing-library/jest-dom`.

- [ ] **Step 2: Write the failing frontend test**

Create `frontend/src/pages/SequenceStudio.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import SequenceStudio from './SequenceStudio'

test('renders Stage 1 blueprint controls', () => {
  render(
    <MemoryRouter>
      <SequenceStudio />
    </MemoryRouter>,
  )
  expect(screen.getByText(/Stage 1 Sequence/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/Content Mode/i)).toBeInTheDocument()
})
```

- [ ] **Step 3: Run the frontend test to verify it fails**

Run:

```bash
cd frontend && npm install
cd frontend && npm run test -- SequenceStudio
```

Expected: FAIL because the page and components do not exist yet.

- [ ] **Step 4: Implement the UI**

Modify `frontend/src/api/client.ts` to add sequence types and client methods:

- `createSequenceBlueprint`
- `listSequenceBlueprints`
- `createSequenceRun`
- `getSequenceRun`
- `startSequenceRun`

Create:

- `frontend/src/pages/SequenceStudio.tsx`
- `frontend/src/components/SequenceBlueprintForm.tsx`
- `frontend/src/components/SequenceRunReview.tsx`
- `frontend/src/components/RoughCutCandidateCard.tsx`

Modify `frontend/src/App.tsx` to:

- lazy-load `SequenceStudio`
- add a nav item such as `/sequences`
- add a route for the new page

The first UI slice should cover:

- blueprint creation
- content-mode selection
- executor-profile selection
- run list
- per-run shot status
- rough-cut candidate cards

- [ ] **Step 5: Run frontend verification**

Run:

```bash
cd frontend && npm run test -- SequenceStudio
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SequenceStudio.tsx frontend/src/components/SequenceBlueprintForm.tsx frontend/src/components/SequenceRunReview.tsx frontend/src/components/RoughCutCandidateCard.tsx frontend/src/test/setup.ts frontend/src/pages/SequenceStudio.test.tsx frontend/src/api/client.ts frontend/src/App.tsx frontend/package.json frontend/vite.config.ts
git commit -m "feat(hollowforge): add sequence studio ui"
```

## Task 7: Add Preflight Checks and Operator Runbook

**Files:**
- Create: `backend/scripts/check_sequence_pipeline_preflight.py`
- Create: `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md`

- [ ] **Step 1: Write a failing preflight test**

Extend `backend/tests/test_sequence_run_service.py` or add a small smoke test that expects the ffmpeg binary resolver to reject an empty configuration:

```python
import pytest

from app.services.rough_cut_service import resolve_ffmpeg_bin


def test_resolve_ffmpeg_bin_requires_existing_binary(monkeypatch):
    monkeypatch.setenv("HOLLOWFORGE_SEQUENCE_FFMPEG_BIN", "/tmp/does-not-exist")
    with pytest.raises(RuntimeError):
        resolve_ffmpeg_bin()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_run_service.py -q
```

Expected: FAIL until the resolver and smoke script exist.

- [ ] **Step 3: Add the preflight script**

Create `backend/scripts/check_sequence_pipeline_preflight.py` to validate:

- backend DB migration availability
- sequence tables present
- prompt provider profiles resolvable
- executor profiles resolvable
- ffmpeg binary available
- animation worker reachable when remote execution is selected

Create `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md` covering:

- required env vars
- local-first workflow
- safe vs adult lane separation
- smoke-test commands
- rough-cut operator checklist

- [ ] **Step 4: Run the full verification pass**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests -q
cd backend && ./.venv/bin/python scripts/check_sequence_pipeline_preflight.py
cd backend && ./.venv/bin/python -m compileall app
cd frontend && npm run test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/check_sequence_pipeline_preflight.py docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md backend/tests
git commit -m "docs(hollowforge): add sequence stage1 runbook"
```

## Final Verification Checklist

Before handing the feature off for broader use, run:

```bash
cd backend && ./.venv/bin/python -m pytest tests -q
cd backend && ./.venv/bin/python scripts/check_sequence_pipeline_preflight.py
cd backend && ./.venv/bin/python -m compileall app
cd frontend && npm run test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected outcome:

- backend tests pass
- preflight passes for the chosen lane
- backend compiles cleanly
- frontend tests pass
- frontend lint passes
- frontend build passes

## Notes for the Implementer

- Keep `adult_nsfw` and `all_ages` separated at the sequence-domain layer, not just in prompt text.
- Do not create a separate Phase 2 product. All UI and orchestration stay inside HollowForge.
- Do not bypass `GenerationService` or route helpers with copy-pasted queue logic.
- Do not expand the worker payload unless HollowForge-side storage proves insufficient.
- Keep the first slice narrow: one blueprint grammar, one review page, one rough-cut assembler.
