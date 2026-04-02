# Story Planner Direct Input Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the Story Planner direct-input path so natural-language episode prompts produce better planner guidance, deterministic recommended anchor selection, and more render-oriented anchor prompts without adding a new authoring tool.

**Architecture:** Keep the current `Story Planner` as the primary authoring surface, extend its request/response contract with optional guidance and recommendation metadata, then thread that recommendation through the planner service, rerun CLI, and Story Planner UI. The core change is concentrated in the planner path: lane-aware shot generation, deterministic recommendation rules, and a thin deterministic anchor compiler built from existing planner fields rather than a new model call.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, React 19, TanStack Query, Vitest, Testing Library, existing HollowForge API client

---

## Implementation Notes

- Primary target subtree: `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge`
- Existing unrelated dirtiness is expected in:
  - `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-brief.md`
  - `data/`
- Do not revert or include those files in feature commits.
- Backend tests should use:
  - `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python`
- Frontend tests should run from `frontend/` with:
  - `npm test -- <paths>`
- Keep existing prompt-only planner behavior working. The happy path must still support:
  - `story_prompt`
  - `lane`
  - omitted `cast`
- `Lead lock` and `Support lock` remain a UI composition concern that serializes into the existing `cast` array. Do not add new backend fields for lead/support lock state.
- `location_id` is a hard lock:
  - valid id overrides prompt inference completely
  - invalid id returns `422`
  - `match_note` must change to `Locked to catalog location: <location name>.`
- `preferred_anchor_beat` maps to shot numbers:
  - `exchange -> 2`
  - `reveal -> 3`
  - `decision -> 4`
- Auto recommendation ranking must stay deterministic:
  - `adult_nsfw` + lead+support present: `2 > 3 > 4 > 1`
  - `adult_nsfw` + support missing + reveal detail present: `3 > 4 > 2 > 1`
  - `adult_nsfw` fallback: `4 > 3 > 2 > 1`
  - `all_ages` and `unrestricted`: `1 > 2 > 3 > 4`
- Web UI scope for this branch:
  - show `recommended_anchor_shot_no`
  - show `recommended_anchor_reason`
  - add optional guidance controls
  - do not add a post-queue “selected shot” workflow
- Rerun CLI scope for this branch:
  - use planner recommendation by default
  - preserve explicit `--select-shot` override

## File Map

- Modify: `backend/app/models.py`
  - extend story planner request/response models with optional location/anchor-beat input and recommendation output
- Modify: `backend/app/services/story_planner_service.py`
  - implement location lock semantics, lane-aware shots, deterministic recommendation, and thin anchor compiler updates
- Modify: `backend/tests/test_story_planner_service.py`
  - lock planner recommendation, location lock, lane-aware shot behavior, and render-intent prompt content
- Modify: `backend/tests/test_story_planner_routes.py`
  - lock request/response contract changes and invalid location behavior
- Modify: `backend/scripts/run_pilot_rerun_close_loop.py`
  - default to planner recommendation when explicit shot override is absent
- Modify: `backend/tests/test_run_pilot_rerun_close_loop.py`
  - verify recommendation defaulting and explicit override precedence
- Modify: `frontend/src/api/client.ts`
  - add the new planner request/response fields to the typed client
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerInputPanel.tsx`
  - add optional location lock, preferred anchor beat, and explicit support freeform lock input
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerMode.tsx`
  - manage new UI state, serialize optional guidance into the request, and keep prompt-only mode working
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerPlanReview.tsx`
  - show recommended anchor shot number and reason
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerAnchorResults.tsx`
  - surface planner recommendation context after queueing without adding a new shot-picking flow
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerMode.test.tsx`
  - cover new payload mapping, prompt-only compatibility, and recommendation rendering

## Task 1: Extend The Story Planner Contract With Failing Tests First

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_story_planner_service.py`
- Modify: `backend/tests/test_story_planner_routes.py`

- [ ] **Step 1: Add failing service tests for the new planner contract**

Extend `backend/tests/test_story_planner_service.py` with focused tests like:

```python
def test_plan_story_episode_returns_recommended_anchor_fields() -> None:
    preview = plan_story_episode(_build_request(story_prompt="..."))

    assert preview.recommended_anchor_shot_no in {1, 2, 3, 4}
    assert preview.recommended_anchor_reason


def test_plan_story_episode_uses_locked_location_when_location_id_is_present() -> None:
    request = _build_request(story_prompt="ambiguous corridor prompt")
    request = request.model_copy(update={"location_id": "moonlit_bathhouse"})

    preview = plan_story_episode(request)

    assert preview.location.id == "moonlit_bathhouse"
    assert preview.location.match_note == "Locked to catalog location: Moonlit Bathhouse."


def test_plan_story_episode_prefers_shot_two_for_adult_auto_when_lead_and_support_present() -> None:
    preview = plan_story_episode(_build_request(story_prompt="..."))

    assert preview.recommended_anchor_shot_no == 2


def test_plan_story_episode_respects_explicit_preferred_anchor_beat() -> None:
    request = _build_request(story_prompt="...")
    request = request.model_copy(update={"preferred_anchor_beat": "decision"})

    preview = plan_story_episode(request)

    assert preview.recommended_anchor_shot_no == 4
```

- [ ] **Step 2: Add failing route tests for the expanded request/response**

Extend `backend/tests/test_story_planner_routes.py` with route tests like:

```python
async def test_story_planner_plan_route_returns_recommendation_fields() -> None:
    ...
    assert body["recommended_anchor_shot_no"] == 2
    assert body["recommended_anchor_reason"]


async def test_story_planner_plan_route_returns_422_for_invalid_location_lock() -> None:
    ...
    assert response.status_code == 422
    assert "location_id" in response.json()["detail"]
```

- [ ] **Step 3: Run the targeted backend tests to verify failure**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_story_planner_service.py tests/test_story_planner_routes.py -q
```

Expected: FAIL because the request/response models and planner behavior do not support the new fields yet.

- [ ] **Step 4: Extend `StoryPlannerPlanRequest` and `StoryPlannerPlanResponse` minimally**

In `backend/app/models.py`, add:

```python
StoryPlannerPreferredAnchorBeat = Literal["auto", "exchange", "reveal", "decision"]

class StoryPlannerPlanRequest(BaseModel):
    ...
    location_id: Optional[str] = None
    preferred_anchor_beat: StoryPlannerPreferredAnchorBeat = "auto"

class StoryPlannerPlanResponse(BaseModel):
    ...
    recommended_anchor_shot_no: int
    recommended_anchor_reason: str = Field(min_length=1, max_length=240)
```

Keep existing clients compatible by making new request fields optional with defaults.

- [ ] **Step 5: Run the same tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_story_planner_service.py tests/test_story_planner_routes.py -q
```

Expected: still FAIL, but now at planner logic rather than model validation.

- [ ] **Step 6: Commit Task 1 after Task 2 passes**

Do not commit yet. The model changes should land together with the planner logic that makes the new contract real.

## Task 2: Implement Location Lock, Lane-Aware Shots, And Deterministic Recommendation

**Files:**
- Modify: `backend/app/services/story_planner_service.py`
- Modify: `backend/tests/test_story_planner_service.py`
- Modify: `backend/tests/test_story_planner_routes.py`
- Modify: `backend/app/models.py`

- [ ] **Step 1: Add failing tests for lane-aware shot content**

Add focused service tests like:

```python
def test_adult_lane_shot_two_emphasizes_exchange_signal() -> None:
    preview = plan_story_episode(_build_request(story_prompt="..."))

    assert preview.shots[1].beat == "Introduce the exchange"
    assert "exchange" in preview.shots[1].action.lower() or "gaze" in preview.shots[1].action.lower()


def test_locked_location_overrides_prompt_based_inference() -> None:
    request = StoryPlannerPlanRequest(
        story_prompt="A generic corridor with no obvious match.",
        lane="adult_nsfw",
        location_id="moonlit_bathhouse",
    )

    preview = plan_story_episode(request)

    assert preview.location.id == "moonlit_bathhouse"
    assert preview.location.match_note == "Locked to catalog location: Moonlit Bathhouse."
```

- [ ] **Step 2: Implement locked-location resolution helper**

In `backend/app/services/story_planner_service.py`, add a helper like:

```python
def _resolve_location_with_optional_lock(
    *,
    story_prompt: str,
    location_id: str | None,
    locations: list[StoryPlannerLocationCatalogEntry],
) -> tuple[StoryPlannerLocationCatalogEntry, str]:
    ...
```

Rules:

- valid `location_id` returns the catalog location plus locked `match_note`
- invalid `location_id` raises `ValueError` or a route-consumable validation error
- omitted `location_id` falls back to the current inference helper unchanged

- [ ] **Step 3: Make `_build_shots()` lane-aware without changing the four-shot scaffold**

Refactor `_build_shots()` to accept `lane`:

```python
def _build_shots(
    story_prompt: str,
    lane: str,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    location: StoryPlannerResolvedLocationEntry,
) -> list[StoryPlannerShotCard]:
    ...
```

Implementation rules:

- keep `shot 1` as the establishing frame for every lane
- keep shot numbers and count stable
- for `adult_nsfw`, strengthen `shot 2`, `shot 3`, and `shot 4` by emphasizing:
  - relationship signal
  - readable tension
  - private-space framing
  - expressive body language
- for `all_ages` and `unrestricted`, keep behavior close to the current wording

- [ ] **Step 4: Implement deterministic recommendation helper**

Add a helper like:

```python
def _recommend_anchor_shot(
    *,
    lane: str,
    preferred_anchor_beat: str,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    story_prompt: str,
    shots: list[StoryPlannerShotCard],
) -> tuple[int, str]:
    ...
```

Rules:

- explicit beat:
  - `exchange -> 2`
  - `reveal -> 3`
  - `decision -> 4`
- auto:
  - `adult_nsfw` + lead+support present: `2 > 3 > 4 > 1`
  - `adult_nsfw` + no support + reveal detail present: `3 > 4 > 2 > 1`
  - `adult_nsfw` fallback: `4 > 3 > 2 > 1`
  - `all_ages` and `unrestricted`: `1 > 2 > 3 > 4`
- choose the first valid shot in order
- emit a short reason string

- [ ] **Step 5: Wire the new helpers into `plan_story_episode()`**

Update `plan_story_episode()` so it:

- resolves location through the new optional-lock helper
- calls the lane-aware `_build_shots()`
- stores `recommended_anchor_shot_no`
- stores `recommended_anchor_reason`

- [ ] **Step 6: Run the targeted backend planner tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_story_planner_service.py tests/test_story_planner_routes.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add backend/app/models.py backend/app/services/story_planner_service.py backend/tests/test_story_planner_service.py backend/tests/test_story_planner_routes.py
git commit -m "feat(hollowforge): add planner anchor recommendations"
```

## Task 3: Replace Story-Memo Prompt Assembly With A Thin Anchor Compiler

**Files:**
- Modify: `backend/app/services/story_planner_service.py`
- Modify: `backend/tests/test_story_planner_service.py`

- [ ] **Step 1: Add failing tests for render-oriented anchor prompt structure**

Extend `backend/tests/test_story_planner_service.py` with assertions like:

```python
@pytest.mark.asyncio
async def test_queue_story_planner_anchor_batch_compiles_render_intent_sections() -> None:
    approved_plan = plan_story_episode(_build_request(story_prompt="..."))
    service = _CapturingGenerationService()

    await queue_story_planner_anchor_batch(approved_plan, service, candidate_count=2)

    prompt = service.batch_requests[0][0].prompt
    assert "subject_focus:" in prompt
    assert "relationship_signal:" in prompt
    assert "framing_signal:" in prompt
    assert "continuity_guard:" in prompt
```

- [ ] **Step 2: Add a thin compiler helper**

In `backend/app/services/story_planner_service.py`, add a deterministic helper like:

```python
def _compile_story_planner_anchor_intent(
    *,
    plan: StoryPlannerPlanResponse,
    shot: StoryPlannerShotCard,
) -> dict[str, str]:
    return {
        "subject_focus": ...,
        "relationship_signal": ...,
        "environment_signal": ...,
        "framing_signal": ...,
        "mood_signal": ...,
        "continuity_guard": ...,
    }
```

Use only existing planner fields. Do not add a new LLM call.

- [ ] **Step 3: Rewrite `_build_story_planner_anchor_prompt()` to use compiler output**

Keep the debug-friendly structured prompt style, but replace the story-memo-heavy body with
render-oriented sections such as:

```python
lines = [
    "story_planner_anchor still generation",
    f"story_prompt: {plan.story_prompt}",
    f"lane: {plan.lane}",
    f"policy_pack: {plan.policy_pack_id}",
    f"shot_no: {shot.shot_no}",
    f"subject_focus: {intent['subject_focus']}",
    f"relationship_signal: {intent['relationship_signal']}",
    f"environment_signal: {intent['environment_signal']}",
    f"framing_signal: {intent['framing_signal']}",
    f"mood_signal: {intent['mood_signal']}",
    f"continuity_guard: {intent['continuity_guard']}",
    ...
]
```

Keep continuity metadata, checkpoint, and workflow lane visible in the prompt.

- [ ] **Step 4: Run the targeted compiler tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_story_planner_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/app/services/story_planner_service.py backend/tests/test_story_planner_service.py
git commit -m "feat(hollowforge): compile render-ready anchor prompts"
```

## Task 4: Use Planner Recommendation In The Rerun CLI

**Files:**
- Modify: `backend/scripts/run_pilot_rerun_close_loop.py`
- Modify: `backend/tests/test_run_pilot_rerun_close_loop.py`

- [ ] **Step 1: Add failing rerun-cli tests for recommendation defaulting**

Extend `backend/tests/test_run_pilot_rerun_close_loop.py` with tests like:

```python
def test_runner_uses_recommended_anchor_shot_when_no_explicit_override() -> None:
    ...
    assert selected_generation["shot_no"] == 2


def test_runner_keeps_explicit_select_shot_override_over_recommendation() -> None:
    ...
    assert selected_generation["shot_no"] == 4
```

Use the mocked `plan_result` payload to include:

```python
"recommended_anchor_shot_no": 2,
"recommended_anchor_reason": "shot 2 keeps the exchange readable while preserving location continuity",
```

- [ ] **Step 2: Run the rerun-cli tests to verify failure**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_pilot_rerun_close_loop.py -q
```

Expected: FAIL because the runner still defaults to `select_shot=1`.

- [ ] **Step 3: Implement recommendation-aware selection**

In `backend/scripts/run_pilot_rerun_close_loop.py`:

- change `--select-shot` default from `1` to `0` or `None`-like semantics
- treat an explicit positive `--select-shot` as operator override
- otherwise default to `plan_result["recommended_anchor_shot_no"]`
- preserve explicit `--select-candidate`
- print the selected shot and recommendation context in the labeled output

- [ ] **Step 4: Run the rerun-cli tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_pilot_rerun_close_loop.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add backend/scripts/run_pilot_rerun_close_loop.py backend/tests/test_run_pilot_rerun_close_loop.py
git commit -m "feat(hollowforge): default reruns to planner recommendations"
```

## Task 5: Expose Optional Guidance And Recommendation Metadata In The Web UI

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerInputPanel.tsx`
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerMode.tsx`
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerPlanReview.tsx`
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerAnchorResults.tsx`
- Modify: `frontend/src/components/tools/story-planner/StoryPlannerMode.test.tsx`

- [ ] **Step 1: Add failing frontend tests for payload mapping and recommendation rendering**

Extend `frontend/src/components/tools/story-planner/StoryPlannerMode.test.tsx` with tests like:

```tsx
test('submits optional location lock and preferred anchor beat in the plan payload', async () => {
  ...
  expect(planStoryEpisode).toHaveBeenCalledWith(
    expect.objectContaining({
      location_id: 'moonlit_bathhouse',
      preferred_anchor_beat: 'exchange',
    }),
  )
})

test('keeps prompt-only mode working when all optional controls are unset', async () => {
  ...
  expect(planStoryEpisode).toHaveBeenCalledWith(
    expect.objectContaining({
      cast: [],
      location_id: null,
      preferred_anchor_beat: 'auto',
    }),
  )
})

test('renders the planner recommendation in plan review', async () => {
  ...
  expect(await screen.findByText(/recommended anchor/i)).toBeInTheDocument()
  expect(screen.getByText(/shot 2/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run the Story Planner frontend tests to verify failure**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/frontend
npm test -- src/components/tools/story-planner/StoryPlannerMode.test.tsx
```

Expected: FAIL because the client types and UI state do not yet support the new fields.

- [ ] **Step 3: Extend the typed API client**

In `frontend/src/api/client.ts`, add the new planner fields to the existing types:

```ts
export type StoryPlannerPreferredAnchorBeat = 'auto' | 'exchange' | 'reveal' | 'decision'

export interface StoryPlannerPlanRequest {
  ...
  location_id?: string | null
  preferred_anchor_beat?: StoryPlannerPreferredAnchorBeat
}

export interface StoryPlannerPlanResponse {
  ...
  recommended_anchor_shot_no: number
  recommended_anchor_reason: string
}
```

- [ ] **Step 4: Add optional guidance state to `StoryPlannerMode` and `StoryPlannerInputPanel`**

Implement minimal UI state for:

- `locationId`
- `preferredAnchorBeat`
- support lock mode:
  - unlocked
  - registry
  - freeform

Serialize into request rules:

- unlocked roles are omitted from `cast`
- registry roles produce existing registry entries
- freeform support produces:

```ts
{
  role: 'support',
  source_type: 'freeform',
  freeform_description: supportFreeformDescription.trim(),
}
```

- [ ] **Step 5: Surface recommendation metadata in the review/result components**

In `StoryPlannerPlanReview.tsx`, render:

- recommended anchor shot number
- recommended anchor reason

In `StoryPlannerAnchorResults.tsx`, render advisory summary only, for example:

```tsx
<Metric label="Recommended Anchor" value={`Shot ${result.recommended_anchor_shot_no}`} />
<p>{result.recommended_anchor_reason}</p>
```

Do not add a post-queue shot-selection workflow in this branch.

- [ ] **Step 6: Run the frontend tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/frontend
npm test -- src/components/tools/story-planner/StoryPlannerMode.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git add frontend/src/api/client.ts frontend/src/components/tools/story-planner/StoryPlannerInputPanel.tsx frontend/src/components/tools/story-planner/StoryPlannerMode.tsx frontend/src/components/tools/story-planner/StoryPlannerPlanReview.tsx frontend/src/components/tools/story-planner/StoryPlannerAnchorResults.tsx frontend/src/components/tools/story-planner/StoryPlannerMode.test.tsx
git commit -m "feat(hollowforge): improve direct story planner authoring"
```

## Task 6: Run Final Targeted Verification

**Files:**
- No new files

- [ ] **Step 1: Run the full targeted backend suite**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_story_planner_service.py tests/test_story_planner_routes.py tests/test_run_pilot_rerun_close_loop.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the Story Planner frontend test suite**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/frontend
npm test -- src/components/tools/story-planner/StoryPlannerMode.test.tsx
```

Expected: PASS.

- [ ] **Step 3: Run one live planner preview smoke against the branch backend**

If the branch backend is already running, use it. Otherwise start it first in a
separate shell.

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/launch_story_planner_smoke.py --base-url http://127.0.0.1:8010 --lane adult_nsfw --story-prompt "Hana Seo pauses in a locked corridor while a quiet attendant watches for her next move."
```

Expected:

- plan succeeds
- queue succeeds
- output includes later-shot recommendation metadata or logs that confirm the new default path

- [ ] **Step 4: Inspect the compiled anchor prompt from the newest generated workflow**

Use the most recent generated workflow JSON under `data/workflows/` and confirm the
prompt includes render-oriented sections such as:

- `subject_focus`
- `relationship_signal`
- `framing_signal`
- `continuity_guard`

If the branch backend was not run live in this task, document that this live verification
was skipped and why.

- [ ] **Step 5: Final status check**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge
git status --short
```

Expected:

- only the intended feature changes are present
- existing unrelated `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-brief.md` and `data/` dirtiness may remain and should be called out explicitly

- [ ] **Step 6: Commit any final verification-driven fixes**

If verification required no further code changes, do not create an extra commit. If a
small fix was required, commit only that fix with a narrow message such as:

```bash
git add <exact files>
git commit -m "fix(hollowforge): tighten planner anchor recommendation"
```
