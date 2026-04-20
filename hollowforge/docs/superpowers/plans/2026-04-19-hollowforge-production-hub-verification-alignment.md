# HollowForge Production Hub Verification Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the `/production` route, persistence, and operator UI with the canonical production-hub verification flow instead of the older comic-only verification contract.

**Architecture:** Add a dedicated production verification persistence/API slice alongside the existing comic verification slice, then switch the `/production` frontend surface to production-hub commands and summary data. Keep the actual verification scripts unchanged and validate the refactor through repository tests, route tests, frontend page tests, and the live production-hub suite.

**Tech Stack:** FastAPI, Pydantic, SQLite, React 19, TanStack Query, Vitest, pytest

---

## File Map

- Create: `backend/app/services/production_verification_repository.py`
- Create: `backend/tests/test_production_verification_repository.py`
- Create: `docs/HOLLOWFORGE_PRODUCTION_HUB_VERIFICATION_SOP_20260419.md`
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/production.py`
- Modify: `backend/tests/test_production_routes.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/lib/productionVerificationOps.ts`
- Modify: `frontend/src/components/production/VerificationHistoryPanel.tsx`
- Modify: `frontend/src/components/production/VerificationOpsCard.tsx`
- Modify: `frontend/src/components/production/VerificationHistoryPanel.test.tsx`
- Modify: `frontend/src/pages/ProductionHub.test.tsx`
- Modify: `README.md`

### Task 1: Add Production Verification Backend Models

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_production_verification_repository.py`

- [ ] **Step 1: Write the failing repository test shape**

Add a new test module skeleton that expects production verification payloads and summary responses to validate cleanly.

```python
from app.models import ProductionVerificationRunCreate

def test_placeholder_model_contract() -> None:
    payload = ProductionVerificationRunCreate(
        run_mode="suite",
        status="completed",
        overall_success=True,
        base_url="http://127.0.0.1:8014",
        started_at="2026-04-19T00:00:00+00:00",
        finished_at="2026-04-19T00:00:01+00:00",
        stage_status={},
    )
    assert payload.run_mode == "suite"
```

- [ ] **Step 2: Run the placeholder test to verify missing models fail**

Run: `cd backend && ./.venv/bin/python -m pytest -q tests/test_production_verification_repository.py`

Expected: FAIL because `ProductionVerificationRunCreate` and related models do not exist yet.

- [ ] **Step 3: Add the production verification Pydantic models**

Add:

- `ProductionVerificationStageStatusResponse`
- `ProductionVerificationRunCreate`
- `ProductionVerificationRunResponse`
- `ProductionVerificationSummaryResponse`

Use allowed run modes:

```python
Literal["suite", "smoke_only", "ui_only"]
```

- [ ] **Step 4: Run the new repository test to verify the models import cleanly**

Run: `cd backend && ./.venv/bin/python -m pytest -q tests/test_production_verification_repository.py`

Expected: PASS or progress to the next missing repository implementation failure.

### Task 2: Add Production Verification Repository

**Files:**
- Create: `backend/app/services/production_verification_repository.py`
- Test: `backend/tests/test_production_verification_repository.py`

- [ ] **Step 1: Write failing repository tests**

Cover:

- latest `smoke_only`
- latest `suite`
- recent run ordering
- stage-status JSON round-trip

Use the existing comic verification repository tests as the reference shape, but target the new production models and storage.

- [ ] **Step 2: Run the repository tests to verify they fail for the right reason**

Run: `cd backend && ./.venv/bin/python -m pytest -q tests/test_production_verification_repository.py`

Expected: FAIL because the repository file and functions do not exist yet.

- [ ] **Step 3: Implement the repository with minimal dedicated storage logic**

Mirror the existing repository structure with new names:

- `create_production_verification_run()`
- `get_production_verification_summary()`

Use a dedicated table such as `production_verification_runs` and preserve:

- `finished_at DESC, created_at DESC, id DESC` ordering
- JSON stage-status encoding and decoding
- one transaction for summary fetches

- [ ] **Step 4: Run the repository tests again**

Run: `cd backend && ./.venv/bin/python -m pytest -q tests/test_production_verification_repository.py`

Expected: PASS

- [ ] **Step 5: Run a focused syntax check**

Run: `cd backend && ./.venv/bin/python -m py_compile app/models.py app/services/production_verification_repository.py`

Expected: PASS

### Task 3: Expose Production Verification Routes

**Files:**
- Modify: `backend/app/routes/production.py`
- Modify: `backend/tests/test_production_routes.py`
- Test: `backend/tests/test_production_routes.py`

- [ ] **Step 1: Write failing production route tests**

Add tests for:

- `POST /api/v1/production/verification/runs`
- `GET /api/v1/production/verification/summary`

Expected response shape:

```python
assert body["latest_suite"]["run_mode"] == "suite"
assert body["recent_runs"][0]["run_mode"] in {"suite", "smoke_only", "ui_only"}
```

- [ ] **Step 2: Run the focused route tests to verify failure**

Run: `cd backend && ./.venv/bin/python -m pytest -q tests/test_production_routes.py -k verification`

Expected: FAIL because the new route paths and repository wiring do not exist yet.

- [ ] **Step 3: Implement the route wiring**

Update `backend/app/routes/production.py` to import the new repository and models, then add:

- `create_production_verification_run_endpoint`
- `get_production_verification_summary_endpoint`

Keep existing comic verification endpoints intact unless they are already unused and can be left as-is.

- [ ] **Step 4: Run the focused route tests again**

Run: `cd backend && ./.venv/bin/python -m pytest -q tests/test_production_routes.py -k verification`

Expected: PASS

### Task 4: Switch Frontend API And Ops Surface

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/lib/productionVerificationOps.ts`
- Modify: `frontend/src/components/production/VerificationOpsCard.tsx`
- Modify: `frontend/src/components/production/VerificationHistoryPanel.tsx`
- Modify: `frontend/src/components/production/VerificationHistoryPanel.test.tsx`
- Modify: `frontend/src/pages/ProductionHub.test.tsx`

- [ ] **Step 1: Write failing frontend expectations**

Update tests so `/production` expects:

- `Run Production Hub Verification Suite`
- `Rerun Smoke Only`
- `Rerun UI Only`
- `Latest Smoke Only`
- production-hub summary data instead of comic verification summary

- [ ] **Step 2: Run the focused frontend tests to verify failure**

Run: `cd frontend && npm run test -- src/components/production/VerificationHistoryPanel.test.tsx src/pages/ProductionHub.test.tsx`

Expected: FAIL because the API client, ops constants, and summary labels still use comic verification names.

- [ ] **Step 3: Implement the frontend API and UI updates**

In `frontend/src/api/client.ts`:

- add production verification interfaces and fetcher

In `frontend/src/lib/productionVerificationOps.ts`:

- replace comic commands with production-hub commands:

```text
cd frontend
./scripts/run-worktree-handoff-stack.sh

cd backend
python3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014
python3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014 --smoke-only
python3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014 --ui-only
```

In `VerificationHistoryPanel.tsx`:

- fetch production verification summary
- map run modes `suite`, `smoke_only`, `ui_only`
- relabel summary cards

- [ ] **Step 4: Run the focused frontend tests again**

Run: `cd frontend && npm run test -- src/components/production/VerificationHistoryPanel.test.tsx src/pages/ProductionHub.test.tsx`

Expected: PASS

### Task 5: Publish The Production SOP And README References

**Files:**
- Create: `docs/HOLLOWFORGE_PRODUCTION_HUB_VERIFICATION_SOP_20260419.md`
- Modify: `README.md`

- [ ] **Step 1: Write the SOP content**

Document:

- when to use the worktree handoff stack
- the canonical suite command
- when to use `--smoke-only`
- when to use `--ui-only`
- what success markers to expect

- [ ] **Step 2: Update README command references**

Add or adjust:

- production-hub verification suite command
- worktree handoff stack usage
- the new SOP path

- [ ] **Step 3: Run a quick grep verification**

Run: `rg -n "production hub verification|run_production_hub_verification_suite|HOLLOWFORGE_PRODUCTION_HUB_VERIFICATION_SOP" README.md docs/HOLLOWFORGE_PRODUCTION_HUB_VERIFICATION_SOP_20260419.md frontend/src/lib/productionVerificationOps.ts`

Expected: PASS with all new references present.

### Task 6: Full Verification

**Files:**
- Modify: none unless failures require fixes

- [ ] **Step 1: Run backend repository and route tests**

Run:

```bash
cd backend
./.venv/bin/python -m pytest -q \
  tests/test_production_verification_repository.py \
  tests/test_production_routes.py
```

Expected: PASS

- [ ] **Step 2: Run focused frontend production tests**

Run:

```bash
cd frontend
npm run test -- \
  src/components/production/VerificationHistoryPanel.test.tsx \
  src/pages/ProductionHub.test.tsx
```

Expected: PASS

- [ ] **Step 3: Run the full production UI test slice**

Run:

```bash
cd frontend
npm run test -- \
  src/pages/ProductionHub.test.tsx \
  src/pages/ComicStudio.test.tsx \
  src/pages/SequenceStudio.test.tsx
```

Expected: PASS

- [ ] **Step 4: Run the canonical production-hub suite**

Run:

```bash
cd frontend
./scripts/run-worktree-handoff-stack.sh
```

In a second terminal:

```bash
cd backend
python3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014
```

Expected:

- `stage_smoke_exit_code: 0`
- `stage_ui_exit_code: 0`
- `overall_success: true`

- [ ] **Step 5: Stop the stack and confirm cleanup**

Run:

```bash
nc -zvw2 127.0.0.1 8014
nc -zvw2 127.0.0.1 4173
```

Expected: both ports refuse connections after shutdown.
