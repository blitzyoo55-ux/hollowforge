# Story Planner V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `Story Planner` mode to `/prompt-factory` that turns a freeform story prompt into an approved shot plan and then queues anchor still batches without auto-starting animation.

**Architecture:** Keep the v1 planner small by using structured file-based canon catalogs plus an ephemeral preview artifact contract instead of adding new database tables. Backend exposes three Story Planner endpoints under the existing marketing/tool surface: catalog read, plan preview, and approval-to-anchor-queue. Frontend splits the new mode into focused components under `components/tools/story-planner` and keeps `PromptFactory.tsx` as the mode shell.

**Tech Stack:** FastAPI, Pydantic v2, existing generation queue service, React 19, TanStack Query, Axios API client, Vitest, pytest

---

## File Map

### Backend

- Create: `backend/app/story_planner_assets/characters.json`
- Create: `backend/app/story_planner_assets/locations.json`
- Create: `backend/app/story_planner_assets/policy_packs.json`
- Create: `backend/app/services/story_planner_catalog.py`
- Create: `backend/app/services/story_planner_service.py`
- Create: `backend/tests/test_story_planner_catalog.py`
- Create: `backend/tests/test_story_planner_service.py`
- Create: `backend/tests/test_story_planner_routes.py`
- Create: `backend/scripts/launch_story_planner_smoke.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/marketing.py`
- Modify: `backend/tests/test_marketing_routes.py`

### Frontend

- Create: `frontend/src/components/tools/story-planner/StoryPlannerMode.tsx`
- Create: `frontend/src/components/tools/story-planner/StoryPlannerInputPanel.tsx`
- Create: `frontend/src/components/tools/story-planner/StoryPlannerPlanReview.tsx`
- Create: `frontend/src/components/tools/story-planner/StoryPlannerAnchorResults.tsx`
- Create: `frontend/src/components/tools/story-planner/StoryPlannerMode.test.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/PromptFactory.tsx`
- Modify: `frontend/src/pages/PromptFactory.test.tsx`

### Docs

- Modify: `docs/HOLLOWFORGE_MARKET_VALIDATION_PRESET_RUNBOOK_20260313.md`

---

### Task 1: Add Canon Catalogs And Backend Contracts

**Files:**
- Create: `backend/app/story_planner_assets/characters.json`
- Create: `backend/app/story_planner_assets/locations.json`
- Create: `backend/app/story_planner_assets/policy_packs.json`
- Create: `backend/app/services/story_planner_catalog.py`
- Create: `backend/tests/test_story_planner_catalog.py`
- Modify: `backend/app/models.py`

- [ ] **Step 1: Write the failing catalog/model tests**

```python
from app.services.story_planner_catalog import load_story_planner_catalog

def test_load_story_planner_catalog_returns_characters_locations_and_policies():
    catalog = load_story_planner_catalog()
    assert catalog.characters
    assert catalog.locations
    assert {pack.lane for pack in catalog.policy_packs} == {
        "unrestricted",
        "all_ages",
        "adult_nsfw",
    }

def test_story_planner_plan_request_accepts_registry_and_freeform_cast():
    payload = StoryPlannerPlanRequest(
        story_prompt="Hana Seo pauses in a spa corridor after reading a cryptic message.",
        lane="unrestricted",
        cast=[
            StoryPlannerCastInput(role="lead", source_type="registry", character_id="hana_seo"),
            StoryPlannerCastInput(role="support", source_type="freeform", freeform_description="anonymous messenger"),
        ],
    )
    assert payload.cast[0].character_id == "hana_seo"
```

- [ ] **Step 2: Run the backend tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend
pytest tests/test_story_planner_catalog.py -q
```

Expected: FAIL with missing module/class errors for `story_planner_catalog` and `StoryPlannerPlanRequest`.

- [ ] **Step 3: Add minimal catalog assets and Pydantic models**

```python
class StoryPlannerCastInput(BaseModel):
    role: Literal["lead", "support"]
    source_type: Literal["registry", "freeform"]
    character_id: str | None = None
    freeform_description: str | None = None

class StoryPlannerPlanRequest(BaseModel):
    story_prompt: str
    lane: Literal["unrestricted", "all_ages", "adult_nsfw"]
    cast: list[StoryPlannerCastInput] = Field(default_factory=list, max_length=2)
```

```python
def load_story_planner_catalog() -> StoryPlannerCatalog:
    base = Path(__file__).resolve().parent.parent / "story_planner_assets"
    return StoryPlannerCatalog(
        characters=[StoryPlannerCharacter.model_validate(item) for item in json.loads((base / "characters.json").read_text())],
        locations=[StoryPlannerLocation.model_validate(item) for item in json.loads((base / "locations.json").read_text())],
        policy_packs=[StoryPlannerPolicyPack.model_validate(item) for item in json.loads((base / "policy_packs.json").read_text())],
    )
```

- [ ] **Step 4: Re-run the backend tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend
pytest tests/test_story_planner_catalog.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the catalog/schema slice**

```bash
git add backend/app/models.py \
  backend/app/story_planner_assets/characters.json \
  backend/app/story_planner_assets/locations.json \
  backend/app/story_planner_assets/policy_packs.json \
  backend/app/services/story_planner_catalog.py \
  backend/tests/test_story_planner_catalog.py
git commit -m "feat(hollowforge): add story planner catalog contracts"
```

---

### Task 2: Add Planner Preview Service And Routes

**Files:**
- Create: `backend/app/services/story_planner_service.py`
- Create: `backend/tests/test_story_planner_service.py`
- Create: `backend/tests/test_story_planner_routes.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/marketing.py`

- [ ] **Step 1: Write failing planner service and route tests**

```python
async def test_story_planner_preview_builds_episode_brief_and_four_shot_plan():
    response = await plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt="Hana Seo pauses in a marble spa corridor after reading a cryptic message.",
            lane="all_ages",
            cast=[StoryPlannerCastInput(role="lead", source_type="registry", character_id="hana_seo")],
        )
    )
    assert response.episode_brief.one_line_premise
    assert len(response.shots) == 4
    assert response.cast_resolution[0].resolved_character_id == "hana_seo"

async def test_story_planner_plan_route_returns_preview_payload(client):
    response = await client.post(
        "/api/v1/tools/story-planner/plan",
        json={
            "story_prompt": "Hana Seo pauses in a marble spa corridor after reading a cryptic message.",
            "lane": "all_ages",
            "cast": [
                {
                    "role": "lead",
                    "source_type": "registry",
                    "character_id": "hana_seo",
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["episode_brief"]["one_line_premise"]
```

- [ ] **Step 2: Run the preview tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend
pytest tests/test_story_planner_service.py tests/test_story_planner_routes.py -q
```

Expected: FAIL because `plan_story_episode` and Story Planner routes do not exist.

- [ ] **Step 3: Implement the minimal preview service and route handlers**

```python
async def plan_story_episode(request: StoryPlannerPlanRequest) -> StoryPlannerPlanResponse:
    catalog = load_story_planner_catalog()
    policy = resolve_policy_pack(catalog, request.lane)
    cast_resolution = resolve_story_cast(request.cast, catalog.characters)
    location_resolution = resolve_story_location(request.story_prompt, catalog.locations)
    episode_brief = build_episode_brief(request, cast_resolution, location_resolution, policy)
    shots = build_story_shots(request, episode_brief, cast_resolution, location_resolution, policy)
    return StoryPlannerPlanResponse(
        lane=request.lane,
        episode_brief=episode_brief,
        cast_resolution=cast_resolution,
        location_resolution=location_resolution,
        shots=shots,
    )
```

```python
@router.get("/api/v1/tools/story-planner/catalog", response_model=StoryPlannerCatalogResponse)
async def story_planner_catalog() -> StoryPlannerCatalogResponse:
    return get_story_planner_catalog_response()

@router.post("/api/v1/tools/story-planner/plan", response_model=StoryPlannerPlanResponse)
async def story_planner_plan(payload: StoryPlannerPlanRequest) -> StoryPlannerPlanResponse:
    return await plan_story_episode(payload)
```

- [ ] **Step 4: Re-run the planner tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend
pytest tests/test_story_planner_service.py tests/test_story_planner_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit the preview slice**

```bash
git add backend/app/models.py \
  backend/app/routes/marketing.py \
  backend/app/services/story_planner_service.py \
  backend/tests/test_story_planner_service.py \
  backend/tests/test_story_planner_routes.py
git commit -m "feat(hollowforge): add story planner preview flow"
```

---

### Task 3: Add Approval-To-Anchor Queue Handoff

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/routes/marketing.py`
- Modify: `backend/app/services/story_planner_service.py`
- Modify: `backend/tests/test_marketing_routes.py`
- Create: `backend/scripts/launch_story_planner_smoke.py`

- [ ] **Step 1: Write failing approval and handoff tests**

```python
async def test_story_planner_approve_and_generate_queues_two_candidates_per_shot(client):
    response = await client.post("/api/v1/tools/story-planner/generate-anchors", json={
        "approved_plan": build_story_plan_response(),
        "candidate_count": 2,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_shot_count"] == 4
    assert payload["queued_generation_count"] == 8
```

- [ ] **Step 2: Run the approval tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend
pytest tests/test_marketing_routes.py::test_story_planner_approve_and_generate_queues_two_candidates_per_shot -q
```

Expected: FAIL because the approval endpoint and response schema do not exist.

- [ ] **Step 3: Implement the approval endpoint and queue translation**

```python
async def queue_story_plan_anchor_batch(
    approved_plan: StoryPlannerPlanResponse,
    generation_service: GenerationService,
    candidate_count: int = 2,
) -> StoryPlannerAnchorQueueResponse:
    queued = []
    grouped = []
    for shot in approved_plan.shots:
        generation = GenerationCreate(
            prompt=build_anchor_prompt(approved_plan, shot),
            negative_prompt=resolve_lane_negative_prompt(approved_plan.lane, approved_plan.policy_pack),
            checkpoint=select_story_checkpoint(approved_plan, shot),
            workflow_lane=select_story_workflow_lane(approved_plan),
            width=832,
            height=1216,
            steps=30,
            cfg=5.4,
            sampler="euler_a",
            scheduler="normal",
            notes=f"story_planner:{approved_plan.episode_brief.slug}:shot_{shot.shot_no:02d}",
        )
        _, shot_generations = await generation_service.queue_generation_batch(
            generation,
            count=candidate_count,
            seed_increment=1,
        )
        queued.extend(shot_generations)
        grouped.append(
            StoryPlannerQueuedShotResponse(
                shot_no=shot.shot_no,
                generation_ids=[item.id for item in shot_generations],
            )
        )
    return StoryPlannerAnchorQueueResponse(
        lane=approved_plan.lane,
        requested_shot_count=len(approved_plan.shots),
        queued_generation_count=len(queued),
        queued_shots=grouped,
        queued_generations=queued,
    )
```

- [ ] **Step 4: Re-run approval tests and add a smoke script**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend
pytest tests/test_marketing_routes.py -q
```

Expected: PASS with the new Story Planner route coverage included.

- [ ] **Step 5: Commit the approval/handoff slice**

```bash
git add backend/app/models.py \
  backend/app/routes/marketing.py \
  backend/app/services/story_planner_service.py \
  backend/tests/test_marketing_routes.py \
  backend/scripts/launch_story_planner_smoke.py
git commit -m "feat(hollowforge): queue story planner anchor batches"
```

---

### Task 4: Add Story Planner Frontend Mode

**Files:**
- Create: `frontend/src/components/tools/story-planner/StoryPlannerMode.tsx`
- Create: `frontend/src/components/tools/story-planner/StoryPlannerInputPanel.tsx`
- Create: `frontend/src/components/tools/story-planner/StoryPlannerPlanReview.tsx`
- Create: `frontend/src/components/tools/story-planner/StoryPlannerAnchorResults.tsx`
- Create: `frontend/src/components/tools/story-planner/StoryPlannerMode.test.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/PromptFactory.tsx`
- Modify: `frontend/src/pages/PromptFactory.test.tsx`

- [ ] **Step 1: Write failing frontend tests for the new mode**

```tsx
test('switches Prompt Factory into Story Planner mode and renders the input panel', async () => {
  renderPage()
  fireEvent.click(await screen.findByRole('button', { name: /Story Planner/i }))
  expect(screen.getByLabelText(/Story Prompt/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Plan Episode/i })).toBeInTheDocument()
})

test('renders plan review cards after planner preview succeeds', async () => {
  render(<StoryPlannerMode />)
  fireEvent.change(screen.getByLabelText(/Story Prompt/i), { target: { value: 'Hana Seo pauses in a spa corridor.' } })
  fireEvent.click(screen.getByRole('button', { name: /Plan Episode/i }))
  expect(await screen.findByText(/Episode Brief/i)).toBeInTheDocument()
  expect(screen.getAllByText(/Shot/i).length).toBeGreaterThan(0)
})
```

- [ ] **Step 2: Run the frontend tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/frontend
npm run test -- src/components/tools/story-planner/StoryPlannerMode.test.tsx src/pages/PromptFactory.test.tsx
```

Expected: FAIL because the mode button, planner components, and API functions do not exist.

- [ ] **Step 3: Implement API bindings and focused Story Planner components**

```ts
export async function getStoryPlannerCatalog(): Promise<StoryPlannerCatalogResponse> {
  const res = await api.get<StoryPlannerCatalogResponse>('/tools/story-planner/catalog')
  return res.data
}

export async function previewStoryPlan(
  data: StoryPlannerPlanRequest,
): Promise<StoryPlannerPlanResponse> {
  const res = await api.post<StoryPlannerPlanResponse>('/tools/story-planner/plan', data)
  return res.data
}

export async function generateStoryPlanAnchors(
  data: StoryPlannerAnchorQueueRequest,
): Promise<StoryPlannerAnchorQueueResponse> {
  const res = await api.post<StoryPlannerAnchorQueueResponse>('/tools/story-planner/generate-anchors', data)
  return res.data
}
```

```tsx
export function StoryPlannerMode() {
  const catalogQuery = useQuery({ queryKey: ['story-planner-catalog'], queryFn: getStoryPlannerCatalog })
  const previewMutation = useMutation({ mutationFn: previewStoryPlan })
  const queueMutation = useMutation({ mutationFn: generateStoryPlanAnchors })
  const [storyPrompt, setStoryPrompt] = useState('')
  const [lane, setLane] = useState<'unrestricted' | 'all_ages' | 'adult_nsfw'>('unrestricted')
  const [useRegistryCast, setUseRegistryCast] = useState(false)
  const [leadCharacterId, setLeadCharacterId] = useState<string | null>(null)
  const [supportCharacterId, setSupportCharacterId] = useState<string | null>(null)
  const [lastPlan, setLastPlan] = useState<StoryPlannerPlanResponse | null>(null)
  const [lastQueueResult, setLastQueueResult] = useState<StoryPlannerAnchorQueueResponse | null>(null)

  return (
    <>
      <StoryPlannerInputPanel
        storyPrompt={storyPrompt}
        onStoryPromptChange={setStoryPrompt}
        lane={lane}
        onLaneChange={setLane}
        useRegistryCast={useRegistryCast}
        onUseRegistryCastChange={setUseRegistryCast}
        leadCharacterId={leadCharacterId}
        onLeadCharacterIdChange={setLeadCharacterId}
        supportCharacterId={supportCharacterId}
        onSupportCharacterIdChange={setSupportCharacterId}
        catalog={catalogQuery.data}
        onPlanSuccess={setLastPlan}
      />
      <StoryPlannerPlanReview
        plan={lastPlan}
        onRegenerate={() => setLastQueueResult(null)}
        onApproveSuccess={setLastQueueResult}
      />
      <StoryPlannerAnchorResults result={lastQueueResult} />
    </>
  )
}
```

- [ ] **Step 4: Re-run frontend verification**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/frontend
npm run test -- src/components/tools/story-planner/StoryPlannerMode.test.tsx src/pages/PromptFactory.test.tsx
npm run lint
npm run build
```

Expected: All commands PASS.

- [ ] **Step 5: Commit the frontend slice**

```bash
git add frontend/src/api/client.ts \
  frontend/src/components/tools/story-planner/StoryPlannerMode.tsx \
  frontend/src/components/tools/story-planner/StoryPlannerInputPanel.tsx \
  frontend/src/components/tools/story-planner/StoryPlannerPlanReview.tsx \
  frontend/src/components/tools/story-planner/StoryPlannerAnchorResults.tsx \
  frontend/src/components/tools/story-planner/StoryPlannerMode.test.tsx \
  frontend/src/pages/PromptFactory.tsx \
  frontend/src/pages/PromptFactory.test.tsx
git commit -m "feat(hollowforge): add story planner mode"
```

---

### Task 5: Verify Runtime And Update The Runbook

**Files:**
- Modify: `docs/HOLLOWFORGE_MARKET_VALIDATION_PRESET_RUNBOOK_20260313.md`
- Modify: `backend/scripts/launch_story_planner_smoke.py`

- [ ] **Step 1: Document the Story Planner smoke workflow**

```md
## Story Planner Smoke

1. Preview an unrestricted plan from a single-location story prompt.
2. Approve and queue 2-candidate anchors for 4 shots.
3. Verify queue and gallery entries appear.
```

- [ ] **Step 2: Run backend verification**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend
pytest tests/test_story_planner_catalog.py tests/test_story_planner_service.py tests/test_story_planner_routes.py tests/test_marketing_routes.py -q
```

Expected: PASS.

- [ ] **Step 3: Run frontend verification**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/frontend
npm run test
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 4: Run the Story Planner smoke script**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend
python3 scripts/launch_story_planner_smoke.py --lane unrestricted --candidate-count 2
```

Expected: The script prints preview success, queued generation IDs, and queue/gallery links for the resulting shot anchors.

- [ ] **Step 5: Commit docs and final verification artifacts**

```bash
git add docs/HOLLOWFORGE_MARKET_VALIDATION_PRESET_RUNBOOK_20260313.md \
  backend/scripts/launch_story_planner_smoke.py
git commit -m "docs(hollowforge): add story planner smoke workflow"
```
