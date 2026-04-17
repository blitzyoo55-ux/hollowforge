# HollowForge Production Comic Verification History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable comic verification run history to the backend and surface the latest preflight/suite status plus recent runs inside `/production`.

**Architecture:** Store each completed verification execution as a dedicated `comic_verification_runs` row behind the production API. Keep write logic centralized in a focused repository and backend route, then have the CLI scripts post final run payloads to that API instead of touching SQLite directly. On the frontend, keep `Verification Ops` as the command surface and render a separate read-only `VerificationHistoryPanel` that consumes one summary endpoint.

**Tech Stack:** FastAPI, Pydantic, SQLite via `aiosqlite`, Python CLI scripts, React 19, TanStack Query 5, Vitest, Testing Library

---

## File Map

- Create: `backend/migrations/037_comic_verification_runs.sql`
  - Add the durable run-history table.
- Create: `backend/app/services/production_comic_verification_repository.py`
  - Own DB insert/list/latest-summary logic for `comic_verification_runs`.
- Create: `backend/tests/test_production_comic_verification_repository.py`
  - Verify summary selection, recent-run ordering, and stage JSON decoding in isolation.
- Modify: `backend/app/models.py`
  - Add request/response models for production comic verification runs and the `/production` summary response.
- Modify: `backend/app/routes/production.py`
  - Add the write and read endpoints under `/api/v1/production/comic-verification/...`.
- Modify: `backend/tests/test_production_routes.py`
  - Cover the new POST and GET summary contracts.
- Modify: `backend/tests/test_comic_schema.py`
  - Assert the new table exists after migrations.
- Modify: `backend/scripts/check_comic_remote_render_preflight.py`
  - Add payload-building + POST submission for completed preflight checks.
- Modify: `backend/scripts/run_comic_verification_suite.py`
  - Add payload-building + POST submission for completed suite runs.
- Modify: `backend/tests/test_comic_remote_render_scripts.py`
  - Extend preflight tests to verify payload creation and persistence-failure behavior.
- Modify: `backend/tests/test_run_comic_verification_suite.py`
  - Extend suite tests to verify payload creation and persistence-failure behavior.
- Modify: `frontend/src/api/client.ts`
  - Add TypeScript response types and fetcher for production verification history.
- Create: `frontend/src/components/production/VerificationHistoryPanel.tsx`
  - Render latest preflight, latest suite, recent runs, and empty-state behavior.
- Create: `frontend/src/components/production/VerificationHistoryPanel.test.tsx`
  - Verify summary cards, failure-stage display, truncated error display, and empty state.
- Modify: `frontend/src/pages/ProductionHub.tsx`
  - Query the new summary endpoint and mount `VerificationHistoryPanel` below `VerificationOpsCard`.
- Modify: `frontend/src/pages/ProductionHub.test.tsx`
  - Assert that the new history block renders and tolerates empty history.

## Implementation Notes

- Keep the stored unit global, not per-episode. Do not add `production_episode_id` to the run-history table.
- Store only completed final state. Do not add `in_progress` polling in this phase.
- Use `run_mode` values exactly as approved:
  - `preflight`
  - `suite`
  - `full_only`
  - `remote_only`
- Keep stage detail in `stage_status_json`; do not explode stage columns into the table schema.
- Treat persistence failure as operator failure:
  - if verification succeeded but POSTing the history record fails, the CLI must exit non-zero.
- On the frontend, do not merge history into `VerificationOpsCard`; keep the history display in a separate component so the static command contract and read-only status surface stay independently testable.

### Task 1: Add the Run-History Schema and Repository

**Files:**
- Create: `backend/migrations/037_comic_verification_runs.sql`
- Create: `backend/app/services/production_comic_verification_repository.py`
- Create: `backend/tests/test_production_comic_verification_repository.py`
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_comic_schema.py`

- [ ] **Step 1: Write the failing schema and repository tests**

```python
@pytest.mark.asyncio
async def test_comic_verification_run_table_exists(temp_db) -> None:
    await init_db()
    with sqlite3.connect(temp_db) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "comic_verification_runs" in table_names


@pytest.mark.asyncio
async def test_list_summary_returns_latest_preflight_latest_suite_and_recent_runs(temp_db) -> None:
    await init_db()
    await create_comic_verification_run(
        ComicVerificationRunCreate(
            run_mode="preflight",
            status="completed",
            overall_success=True,
            base_url="http://127.0.0.1:8000",
            total_duration_sec=1.2,
            started_at="2026-04-17T00:00:00+00:00",
            finished_at="2026-04-17T00:00:01+00:00",
            stage_status={
                "preflight": {"status": "passed", "duration_sec": 1.2, "error_summary": None}
            },
        )
    )
    summary = await get_comic_verification_summary(limit=5)
    assert summary.latest_preflight is not None
    assert summary.latest_suite is None
    assert len(summary.recent_runs) == 1
```

- [ ] **Step 2: Run the backend tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_comic_schema.py tests/test_production_comic_verification_repository.py -q`

Expected: FAIL because the table, repository, and models do not exist yet.

- [ ] **Step 3: Add the migration, models, and focused repository**

```sql
CREATE TABLE IF NOT EXISTS comic_verification_runs (
    id TEXT PRIMARY KEY,
    run_mode TEXT NOT NULL CHECK (
        run_mode IN ('preflight', 'suite', 'full_only', 'remote_only')
    ),
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
    overall_success INTEGER NOT NULL CHECK (overall_success IN (0, 1)),
    failure_stage TEXT,
    error_summary TEXT,
    base_url TEXT NOT NULL,
    total_duration_sec REAL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    stage_status_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

```python
class ComicVerificationStageStatusResponse(BaseModel):
    status: str
    duration_sec: float | None = None
    error_summary: str | None = None


class ComicVerificationRunCreate(BaseModel):
    run_mode: Literal["preflight", "suite", "full_only", "remote_only"]
    status: Literal["completed", "failed"]
    overall_success: bool
    failure_stage: str | None = None
    error_summary: str | None = None
    base_url: str
    total_duration_sec: float | None = None
    started_at: str
    finished_at: str
    stage_status: dict[str, ComicVerificationStageStatusResponse] = Field(default_factory=dict)
```

```python
async def create_comic_verification_run(
    payload: ComicVerificationRunCreate,
) -> ComicVerificationRunResponse:
    run_id = str(uuid.uuid4())
    now = _now_iso()
    async with get_db() as db:
        await db.execute(
            """
            INSERT INTO comic_verification_runs (
                id, run_mode, status, overall_success, failure_stage,
                error_summary, base_url, total_duration_sec,
                started_at, finished_at, stage_status_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                payload.run_mode,
                payload.status,
                int(payload.overall_success),
                payload.failure_stage,
                payload.error_summary,
                payload.base_url,
                payload.total_duration_sec,
                payload.started_at,
                payload.finished_at,
                json.dumps(payload.stage_status, ensure_ascii=False),
                now,
                now,
            ),
        )
```

- [ ] **Step 4: Re-run the backend schema and repository tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_comic_schema.py tests/test_production_comic_verification_repository.py -q`

Expected: PASS

- [ ] **Step 5: Commit the schema and repository slice**

```bash
git add backend/migrations/037_comic_verification_runs.sql backend/app/models.py backend/app/services/production_comic_verification_repository.py backend/tests/test_comic_schema.py backend/tests/test_production_comic_verification_repository.py
git commit -m "feat: add comic verification run history schema"
```

### Task 2: Add Production API Write and Summary Endpoints

**Files:**
- Modify: `backend/app/routes/production.py`
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_production_routes.py`
- Verify: `backend/app/services/production_comic_verification_repository.py`

- [ ] **Step 1: Add the failing route tests**

```python
def test_create_comic_verification_run_and_read_summary(temp_db) -> None:
    client = _build_client()

    create_response = client.post(
        "/api/v1/production/comic-verification/runs",
        json={
            "run_mode": "suite",
            "status": "failed",
            "overall_success": False,
            "failure_stage": "full",
            "error_summary": "remote poll timeout",
            "base_url": "http://127.0.0.1:8000",
            "total_duration_sec": 540.25,
            "started_at": "2026-04-17T01:00:00+00:00",
            "finished_at": "2026-04-17T01:09:00+00:00",
            "stage_status": {
                "smoke": {"status": "passed", "duration_sec": 44.0, "error_summary": None},
                "full": {"status": "failed", "duration_sec": 496.25, "error_summary": "remote poll timeout"},
            },
        },
    )
    assert create_response.status_code == 201

    summary_response = client.get("/api/v1/production/comic-verification/summary")
    assert summary_response.status_code == 200
    payload = summary_response.json()
    assert payload["latest_suite"]["failure_stage"] == "full"
    assert len(payload["recent_runs"]) == 1
```

- [ ] **Step 2: Run the route test to verify it fails**

Run: `cd backend && python3 -m pytest tests/test_production_routes.py -q`

Expected: FAIL because the endpoints do not exist yet.

- [ ] **Step 3: Implement the route layer on top of the repository**

```python
@router.post(
    "/comic-verification/runs",
    response_model=ComicVerificationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comic_verification_run_endpoint(
    payload: ComicVerificationRunCreate,
) -> ComicVerificationRunResponse:
    return await create_comic_verification_run(payload)


@router.get(
    "/comic-verification/summary",
    response_model=ProductionComicVerificationSummaryResponse,
)
async def get_comic_verification_summary_endpoint() -> ProductionComicVerificationSummaryResponse:
    return await get_comic_verification_summary(limit=5)
```

- [ ] **Step 4: Re-run the route tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_production_routes.py -q`

Expected: PASS

- [ ] **Step 5: Commit the production API slice**

```bash
git add backend/app/routes/production.py backend/app/models.py backend/tests/test_production_routes.py
git commit -m "feat: add production comic verification summary api"
```

### Task 3: Record Completed Runs from the CLI Scripts

**Files:**
- Modify: `backend/scripts/check_comic_remote_render_preflight.py`
- Modify: `backend/scripts/run_comic_verification_suite.py`
- Modify: `backend/tests/test_comic_remote_render_scripts.py`
- Modify: `backend/tests/test_run_comic_verification_suite.py`

- [ ] **Step 1: Add the failing script tests for payload creation and POST failure**

```python
def test_preflight_builds_history_payload(monkeypatch) -> None:
    module = _load_script_module(
        "check_comic_remote_render_preflight.py",
        "check_comic_remote_render_preflight_history_payload",
    )
    checks = [
        module.CheckResult(name="local_backend_health", status="PASS", detail="healthy"),
        module.CheckResult(name="remote_worker_health", status="PASS", detail="ready"),
    ]
    payload = module._build_history_payload(
        checks=checks,
        backend_url="http://127.0.0.1:8000",
        started_at="2026-04-17T00:00:00+00:00",
        finished_at="2026-04-17T00:00:01+00:00",
    )
    assert payload["run_mode"] == "preflight"
    assert payload["overall_success"] is True
    assert payload["stage_status"]["preflight"]["status"] == "passed"


def test_suite_returns_nonzero_when_history_post_fails(monkeypatch, tmp_path, capsys) -> None:
    module = _load_module()
    _patch_stage_environment(module, monkeypatch, tmp_path)
    monkeypatch.setattr(module, "_post_history_payload", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("history post failed")))
    assert module.main(["--base-url", "http://127.0.0.1:8012"]) == 1
    assert "history post failed" in capsys.readouterr().err
```

- [ ] **Step 2: Run the script tests to verify they fail**

Run: `cd backend && python3 -m pytest tests/test_comic_remote_render_scripts.py tests/test_run_comic_verification_suite.py -q`

Expected: FAIL because the payload helpers and POST behavior do not exist yet.

- [ ] **Step 3: Add payload helpers and final-result POSTing to both scripts**

```python
def _build_history_payload(... ) -> dict[str, Any]:
    return {
        "run_mode": "preflight",
        "status": "completed" if all(check.status != "FAIL" for check in checks) else "failed",
        "overall_success": all(check.status != "FAIL" for check in checks),
        "failure_stage": "preflight" if any(check.status == "FAIL" for check in checks) else None,
        "error_summary": next((check.detail for check in checks if check.status == "FAIL"), None),
        "base_url": backend_url,
        "total_duration_sec": duration_sec,
        "started_at": started_at,
        "finished_at": finished_at,
        "stage_status": {
            "preflight": {
                "status": "passed" if all(check.status != "FAIL" for check in checks) else "failed",
                "duration_sec": duration_sec,
                "error_summary": next((check.detail for check in checks if check.status == "FAIL"), None),
            }
        },
    }
```

```python
try:
    _post_history_payload(base_url=base_url, payload=payload)
except RuntimeError as exc:
    print(str(exc), file=sys.stderr)
    return 1
```

- [ ] **Step 4: Re-run the script tests to verify they pass**

Run: `cd backend && python3 -m pytest tests/test_comic_remote_render_scripts.py tests/test_run_comic_verification_suite.py -q`

Expected: PASS

- [ ] **Step 5: Commit the CLI persistence slice**

```bash
git add backend/scripts/check_comic_remote_render_preflight.py backend/scripts/run_comic_verification_suite.py backend/tests/test_comic_remote_render_scripts.py backend/tests/test_run_comic_verification_suite.py
git commit -m "feat: persist comic verification history from cli"
```

### Task 4: Add the Production Verification History UI

**Files:**
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/components/production/VerificationHistoryPanel.tsx`
- Create: `frontend/src/components/production/VerificationHistoryPanel.test.tsx`
- Modify: `frontend/src/pages/ProductionHub.tsx`
- Modify: `frontend/src/pages/ProductionHub.test.tsx`

- [ ] **Step 1: Add the failing frontend tests**

```tsx
test('renders latest suite failure and recent verification runs', async () => {
  vi.mocked(listProductionComicVerificationSummary).mockResolvedValue({
    latest_preflight: null,
    latest_suite: {
      id: 'run_suite_1',
      run_mode: 'suite',
      status: 'failed',
      overall_success: false,
      failure_stage: 'full',
      error_summary: 'remote poll timeout after callback delay',
      base_url: 'http://127.0.0.1:8000',
      total_duration_sec: 540.25,
      started_at: '2026-04-17T01:00:00+00:00',
      finished_at: '2026-04-17T01:09:00+00:00',
      stage_status: {},
      created_at: '2026-04-17T01:09:00+00:00',
      updated_at: '2026-04-17T01:09:00+00:00',
    },
    recent_runs: [/* same row */],
  })

  renderPage()

  expect(await screen.findByRole('heading', { name: /Verification History/i })).toBeInTheDocument()
  expect(screen.getByText(/Latest Suite/i)).toBeInTheDocument()
  expect(screen.getByText(/full/i)).toBeInTheDocument()
  expect(screen.getByText(/remote poll timeout/i)).toBeInTheDocument()
})


test('renders verification history empty state', () => {
  render(<VerificationHistoryPanel summary={null} isLoading={false} isError={false} />)
  expect(screen.getByText(/No comic verification runs recorded yet/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the focused frontend tests to verify they fail**

Run: `cd frontend && npm run test -- src/components/production/VerificationHistoryPanel.test.tsx src/pages/ProductionHub.test.tsx`

Expected: FAIL because the client contract and history panel do not exist yet.

- [ ] **Step 3: Add the client contract, isolated panel, and page query**

```ts
export interface ComicVerificationRunResponse {
  id: string
  run_mode: 'preflight' | 'suite' | 'full_only' | 'remote_only'
  status: 'completed' | 'failed'
  overall_success: boolean
  failure_stage: string | null
  error_summary: string | null
  base_url: string
  total_duration_sec: number | null
  started_at: string
  finished_at: string
  stage_status: Record<string, { status: string; duration_sec: number | null; error_summary: string | null }>
  created_at: string
  updated_at: string
}

export interface ProductionComicVerificationSummaryResponse {
  latest_preflight: ComicVerificationRunResponse | null
  latest_suite: ComicVerificationRunResponse | null
  recent_runs: ComicVerificationRunResponse[]
}

export async function listProductionComicVerificationSummary(): Promise<ProductionComicVerificationSummaryResponse> {
  const res = await api.get<ProductionComicVerificationSummaryResponse>('/production/comic-verification/summary')
  return res.data
}
```

```tsx
const verificationHistoryQuery = useQuery({
  queryKey: ['production-comic-verification-summary'],
  queryFn: () => listProductionComicVerificationSummary(),
  refetchInterval: 30_000,
})

<VerificationOpsCard />
<VerificationHistoryPanel
  summary={verificationHistoryQuery.data ?? null}
  isLoading={verificationHistoryQuery.isLoading}
  isError={verificationHistoryQuery.isError}
/>
```

- [ ] **Step 4: Re-run the focused frontend tests to verify they pass**

Run: `cd frontend && npm run test -- src/components/production/VerificationHistoryPanel.test.tsx src/pages/ProductionHub.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit the frontend history slice**

```bash
git add frontend/src/api/client.ts frontend/src/components/production/VerificationHistoryPanel.tsx frontend/src/components/production/VerificationHistoryPanel.test.tsx frontend/src/pages/ProductionHub.tsx frontend/src/pages/ProductionHub.test.tsx
git commit -m "feat: show production verification history"
```

### Task 5: Run Cross-Stack Verification and Final Polish

**Files:**
- Modify: only if verification reveals needed fixes
- Verify: `backend/tests/test_comic_schema.py`
- Verify: `backend/tests/test_production_comic_verification_repository.py`
- Verify: `backend/tests/test_production_routes.py`
- Verify: `backend/tests/test_comic_remote_render_scripts.py`
- Verify: `backend/tests/test_run_comic_verification_suite.py`
- Verify: `frontend/src/components/production/VerificationHistoryPanel.test.tsx`
- Verify: `frontend/src/pages/ProductionHub.test.tsx`

- [ ] **Step 1: Run the full backend verification bundle**

Run: `cd backend && python3 -m pytest tests/test_comic_schema.py tests/test_production_comic_verification_repository.py tests/test_production_routes.py tests/test_comic_remote_render_scripts.py tests/test_run_comic_verification_suite.py -q`

Expected: PASS

- [ ] **Step 2: Run the focused frontend verification bundle**

Run: `cd frontend && npm run test -- src/components/production/VerificationHistoryPanel.test.tsx src/pages/ProductionHub.test.tsx`

Expected: PASS

- [ ] **Step 3: Run the frontend production build**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 4: Run a bounded local smoke of the new summary surface**

Run: `cd backend && python3 -m pytest tests/test_production_routes.py::test_create_comic_verification_run_and_read_summary -q`

Expected: PASS with the summary endpoint returning the newly created run in `recent_runs`.

- [ ] **Step 5: Commit only if verification required tracked follow-up edits**

```bash
git add backend/migrations/037_comic_verification_runs.sql backend/app/models.py backend/app/services/production_comic_verification_repository.py backend/app/routes/production.py backend/scripts/check_comic_remote_render_preflight.py backend/scripts/run_comic_verification_suite.py backend/tests/test_comic_schema.py backend/tests/test_production_comic_verification_repository.py backend/tests/test_production_routes.py backend/tests/test_comic_remote_render_scripts.py backend/tests/test_run_comic_verification_suite.py frontend/src/api/client.ts frontend/src/components/production/VerificationHistoryPanel.tsx frontend/src/components/production/VerificationHistoryPanel.test.tsx frontend/src/pages/ProductionHub.tsx frontend/src/pages/ProductionHub.test.tsx
git commit -m "test: verify comic verification history end to end"
```
