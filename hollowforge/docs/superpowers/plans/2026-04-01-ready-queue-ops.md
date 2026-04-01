# HollowForge Ready Queue Ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a publishing-readiness contract and `draft_only` degradation so the Ready Queue and Publishing Pilot surfaces expose caption-provider readiness before the operator hits a runtime error.

**Architecture:** Add one backend readiness endpoint in the publishing domain, use it to guard the caption action path with a stable `503` operator error, and thread the same readiness state through the React publishing surfaces. The frontend should disable caption generation when caption readiness is false, keep draft creation available, and explain the degraded mode in the batch UI.

**Tech Stack:** FastAPI, Pydantic, SQLite-backed route tests with `pytest`, React 19, TanStack Query, Vitest, Testing Library

---

## Implementation Notes

- Primary target subtree: `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge`
- Existing unrelated dirtiness is expected in:
  - `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-brief.md`
  - `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`
  - `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-retro.md`
  - `data/`
- Do not revert or include those pilot artifacts in feature commits.
- Backend test runner should use the shared backend venv:
  - `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python`
- Frontend tests should run from `frontend/` with:
  - `npm test -- <paths>`

## File Map

- Modify: `backend/app/models.py`
  - Add publishing readiness response model and any small supporting literals/types.
- Modify: `backend/app/routes/publishing.py`
  - Add `GET /api/v1/publishing/readiness`.
  - Add caption-generation preflight that returns a stable `503` detail when readiness is false.
- Create: `backend/tests/test_publishing_routes.py`
  - Cover readiness endpoint and caption-route degradation behavior.
- Modify: `backend/tests/test_publishing_service.py`
  - Keep draft-job and ready-items behavior covered while extending the readiness-era contract where useful.
- Modify: `frontend/src/api/client.ts`
  - Add readiness types and `getPublishingReadiness()`.
- Modify: `frontend/src/pages/Marketing.tsx`
  - Show the top-level publishing mode summary when a batch is selected.
- Modify: `frontend/src/pages/Marketing.test.tsx`
  - Verify the publishing mode summary state.
- Modify: `frontend/src/components/publishing/PublishingPilotWorkbench.tsx`
  - Query readiness, render warning state, and pass readiness to cards.
- Modify: `frontend/src/components/publishing/PublishingPilotWorkbench.test.tsx`
  - Verify degraded-mode warning behavior and card prop wiring.
- Modify: `frontend/src/components/publishing/PublishingPilotCard.tsx`
  - Disable caption generation when unavailable, show reason text, keep draft creation enabled.
- Create: `frontend/src/components/publishing/PublishingPilotCard.test.tsx`
  - Verify disabled caption button and still-available draft path.

## Task 1: Add Backend Publishing Readiness Contract

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/publishing.py`
- Create: `backend/tests/test_publishing_routes.py`

- [ ] **Step 1: Write the failing readiness-route tests**

Create `backend/tests/test_publishing_routes.py` with route-level tests for:

```python
async def test_publishing_readiness_returns_draft_only_without_openrouter_key(...):
    ...
    assert response.status_code == 200
    assert response.json()["caption_generation_ready"] is False
    assert response.json()["draft_publish_ready"] is True
    assert response.json()["degraded_mode"] == "draft_only"
    assert response.json()["missing_requirements"] == ["OPENROUTER_API_KEY"]

async def test_publishing_readiness_returns_full_when_openrouter_key_exists(...):
    ...
    assert response.json()["caption_generation_ready"] is True
    assert response.json()["degraded_mode"] == "full"
```

- [ ] **Step 2: Run the new backend tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_publishing_routes.py -q
```

Expected: FAIL because the readiness model/route does not exist yet.

- [ ] **Step 3: Add the readiness response model**

In `backend/app/models.py`, add the smallest explicit response model needed, for example:

```python
class PublishingReadinessResponse(BaseModel):
    caption_generation_ready: bool
    draft_publish_ready: bool
    degraded_mode: Literal["full", "draft_only"]
    provider: str
    model: str
    missing_requirements: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement `GET /api/v1/publishing/readiness`**

In `backend/app/routes/publishing.py`, add a small helper that reads `settings.OPENROUTER_API_KEY`, `settings.MARKETING_PROVIDER_NAME`, and `settings.MARKETING_MODEL`, then returns `PublishingReadinessResponse`.

Implementation constraints:
- No DB access required.
- Return `200 OK` even when secrets are missing.
- Missing key should map to `draft_only`.
- Do not add provider-switching logic in this branch.

- [ ] **Step 5: Run the readiness-route tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_publishing_routes.py -q
```

Expected: PASS for the readiness-route cases.

- [ ] **Step 6: Commit Task 1**

```bash
git add backend/app/models.py backend/app/routes/publishing.py backend/tests/test_publishing_routes.py
git commit -m "feat(hollowforge): add publishing readiness route"
```

## Task 2: Guard Caption Generation With Stable `503` Degradation

**Files:**
- Modify: `backend/app/routes/publishing.py`
- Modify: `backend/tests/test_publishing_routes.py`
- Modify: `backend/tests/test_publishing_service.py`

- [ ] **Step 1: Add failing tests for degraded caption behavior**

Extend `backend/tests/test_publishing_routes.py` with:

```python
async def test_caption_generation_returns_503_without_openrouter_key(...):
    ...
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Caption generation unavailable: OPENROUTER_API_KEY is not configured"
    )
```

Keep or add one draft-path assertion, either in `test_publishing_routes.py` or `test_publishing_service.py`:

```python
async def test_draft_publish_job_still_succeeds_without_openrouter_key(...):
    ...
    assert response.status_code == 201
    assert response.json()["status"] == "draft"
```

- [ ] **Step 2: Run the targeted backend tests to verify failure**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_publishing_routes.py tests/test_publishing_service.py -q
```

Expected: FAIL because the caption route still falls through to the current runtime error path.

- [ ] **Step 3: Implement caption preflight in the route**

In `backend/app/routes/publishing.py`:
- Reuse the same readiness helper introduced in Task 1.
- Before reading image bytes or calling `generate_caption_from_image_bytes`, short-circuit when `caption_generation_ready` is false.
- Raise:

```python
HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    detail="Caption generation unavailable: OPENROUTER_API_KEY is not configured",
)
```

Important:
- Do not change draft-job behavior.
- Do not alter caption persistence logic when readiness is true.

- [ ] **Step 4: Run the targeted backend tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_publishing_routes.py tests/test_publishing_service.py -q
```

Expected: PASS for readiness, `503` degradation, and draft-path tests.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/app/routes/publishing.py backend/tests/test_publishing_routes.py backend/tests/test_publishing_service.py
git commit -m "fix(hollowforge): gate caption generation by readiness"
```

## Task 3: Expose Publishing Readiness in the Frontend API and Marketing Page

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/Marketing.tsx`
- Modify: `frontend/src/pages/Marketing.test.tsx`

- [ ] **Step 1: Add failing Marketing-page tests**

Extend `frontend/src/pages/Marketing.test.tsx` to cover the publishing-ready batch state with a mocked readiness response:

```tsx
test('renders the publishing readiness summary when the batch is draft-only', async () => {
  ...
  expect(await screen.findByText(/draft-only mode/i)).toBeInTheDocument()
  expect(screen.getByText(/OPENROUTER_API_KEY/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the Marketing-page test to verify it fails**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/frontend
npm test -- src/pages/Marketing.test.tsx
```

Expected: FAIL because no readiness client/type/UI exists yet.

- [ ] **Step 3: Add frontend readiness types and client call**

In `frontend/src/api/client.ts`, add:

```ts
export type PublishingDegradedMode = 'full' | 'draft_only'

export interface PublishingReadinessResponse {
  caption_generation_ready: boolean
  draft_publish_ready: boolean
  degraded_mode: PublishingDegradedMode
  provider: string
  model: string
  missing_requirements: string[]
  notes: string[]
}

export async function getPublishingReadiness(): Promise<PublishingReadinessResponse> {
  ...
}
```

- [ ] **Step 4: Add the Marketing-page readiness summary**

In `frontend/src/pages/Marketing.tsx`:
- Query `getPublishingReadiness()` only when `hasPublishingSelection` is true.
- Render a compact summary banner above `PublishingPilotWorkbench`.
- Keep the no-selection empty state unchanged.

Recommended copy shape:
- `full`: "Caption generation and draft publishing are available."
- `draft_only`: "Draft-only mode. Caption generation is unavailable until OPENROUTER_API_KEY is configured."

- [ ] **Step 5: Run the Marketing-page test again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/frontend
npm test -- src/pages/Marketing.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add frontend/src/api/client.ts frontend/src/pages/Marketing.tsx frontend/src/pages/Marketing.test.tsx
git commit -m "feat(hollowforge): surface publishing readiness in marketing"
```

## Task 4: Degrade the Publishing Workbench and Cards Cleanly

**Files:**
- Modify: `frontend/src/components/publishing/PublishingPilotWorkbench.tsx`
- Modify: `frontend/src/components/publishing/PublishingPilotWorkbench.test.tsx`
- Modify: `frontend/src/components/publishing/PublishingPilotCard.tsx`
- Create: `frontend/src/components/publishing/PublishingPilotCard.test.tsx`

- [ ] **Step 1: Add failing workbench and card tests**

In `frontend/src/components/publishing/PublishingPilotWorkbench.test.tsx`, add a case asserting:

```tsx
expect(await screen.findByText(/draft-only mode/i)).toBeInTheDocument()
expect(screen.getByText(/OPENROUTER_API_KEY/i)).toBeInTheDocument()
```

Create `frontend/src/components/publishing/PublishingPilotCard.test.tsx` with a focused test:

```tsx
test('disables caption generation and keeps draft creation available in draft-only mode', async () => {
  ...
  expect(screen.getByRole('button', { name: /Generate caption/i })).toBeDisabled()
  expect(screen.getByText(/OPENROUTER_API_KEY is not configured/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Create draft/i })).toBeEnabled()
})
```

- [ ] **Step 2: Run the targeted frontend tests to verify failure**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/frontend
npm test -- src/components/publishing/PublishingPilotWorkbench.test.tsx src/components/publishing/PublishingPilotCard.test.tsx
```

Expected: FAIL because readiness is not threaded into the workbench/card yet.

- [ ] **Step 3: Implement workbench readiness display**

In `frontend/src/components/publishing/PublishingPilotWorkbench.tsx`:
- Query `getPublishingReadiness()` with a stable React Query key.
- Render a warning box when `degraded_mode === 'draft_only'`.
- Pass the readiness object down to each `PublishingPilotCard`.

Keep the current ready-items/captions/publish-jobs fetching order unchanged.

- [ ] **Step 4: Implement card-level degradation**

In `frontend/src/components/publishing/PublishingPilotCard.tsx`:
- Extend props to accept readiness.
- Disable `Generate caption` when `caption_generation_ready` is false.
- Show the reason text near the button using `missing_requirements` or `notes`.
- Leave `Create draft` enabled when `draft_publish_ready` is true.
- Do not remove the existing local error handling for real action failures.

- [ ] **Step 5: Run the targeted frontend tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/frontend
npm test -- src/pages/Marketing.test.tsx src/components/publishing/PublishingPilotWorkbench.test.tsx src/components/publishing/PublishingPilotCard.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add frontend/src/components/publishing/PublishingPilotWorkbench.tsx frontend/src/components/publishing/PublishingPilotWorkbench.test.tsx frontend/src/components/publishing/PublishingPilotCard.tsx frontend/src/components/publishing/PublishingPilotCard.test.tsx
git commit -m "feat(hollowforge): add draft-only publishing degrade mode"
```

## Task 5: Final Targeted Verification

**Files:**
- No new files

- [ ] **Step 1: Run the full targeted backend verification**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_publishing_routes.py tests/test_publishing_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the full targeted frontend verification**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/frontend
npm test -- src/pages/Marketing.test.tsx src/components/publishing/PublishingPilotWorkbench.test.tsx src/components/publishing/PublishingPilotCard.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Verify working tree scope**

Run:

```bash
git status --short
```

Expected:
- Only the intended feature files are staged/committed for this branch.
- Existing pilot docs/data dirtiness remains untouched unless intentionally excluded from the commit set.

- [ ] **Step 4: Commit the verification checkpoint if needed**

If final fixups were required after targeted verification:

```bash
git add <relevant files>
git commit -m "test(hollowforge): verify ready queue ops degrade path"
```

If no fixups were needed, skip this commit.
