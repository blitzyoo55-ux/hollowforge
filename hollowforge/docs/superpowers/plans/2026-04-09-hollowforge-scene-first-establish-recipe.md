# HollowForge Scene-First Establish Recipe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `establish` comic panels read as room-first storytelling cuts instead of glamour-biased single-character stills, without changing the broader comic or teaser pipeline.

**Architecture:** Keep the existing panel-role render profile layer, but add a tightly bounded `establish_env_v2` path that only changes prompt ordering, subject prominence, optional `Artist Loft Morning` scene cues, and establish-specific negatives. Do not split checkpoints in this phase; keep the same generation lane and fix composition behavior through prompt assembly and lightweight location metadata only.

**Tech Stack:** Python, FastAPI service layer, existing SQLite-backed comic pipeline, JSON location catalog, pytest, existing remote render smoke helper

---

## Preconditions

- I'm using the writing-plans skill to create the implementation plan.
- Follow `@superpowers:test-driven-development` for each behavior change.
- Follow `@superpowers:verification-before-completion` before claiming each checkpoint.
- Treat [2026-04-09-hollowforge-scene-first-establish-recipe-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/docs/superpowers/specs/2026-04-09-hollowforge-scene-first-establish-recipe-design.md) as the source spec.
- Preserve the current comic import / remote still render / selected render / export / teaser flow.
- Do not add migrations in this phase.
- Do not touch unrelated dirty files already in the repo:
  - `backend/app/services/prompt_factory_service.py`
  - `backend/tests/test_sequence_registry.py`
  - `frontend/src/api/client.ts`
  - existing unrelated `data/` artifacts
  - existing 3월 문서 변경
- Be careful with already-dirty docs:
  - `README.md`
  - `STATE.md`
  - `ROADMAP.md`
  Only add the establish-recipe note after live acceptance, and do not overwrite unrelated local edits.

## File Map

### Profile and metadata

- Modify: `backend/app/services/comic_render_profiles.py`
  - extend `ComicPanelRenderProfile` with establish-only scene-first knobs
  - add deterministic scene-cue selection helper
  - upgrade establish profile from `establish_env_v1` to `establish_env_v2`
- Modify: `backend/app/models.py`
  - allow optional `scene_cues` on `StoryPlannerLocationCatalogEntry`
- Modify: `backend/app/story_planner_assets/locations.json`
  - add optional `scene_cues` only for `artist_loft_morning`
- Modify: `backend/tests/test_comic_render_profiles.py`
  - cover `establish_env_v2`, cue selection, and bounded scope behavior
- Modify: `backend/tests/test_story_planner_catalog.py`
  - keep catalog schema expectations aligned with the new optional location field

### Prompt integration

- Modify: `backend/app/services/comic_render_service.py`
  - resolve scene cues from the story-planner catalog via `location_label`
  - assemble establish prompts in `scene_first` order
  - reduce subject-prominence language only for establish
  - inject selected scene cues only for establish
  - append establish-only anti-glamour negatives
- Modify: `backend/tests/test_comic_render_service.py`
  - assert scene-first prompt order, same-checkpoint behavior, catalog-backed cue injection, and stronger establish negatives

### Acceptance and docs

- Modify: `README.md`
  - add a short note that establish panels now use a scene-first prompt recipe
- Modify: `STATE.md`
  - replace the current “next bounded fix” note with the landed establish recipe once accepted
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`
  - add one sentence that establish panels intentionally bias toward room readability over portrait glamour

## Task 1: Add RED Tests For Establish-Only Scene-First Profile Behavior

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_comic_render_profiles.py`
- Modify: `backend/app/story_planner_assets/locations.json`
- Modify: `backend/tests/test_story_planner_catalog.py`

- [ ] **Step 1: Add failing profile tests for the new establish knobs**

Extend `backend/tests/test_comic_render_profiles.py` with coverage like:

```python
def test_resolve_profile_returns_establish_env_v2_for_establish_panel() -> None:
    profile = resolve_comic_panel_render_profile({"panel_type": "establish"})
    assert profile.profile_id == "establish_env_v2"
    assert profile.prompt_order_mode == "scene_first"
    assert profile.subject_prominence_mode == "reduced"
    assert profile.scene_cue_mode == "artist_loft_scene_cues"
```

```python
def test_select_scene_cues_returns_first_two_artist_loft_cues() -> None:
    location = {
        "id": "artist_loft_morning",
        "scene_cues": ["tall factory windows", "easel", "canvas"],
    }
    assert select_scene_cues(location, scene_cue_mode="artist_loft_scene_cues") == [
        "tall factory windows",
        "easel",
    ]
```

```python
def test_select_scene_cues_is_empty_when_location_has_no_scene_cues() -> None:
    location = {"id": "moonlit_bathhouse"}
    assert select_scene_cues(location, scene_cue_mode="artist_loft_scene_cues") == []
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_profiles.py -k "establish_env_v2 or scene_cues"
```

Expected: FAIL because the new profile fields, optional model field, and cue helper do not exist yet.

- [ ] **Step 3: Add minimal metadata needed for the failing case**

Update `backend/app/story_planner_assets/locations.json` only for `artist_loft_morning`:

```json
"scene_cues": [
  "tall factory windows",
  "easel",
  "canvas",
  "worktable",
  "coffee mug",
  "sketchbook"
]
```

Do not add `scene_cues` to other locations in this phase.

- [ ] **Step 4: Allow the optional catalog field**

In `backend/app/models.py`, extend only the location catalog model:

```python
class StoryPlannerLocationCatalogEntry(BaseModel):
    model_config = {"extra": "forbid"}
    ...
    scene_cues: List[str] = Field(default_factory=list, max_length=12)
```

Keep every other story-planner model unchanged.

- [ ] **Step 5: Update the catalog schema test**

In `backend/tests/test_story_planner_catalog.py`, update the location-key expectation to include `scene_cues` and add one explicit optionality check such as:

```python
assert all("scene_cues" in location.model_dump() for location in catalog.locations)
artist_loft = next(location for location in catalog.locations if location.id == "artist_loft_morning")
assert artist_loft.scene_cues[:2] == ["tall factory windows", "easel"]
```

Do not loosen the `extra="forbid"` contract.

- [ ] **Step 6: Implement the minimal profile-layer changes**

In `backend/app/services/comic_render_profiles.py`:

- extend the dataclass:

```python
@dataclass(frozen=True)
class ComicPanelRenderProfile:
    profile_id: str
    panel_types: tuple[str, ...]
    lora_mode: str
    width: int
    height: int
    negative_prompt_append: str
    anchor_filter_mode: str
    prompt_order_mode: str = "default_subject_first"
    subject_prominence_mode: str = "default"
    scene_cue_mode: str = "none"
```

- add:

```python
def select_scene_cues(
    location: dict[str, object] | None,
    *,
    scene_cue_mode: str,
) -> list[str]:
    ...
```

- upgrade only the establish profile:

```python
_make_profile(
    "establish_env_v2",
    ("establish",),
    lora_mode="filter_beauty_enhancers",
    width=1216,
    height=832,
    negative_prompt_append="glamour shoot, fashion editorial, close portrait, airbrushed skin, copy-paste composition, single-subject glamour poster, pinup composition, beauty key visual, empty background, minimal room detail, subject filling frame",
    anchor_filter_mode="drop_portrait_bias",
    prompt_order_mode="scene_first",
    subject_prominence_mode="reduced",
    scene_cue_mode="artist_loft_scene_cues",
)
```

Leave `beat_dialogue_v1`, `insert_prop_v1`, and `closeup_emotion_v1` unchanged.

- [ ] **Step 7: Re-run the tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_comic_render_profiles.py \
  tests/test_story_planner_catalog.py -k "establish_env_v2 or scene_cues or catalog"
```

Expected: PASS.

- [ ] **Step 8: Commit the profile-layer change**

```bash
git add backend/app/models.py \
  backend/app/services/comic_render_profiles.py \
  backend/app/story_planner_assets/locations.json \
  backend/tests/test_comic_render_profiles.py \
  backend/tests/test_story_planner_catalog.py
git commit -m "feat(hollowforge): add scene-first establish profile"
```

## Task 2: Make Establish Prompt Assembly Truly Scene-First

**Files:**
- Modify: `backend/app/services/comic_render_service.py`
- Modify: `backend/tests/test_comic_render_service.py`

- [ ] **Step 1: Add failing prompt-shape tests**

Extend `backend/tests/test_comic_render_service.py` with coverage like:

```python
async def test_build_prompt_frontloads_scene_cues_for_establish_panels() -> None:
    prompt = comic_render_service._build_prompt(
        {
            "prompt_prefix": "masterpiece, best quality, tasteful adult allure",
            "canonical_prompt_anchor": "Camila Duarte, glamorous adult woman, luminous skin",
            "location_label": "Artist Loft Morning",
            "location_scene_cues": ["tall factory windows", "easel"],
            "panel_type": "establish",
            ...
        }
    )
    assert prompt.startswith("Setting: inside Artist Loft Morning.")
    assert "Scene cues: tall factory windows; easel." in prompt
    assert "tasteful adult allure" not in prompt
    assert "glamorous adult woman" not in prompt
```

```python
async def test_build_generation_request_keeps_same_checkpoint_for_establish_panel(...) -> None:
    payload = generation_service.batch_calls[0][0]
    assert payload["checkpoint"] == "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors"
```

```python
async def test_build_generation_request_appends_scene_first_establish_negatives(...) -> None:
    payload = generation_service.batch_calls[0][0]
    assert "single-subject glamour poster" in payload["negative_prompt"]
    assert "subject filling frame" in payload["negative_prompt"]
```

```python
async def test_build_generation_request_loads_artist_loft_scene_cues_from_catalog(...) -> None:
    payload = generation_service.batch_calls[0][0]
    assert "Scene cues: tall factory windows; easel." in payload["prompt"]
```

- [ ] **Step 2: Run the targeted tests to verify RED**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_service.py -k "scene_first or scene_cues or subject_filling_frame or same_checkpoint"
```

Expected: FAIL because `_build_prompt()` does not yet know about catalog-backed `scene_cues`, reduced subject prominence, or the expanded establish negative policy.

- [ ] **Step 3: Implement the minimal prompt integration**

In `backend/app/services/comic_render_service.py`:

- add a small helper that resolves location metadata from the story-planner catalog using `location_label`
- resolve the profile once inside `_build_prompt()`
- add establish-only helper branches, for example:

```python
location_metadata = _resolve_location_catalog_entry(
    str(context.get("location_label") or "")
)
scene_cues = select_scene_cues(
    location_metadata,
    scene_cue_mode=profile.scene_cue_mode,
)
```

```python
if profile.prompt_order_mode == "scene_first":
    prompt_parts = [
        setting_block,
        scene_cue_block,
        composition_block,
        subject_prominence_block,
        action_block,
        minimal_subject_block,
        continuity_block,
    ]
```

```python
if profile.subject_prominence_mode == "reduced":
    # Do not include tasteful adult allure or glamour-forward subject adjectives.
```

Implementation constraints:

- same checkpoint, workflow lane, and LoRA filtering behavior as today
- no changes to `beat`, `insert`, or `closeup` prompt order
- keep existing remote dispatch and callback behavior untouched
- do not modify `comic_story_bridge_service.py`; derive cues at render time from `location_label`

- [ ] **Step 4: Re-run the targeted tests to verify GREEN**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_service.py -k "scene_first or scene_cues or subject_filling_frame or same_checkpoint"
```

Expected: PASS.

- [ ] **Step 5: Run the focused backend regression bundle**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_comic_render_profiles.py \
  tests/test_story_planner_catalog.py \
  tests/test_comic_render_service.py \
  tests/test_comic_render_dispatch_service.py
```

Expected: PASS.

- [ ] **Step 6: Commit the prompt integration**

```bash
git add backend/app/services/comic_render_service.py \
  backend/tests/test_comic_render_service.py
git commit -m "feat(hollowforge): make establish prompts scene-first"
```

## Task 3: Verify The Live Establish Output Improves Before Any Doc Claim

**Files:**
- Modify: none
- Verify: `backend/scripts/launch_comic_remote_render_smoke.py`

- [ ] **Step 1: Restart the stable backend so live validation uses the new code**

Run:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <backend_pid>
sleep 2
lsof -nP -iTCP:8000 -sTCP:LISTEN
curl -s http://127.0.0.1:8000/api/v1/system/health
```

Expected: a new backend PID is listening on `127.0.0.1:8000` and health is `healthy`.

- [ ] **Step 2: Run the single-panel remote smoke**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python scripts/launch_comic_remote_render_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --title "Camila Artist Loft Morning Scene-First Validation" \
  --character-slug camila_duarte \
  --character-version-id charver_camila_duarte_canonical_still_v1 \
  --story-prompt "{character_name} stands inside an artist loft in the morning, with sunlight, easels, canvas, coffee, and a room-first establishing manga panel that clearly differs from the later emotional close panels." \
  --candidate-count 3 \
  --render-poll-attempts 360 \
  --render-poll-sec 1.0
```

Expected:

- `overall_success: true`
- one `selected_render_asset_storage_path`

- [ ] **Step 3: Inspect the selected PNG directly**

Use image inspection on the selected output path and compare it against:

- [a9d50865-f0a3-4ad5-9aee-64b324fab7bc.png](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/data/outputs/a9d50865-f0a3-4ad5-9aee-64b324fab7bc.png)

Acceptance criteria:

- at least two loft-readable cues are visible
- subject no longer fills most of the frame
- room readability is clearly better than `a9d50865...`
- the three candidates do not look like near-identical portraits

- [ ] **Step 4: If live acceptance still fails, stop here**

Do **not** update docs or claim completion.

Instead:

- capture the selected output path
- note the exact visual failure
- surface that the next fix must be larger than prompt-order-only tuning

- [ ] **Step 5: If live acceptance passes, commit the acceptance evidence note only if needed**

No code change required here. This step is only a checkpoint before docs.

## Task 4: Update Re-entry Docs Only After Live Acceptance Passes

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 1: Carefully add the establish-only note without overwriting unrelated edits**

Add a short, bounded note:

- `README.md`: establish panels now use a scene-first prompt recipe
- `STATE.md`: current next issue moves beyond establish recipe only if live acceptance passed
- `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`: establish panels intentionally optimize for room readability first

Do not rewrite surrounding unrelated local changes.

- [ ] **Step 2: Run diff hygiene**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge
git diff --check
```

Expected: no whitespace or patch formatting errors.

- [ ] **Step 3: Commit the doc update**

```bash
git add README.md STATE.md docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): note scene-first establish recipe"
```

## Final Verification

- [ ] **Step 1: Re-run the full focused verification bundle**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_comic_render_profiles.py \
  tests/test_story_planner_catalog.py \
  tests/test_comic_render_service.py \
  tests/test_comic_render_dispatch_service.py
```

Expected: PASS.

- [ ] **Step 2: Re-state live evidence**

Record:

- smoke `episode_id`
- selected establish asset path
- whether acceptance passed or failed
- if failed, stop with evidence and do not claim the plan is complete
- if passed, cite the updated docs and final commit SHAs
