# HollowForge Production Verification Artifact Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mark production verification smoke artifacts explicitly and hide them from the default `/production` operator surface while preserving deliberate debug retrieval and lineage for later cleanup.

**Architecture:** Add `record_origin` and `verification_run_id` to top-level production records, teach repository and route listing paths to exclude verification artifacts by default, then propagate artifact lineage from the production verification suite into the smoke launcher. Keep the UI behavior simple by consuming the default filtered endpoints and avoiding any new debug toggle in the first slice.

**Tech Stack:** FastAPI, Pydantic, SQLite migrations, aiosqlite repository helpers, React, React Query, Vitest, pytest

---

### Task 1: Extend The Production Schema And Contracts

**Files:**
- Create: `backend/migrations/039_production_verification_artifact_origin.sql`
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_comic_schema.py`

- [ ] **Step 1: Write the failing schema assertions**

Add assertions in `backend/tests/test_comic_schema.py` for:

```python
r"ALTER TABLE works\s+ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator'"
r"ALTER TABLE works\s+ADD COLUMN verification_run_id TEXT"
r"ALTER TABLE series\s+ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator'"
r"ALTER TABLE series\s+ADD COLUMN verification_run_id TEXT"
r"ALTER TABLE production_episodes\s+ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator'"
r"ALTER TABLE production_episodes\s+ADD COLUMN verification_run_id TEXT"
```

- [ ] **Step 2: Run the focused schema test to verify it fails**

Run:

```bash
cd backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q tests/test_comic_schema.py -k production
```

Expected: FAIL because migration `039_*` does not exist yet and the new column patterns are absent.

- [ ] **Step 3: Add the migration**

Create `backend/migrations/039_production_verification_artifact_origin.sql` with:

```sql
ALTER TABLE works ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator';
ALTER TABLE works ADD COLUMN verification_run_id TEXT;

ALTER TABLE series ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator';
ALTER TABLE series ADD COLUMN verification_run_id TEXT;

ALTER TABLE production_episodes ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator';
ALTER TABLE production_episodes ADD COLUMN verification_run_id TEXT;
```

Do not add a foreign key on `verification_run_id` in this slice. Smoke records may be created before the verification run row is persisted.

- [ ] **Step 4: Extend the production Pydantic contracts**

Update `backend/app/models.py`:

- add a constrained literal-like type for `record_origin`:

```python
ProductionRecordOrigin = Literal["operator", "verification_smoke"]
```

- extend:
  - `ProductionWorkCreate`
  - `ProductionSeriesCreate`
  - `ProductionEpisodeCreate`
  - `ProductionWorkResponse`
  - `ProductionSeriesResponse`
  - `ProductionEpisodeDetailResponse`

with:

```python
record_origin: ProductionRecordOrigin = "operator"
verification_run_id: Optional[str] = Field(default=None, max_length=120)
```

- extend `ProductionVerificationRunCreate` and `ProductionVerificationRunResponse` with:

```python
id: Optional[str] = Field(default=None, min_length=1, max_length=120)
```

This allows the suite to pre-generate a lineage id and persist the verification run under the same id later.

- [ ] **Step 5: Re-run the focused schema/model test**

Run:

```bash
cd backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q tests/test_comic_schema.py -k production
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/039_production_verification_artifact_origin.sql backend/app/models.py backend/tests/test_comic_schema.py
git commit -m "feat: add production verification artifact origin fields"
```

### Task 2: Filter Production Listings By Default And Allow Explicit Inclusion

**Files:**
- Modify: `backend/app/services/production_hub_repository.py`
- Modify: `backend/app/routes/production.py`
- Test: `backend/tests/test_production_routes.py`

- [ ] **Step 1: Write the failing route tests for default hiding**

Add tests in `backend/tests/test_production_routes.py` that create:

- one `operator` work/series/episode
- one `verification_smoke` work/series/episode

and assert:

```python
client.get("/api/v1/production/works").json() == [operator_work]
client.get("/api/v1/production/series").json() == [operator_series]
client.get("/api/v1/production/episodes").json() == [operator_episode]
```

Add explicit inclusion tests:

```python
client.get("/api/v1/production/works", params={"include_verification_artifacts": True})
client.get("/api/v1/production/series", params={"include_verification_artifacts": True})
client.get("/api/v1/production/episodes", params={"include_verification_artifacts": True})
```

Expected payload contains both operator and verification smoke records.

- [ ] **Step 2: Run the focused route tests to verify they fail**

Run:

```bash
cd backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q tests/test_production_routes.py -k "production and (works or series or episodes)"
```

Expected: FAIL because the list endpoints currently return every record and do not accept `include_verification_artifacts`.

- [ ] **Step 3: Implement repository-level filtering**

Update `backend/app/services/production_hub_repository.py`:

- `create_work`, `create_series`, `create_production_episode` must persist:

```python
payload.record_origin
payload.verification_run_id
```

- `list_works`, `list_series`, `list_production_episodes` must accept:

```python
include_verification_artifacts: bool = False
```

- when `include_verification_artifacts` is false, add:

```sql
WHERE record_origin = 'operator'
```

- when true, do not filter on `record_origin`

Keep the existing `work_id` filter working together with the origin filter.

- [ ] **Step 4: Implement route query parameters**

Update `backend/app/routes/production.py` so:

- `GET /works`
- `GET /series`
- `GET /episodes`

all accept:

```python
include_verification_artifacts: bool = Query(default=False)
```

and pass the value into the repository helpers.

- [ ] **Step 5: Re-run the focused route tests**

Run:

```bash
cd backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q tests/test_production_routes.py -k "production and (works or series or episodes)"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/production_hub_repository.py backend/app/routes/production.py backend/tests/test_production_routes.py
git commit -m "feat: hide production verification artifacts by default"
```

### Task 3: Propagate Verification Artifact Lineage Through Smoke And Suite

**Files:**
- Modify: `backend/scripts/launch_production_hub_smoke.py`
- Modify: `backend/scripts/run_production_hub_verification_suite.py`
- Modify: `backend/app/services/production_verification_repository.py`
- Test: `backend/tests/test_launch_production_hub_smoke.py`
- Test: `backend/tests/test_run_production_hub_verification_suite.py`
- Test: `backend/tests/test_production_verification_repository.py`

- [ ] **Step 1: Write the failing smoke-script test**

Extend `backend/tests/test_launch_production_hub_smoke.py` so the mocked POST payloads for:

- `/api/v1/production/works`
- `/api/v1/production/series`
- `/api/v1/production/episodes`

must include:

```python
"record_origin": "verification_smoke"
"verification_run_id": "run-smoke-1"
```

Drive the script with:

```python
module.main(["--base-url", base_url, "--verification-run-id", "run-smoke-1"])
```

- [ ] **Step 2: Write the failing suite-script tests**

Extend `backend/tests/test_run_production_hub_verification_suite.py` to prove:

- the suite pre-generates a run id
- smoke stage command receives `--verification-run-id <same-id>`
- persisted production verification run payload uses the same `id`
- `--smoke-only` also persists a run under that same pre-generated id

The stage command assertion should look for:

```python
[
  sys.executable,
  ".../launch_production_hub_smoke.py",
  "--base-url",
  "http://127.0.0.1:8014",
  "--verification-run-id",
  "<generated-id>",
]
```

- [ ] **Step 3: Run the focused script tests to verify they fail**

Run:

```bash
cd backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q tests/test_launch_production_hub_smoke.py tests/test_run_production_hub_verification_suite.py
```

Expected: FAIL because the smoke launcher has no `--verification-run-id` and the suite does not propagate a shared id.

- [ ] **Step 4: Implement smoke lineage support**

Update `backend/scripts/launch_production_hub_smoke.py`:

- add parser arg:

```python
parser.add_argument("--verification-run-id")
```

- resolve a lineage id:

```python
verification_run_id = str(args.verification_run_id or uuid.uuid4())
```

- include on production creation payloads:

```python
"record_origin": "verification_smoke",
"verification_run_id": verification_run_id,
```

- print the lineage marker:

```python
"verification_run_id": verification_run_id
```

- [ ] **Step 5: Implement suite lineage propagation**

Update `backend/scripts/run_production_hub_verification_suite.py`:

- create one run id before stages start:

```python
verification_run_id = str(uuid.uuid4())
```

- pass it to the smoke stage command
- include it in the persistence payload:

```python
"id": verification_run_id
```

Do not pass it to the UI stage.

- [ ] **Step 6: Teach repository persistence to accept explicit ids**

Update `backend/app/services/production_verification_repository.py` so `create_production_verification_run()` uses:

```python
run_id = payload.id or str(uuid.uuid4())
```

and persists the explicit id when provided.

- [ ] **Step 7: Re-run the focused script and repository tests**

Run:

```bash
cd backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q tests/test_launch_production_hub_smoke.py tests/test_run_production_hub_verification_suite.py tests/test_production_verification_repository.py
```

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/scripts/launch_production_hub_smoke.py backend/scripts/run_production_hub_verification_suite.py backend/app/services/production_verification_repository.py backend/tests/test_launch_production_hub_smoke.py backend/tests/test_run_production_hub_verification_suite.py backend/tests/test_production_verification_repository.py
git commit -m "feat: track production verification smoke artifact lineage"
```

### Task 4: Keep The Production UI Clean While Preserving Explicit Retrieval

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/ProductionHub.tsx`
- Test: `frontend/src/pages/ProductionHub.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

Extend `frontend/src/pages/ProductionHub.test.tsx` with cases that prove default operator rendering ignores smoke artifacts.

Mock the API results so:

- `listProductionWorks()` returns only operator records by default
- `listProductionSeries()` returns only operator records by default
- `listProductionEpisodes()` returns only operator records by default

Add type fixtures with:

```ts
record_origin: 'operator' | 'verification_smoke'
verification_run_id: string | null
```

Then assert:

- the summary episode count reflects only operator records
- work/series dropdowns do not show smoke work titles
- the episode registry does not show smoke episode cards

- [ ] **Step 2: Run the focused frontend test to verify it fails**

Run:

```bash
cd frontend
npm run test -- src/pages/ProductionHub.test.tsx
```

Expected: FAIL because the current types do not include `record_origin` / `verification_run_id`.

- [ ] **Step 3: Extend frontend production types and query helpers**

Update `frontend/src/api/client.ts`:

- add `record_origin` and `verification_run_id` to:
  - `ProductionWorkResponse`
  - `ProductionSeriesResponse`
  - `ProductionEpisodeDetailResponse`

- extend query helper signatures:

```ts
listProductionWorks(query?: { include_verification_artifacts?: boolean })
listProductionSeries(query?: { work_id?: string; include_verification_artifacts?: boolean })
listProductionEpisodes(query?: { work_id?: string; include_verification_artifacts?: boolean })
```

The default call sites in `ProductionHub.tsx` should continue to pass no flag so the backend default filter remains active.

- [ ] **Step 4: Keep ProductionHub on the default filtered endpoints**

Update `frontend/src/pages/ProductionHub.tsx` only as needed to align with the expanded client signatures and response types. Do not add a debug toggle in this slice.

- [ ] **Step 5: Re-run the focused frontend test**

Run:

```bash
cd frontend
npm run test -- src/pages/ProductionHub.test.tsx
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/ProductionHub.tsx frontend/src/pages/ProductionHub.test.tsx
git commit -m "feat: keep production hub UI clean of smoke artifacts"
```

### Task 5: Full Verification

**Files:**
- Modify: none unless failures require fixes

- [ ] **Step 1: Run the backend verification set**

Run:

```bash
cd backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_comic_schema.py \
  tests/test_production_routes.py \
  tests/test_production_verification_repository.py \
  tests/test_launch_production_hub_smoke.py \
  tests/test_run_production_hub_verification_suite.py
```

Expected: PASS

- [ ] **Step 2: Run the focused frontend production set**

Run:

```bash
cd frontend
npm run test -- \
  src/pages/ProductionHub.test.tsx \
  src/pages/ComicStudio.test.tsx \
  src/pages/SequenceStudio.test.tsx \
  src/components/production/VerificationHistoryPanel.test.tsx
```

Expected: PASS

- [ ] **Step 3: Run one live smoke-only verification against the worktree stack**

Run:

```bash
cd frontend
./scripts/run-worktree-handoff-stack.sh
```

In a second terminal:

```bash
cd backend
python3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014 --smoke-only
curl -s http://127.0.0.1:8014/api/v1/production/episodes
curl -s "http://127.0.0.1:8014/api/v1/production/episodes?include_verification_artifacts=true"
```

Expected:

- smoke-only run persists successfully
- default `/production/episodes` list excludes the just-created smoke artifact
- explicit `include_verification_artifacts=true` reveals it

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "feat: isolate production verification smoke artifacts"
```
