# HollowForge Comic Panel Render Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `favorite-informed canonical still` from comic generation behavior by introducing panel-role-aware comic render profiles so `establish / beat / insert / closeup` panels stop collapsing into the same glamour-biased still.

**Architecture:** Keep `character_version` as the identity source and add a code-backed `comic_render_profiles` registry that resolves a panel-role-specific generation recipe before `GenerationCreate` is built. Apply the resolved profile inside `comic_render_service` so prompt structure stays in place but `checkpoint / LoRA filtering / width / height / negative append / anchor filtering` can change by panel role without adding new database tables.

**Tech Stack:** Python, FastAPI service layer, existing SQLite-backed comic pipeline, pytest, existing comic dry-run helpers

---

## Preconditions

- I'm using the writing-plans skill to create the implementation plan.
- Follow `@superpowers:test-driven-development` for each behavior change.
- Follow `@superpowers:verification-before-completion` before claiming each checkpoint.
- Treat [2026-04-09-hollowforge-comic-panel-render-profile-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/docs/superpowers/specs/2026-04-09-hollowforge-comic-panel-render-profile-design.md) as the source spec.
- Do not touch unrelated dirty files already in the repo:
  - `backend/app/services/prompt_factory_service.py`
  - `backend/tests/test_sequence_registry.py`
  - `frontend/src/api/client.ts`
  - existing docs and `data/` artifacts unrelated to this bounded fix
- Do not add migrations in this phase.
- Preserve the existing comic import / remote render / selected render / export / teaser pipeline.

## File Map

### New profile layer

- Create: `backend/app/services/comic_render_profiles.py`
  - code-backed panel-role registry
  - profile resolution helpers
  - LoRA filtering and anchor-filter helpers
- Create: `backend/tests/test_comic_render_profiles.py`
  - unit coverage for profile resolution and filtering behavior

### Render integration

- Modify: `backend/app/services/comic_render_service.py`
  - resolve profile before building `GenerationCreate`
  - use panel-role-specific width / height / loras / negative / anchor filtering
  - keep structured prompt assembly but make it operate on role-filtered context
- Modify: `backend/tests/test_comic_render_service.py`
  - assert resolved dimensions, filtered LoRAs, negative prompt append, and role-specific prompt shaping

### Documentation and acceptance

- Modify: `README.md`
  - note that comic still generation now uses panel-role-aware render profiles
- Modify: `STATE.md`
  - replace the current “next bounded fix” note with the landed profile split once complete
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`
  - add a short note that panel roles now intentionally use different generation profiles

## Task 1: Add Failing Tests For The Panel-Role Profile Layer

**Files:**
- Create: `backend/tests/test_comic_render_profiles.py`

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/test_comic_render_profiles.py`.

Required coverage:

```python
def test_resolve_profile_returns_establish_env_profile_for_establish_panel():
    profile = resolve_comic_panel_render_profile({"panel_type": "establish"})
    assert profile.profile_id == "establish_env_v1"
    assert profile.width == 1216
    assert profile.height == 832
```

```python
def test_establish_profile_filters_beauty_enhancers():
    filtered = filter_profile_loras(
        [{"filename": "DetailedEyes_V3", "strength": 0.45},
         {"filename": "Face_Enhancer_Illustrious", "strength": 0.36}],
        lora_mode="filter_beauty_enhancers",
    )
    assert filtered == []
```

```python
def test_closeup_profile_keeps_identity_loras():
    profile = resolve_comic_panel_render_profile({"panel_type": "closeup"})
    assert profile.profile_id == "closeup_emotion_v1"
    assert profile.lora_mode == "inherit_all"
```

- [ ] **Step 2: Run the test file to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_profiles.py
```

Expected: FAIL because the service module does not exist yet.

- [ ] **Step 3: Implement the minimal profile registry**

Create `backend/app/services/comic_render_profiles.py`.

Required initial API:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ComicPanelRenderProfile:
    profile_id: str
    panel_types: tuple[str, ...]
    lora_mode: str
    width: int
    height: int
    negative_prompt_append: str
    anchor_filter_mode: str

def resolve_comic_panel_render_profile(context: dict[str, object]) -> ComicPanelRenderProfile:
    ...

def filter_profile_loras(
    loras: list[dict[str, object]],
    *,
    lora_mode: str,
) -> list[dict[str, object]]:
    ...
```

Required initial profiles:

- `establish_env_v1`
- `beat_dialogue_v1`
- `insert_prop_v1`
- `closeup_emotion_v1`

Required initial behavior:

- `establish -> 1216x832`
- `beat -> 960x1216`
- `insert -> 1024x1024`
- `closeup -> 832x1216`

- [ ] **Step 4: Re-run the unit tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_profiles.py
```

Expected: PASS.

- [ ] **Step 5: Commit the profile layer**

```bash
git add backend/app/services/comic_render_profiles.py \
  backend/tests/test_comic_render_profiles.py
git commit -m "feat(hollowforge): add comic panel render profiles"
```

## Task 2: Wire Profile Resolution Into Comic Render Requests

**Files:**
- Modify: `backend/app/services/comic_render_service.py`
- Modify: `backend/tests/test_comic_render_service.py`

- [ ] **Step 1: Add the failing integration tests**

Extend `backend/tests/test_comic_render_service.py`.

Required coverage:

```python
async def test_build_generation_request_uses_establish_profile_dimensions(...):
    panel_id = await _create_establish_panel_fixture(...)
    result = await queue_panel_render_candidates(...)
    payload = generation_service.batch_calls[0][0]
    assert payload["width"] == 1216
    assert payload["height"] == 832
```

```python
async def test_establish_generation_filters_beauty_enhancer_loras(...):
    payload = generation_service.batch_calls[0][0]
    assert payload["loras"] == []
```

```python
async def test_closeup_generation_keeps_character_version_loras(...):
    payload = generation_service.batch_calls[0][0]
    assert payload["loras"] != []
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_service.py -k "profile or establish or closeup"
```

Expected: FAIL because the generation request still inherits the same recipe for every panel.

- [ ] **Step 3: Integrate the minimal implementation**

In `backend/app/services/comic_render_service.py`:

- import `resolve_comic_panel_render_profile` and filtering helpers
- resolve the profile inside `_build_generation_request()`
- replace direct context inheritance with profile-aware values for:
  - `loras`
  - `width`
  - `height`
  - `negative_prompt`
- keep `checkpoint` and `workflow_lane` inherited in v1

Required implementation shape:

```python
profile = resolve_comic_panel_render_profile(context)
filtered_loras = filter_profile_loras(raw_loras, lora_mode=profile.lora_mode)
negative_prompt = merge_negative_prompt(
    base_negative_prompt,
    profile.negative_prompt_append,
)
```

Do not rewrite unrelated queueing or callback code in this task.

- [ ] **Step 4: Re-run the targeted tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_service.py -k "profile or establish or closeup"
```

Expected: PASS.

- [ ] **Step 5: Commit the render integration**

```bash
git add backend/app/services/comic_render_service.py \
  backend/tests/test_comic_render_service.py
git commit -m "feat(hollowforge): apply comic render profiles by panel role"
```

## Task 3: Apply Role-Specific Anchor Filtering And Negative Prompt Policy

**Files:**
- Modify: `backend/app/services/comic_render_profiles.py`
- Modify: `backend/app/services/comic_render_service.py`
- Modify: `backend/tests/test_comic_render_profiles.py`
- Modify: `backend/tests/test_comic_render_service.py`

- [ ] **Step 1: Add the failing behavior tests**

Add assertions for:

```python
def test_drop_portrait_bias_filters_glamour_anchor_fragments():
    filtered = filter_anchor_fragments(
        ["brazilian glamour beauty", "warm hazel eyes", "elegant proportions"],
        anchor_filter_mode="drop_portrait_bias",
    )
    assert "brazilian glamour beauty" not in filtered
    assert "warm hazel eyes" in filtered
```

```python
async def test_establish_prompt_includes_environment_priority_without_glamour_bias(...):
    payload = generation_service.batch_calls[0][0]
    assert "environment-first framing" in payload["prompt"]
    assert "high-response beauty editorial" not in payload["prompt"]
```

```python
async def test_establish_negative_prompt_appends_glamour_suppression_terms(...):
    payload = generation_service.batch_calls[0][0]
    assert "glamour shoot" in payload["negative_prompt"]
    assert "close portrait" in payload["negative_prompt"]
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_profiles.py tests/test_comic_render_service.py -k "anchor or glamour or negative"
```

Expected: FAIL because anchor filtering and negative append are not complete yet.

- [ ] **Step 3: Implement the minimal filtering policy**

In `backend/app/services/comic_render_profiles.py`:

- add `filter_anchor_fragments(...)`
- define role-specific negative additions

Required suppression terms for `establish_env_v1`:

- `glamour shoot`
- `fashion editorial`
- `close portrait`
- `airbrushed skin`
- `copy-paste composition`

Required suppression terms for `closeup_emotion_v1`:

- `plastic skin`
- `waxy face`
- `dead eyes`

In `backend/app/services/comic_render_service.py`:

- run anchor filtering before `style_and_subject` is assembled
- append profile negatives without dropping the base negative prompt

- [ ] **Step 4: Re-run the targeted tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_profiles.py tests/test_comic_render_service.py -k "anchor or glamour or negative"
```

Expected: PASS.

- [ ] **Step 5: Commit the filtering policy**

```bash
git add backend/app/services/comic_render_profiles.py \
  backend/app/services/comic_render_service.py \
  backend/tests/test_comic_render_profiles.py \
  backend/tests/test_comic_render_service.py
git commit -m "fix(hollowforge): reduce glamour bias in comic panel renders"
```

## Task 4: Verify Against A Real Comic Dry Run And Record The Outcome

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 1: Add the documentation updates**

Document three operator-visible changes:

- panel roles now use different render profiles
- `establish` and `insert` intentionally suppress glamour bias
- if a page still collapses into repeated portraits, the next tuning target is profile values, not story import

- [ ] **Step 2: Run the focused backend test bundle**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_story_planner_service.py \
  tests/test_comic_story_bridge_service.py \
  tests/test_comic_render_profiles.py \
  tests/test_comic_render_service.py \
  tests/test_comic_render_dispatch_service.py \
  tests/test_comic_remote_render_callback.py
```

Expected: PASS.

- [ ] **Step 3: Run a live one-shot dry run using the existing helper**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python scripts/launch_comic_remote_one_shot_dry_run.py \
  --base-url http://127.0.0.1:8000 \
  --title "Camila Artist Loft Morning Profile Validation" \
  --character-id char_camila_duarte \
  --character-version-id charver_camila_duarte_still_v1
```

Expected:

- `overall_success: true`
- `selected_panel_asset_count: 4`
- new preview/report/export paths printed

- [ ] **Step 4: Perform visual acceptance before claiming completion**

Inspect the regenerated page preview and at least the selected `establish` and `insert` assets.

Acceptance criteria:

- establish panel reads as room-first
- insert panel reads as object-first
- closeup is still allowed to be face-first
- four selected panels are not visually interchangeable

If visual acceptance fails, stop and open a follow-up spec instead of continuing to tune ad hoc.

- [ ] **Step 5: Commit docs and acceptance notes**

```bash
git add README.md STATE.md docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): document comic panel render profiles"
```

## Final Verification

- [ ] **Step 1: Run diff hygiene**

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge
git diff --check
```

Expected: no output.

- [ ] **Step 2: Re-run the focused backend bundle**

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_story_planner_service.py \
  tests/test_comic_story_bridge_service.py \
  tests/test_comic_render_profiles.py \
  tests/test_comic_render_service.py \
  tests/test_comic_render_dispatch_service.py \
  tests/test_comic_remote_render_callback.py
```

Expected: PASS.

- [ ] **Step 3: Capture the final operator evidence**

Record in the execution notes:

- preview PNG path
- export ZIP path
- dry-run report path
- whether establish / insert / beat / closeup were visually distinct
