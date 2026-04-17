# HollowForge Character Canon V2 + Series Style Canon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Camila-only V2 render lane that separates identity, series style, binding, and panel-role grammar without replacing the current legacy comic runtime.

**Architecture:** Keep the existing `character_versions`-based comic lane as the default. Introduce a code-backed V2 registry plus a materialized resolver contract (`identity_block`, `style_block`, `binding_block`, `role_block`, `execution_params`, `negative_rules`) and wire it only when an episode is explicitly created/imported with a Camila V2 binding and series style. Validate through backend-first pilot helpers before any frontend selection UX.

**Tech Stack:** FastAPI, Pydantic v2, SQLite/aiosqlite, code-backed registries in Python, pytest, existing comic remote render pipeline, existing smoke helpers.

---

## File Map

### New files

- `backend/app/services/character_canon_v2_registry.py`
  - code-backed V2 character canon entries
- `backend/app/services/series_style_canon_registry.py`
  - code-backed series style canon entries
- `backend/app/services/character_series_binding_registry.py`
  - code-backed Camila pilot binding entries
- `backend/app/services/comic_render_v2_resolver.py`
  - materializes V2 blocks and merge contract into a single render recipe
- `backend/tests/test_character_canon_v2_registry.py`
- `backend/tests/test_series_style_canon_registry.py`
- `backend/tests/test_character_series_binding_registry.py`
- `backend/tests/test_comic_render_v2_resolver.py`
- `backend/tests/test_comic_render_v2_integration.py`
- `backend/scripts/launch_camila_v2_comic_pilot.py`
  - bounded helper for one-shot pilot episode creation/import/render/export
- `backend/scripts/launch_camila_v2_teaser_pilot.py`
  - bounded helper for teaser derivative on the pilot lane

### Modified files

- `backend/app/models.py`
  - add optional V2 identifiers to comic creation/import models and responses
- `backend/app/services/comic_repository.py`
  - persist/read optional `series_style_id`, `character_series_binding_id`, `render_lane`
- `backend/app/routes/comic.py`
  - accept explicit V2 opt-in payload for Camila-only pilot
- `backend/app/services/comic_story_bridge_service.py`
  - preserve explicit V2 metadata through import-story-plan draft building
- `backend/app/services/comic_render_service.py`
  - branch between legacy and V2 resolver at render build time
- `backend/app/services/comic_story_bridge_service.py`
  - ensure imported drafts can preserve V2 lane metadata without changing story semantics
- `backend/app/services/comic_render_dispatch_service.py`
  - include V2 lineage metadata in request snapshots if needed for debugging
- `backend/app/services/comic_render_profiles.py`
  - explicit legacy/V2 boundary coverage only; do not move checkpoint ownership into profiles for V2
- `backend/app/db.py` or migration location already used by repo
  - add episode-level columns if needed (`series_style_id`, `character_series_binding_id`, `render_lane`)
- `README.md`
- `STATE.md`
- `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

### Existing files to reference while implementing

- `backend/app/services/comic_render_service.py`
- `backend/app/services/comic_render_profiles.py`
- `backend/app/services/comic_repository.py`
- `backend/app/routes/comic.py`
- `backend/scripts/launch_comic_remote_render_smoke.py`
- `backend/scripts/launch_comic_remote_one_shot_dry_run.py`
- `backend/scripts/launch_comic_teaser_animation_smoke.py`
- `docs/superpowers/specs/2026-04-09-hollowforge-character-canon-v2-series-style-design.md`
- `docs/superpowers/specs/2026-04-09-hollowforge-comic-panel-render-profile-design.md`

## Scope Guardrails

- Keep the current legacy comic lane as default.
- V2 is `Camila Duarte` only.
- V2 activation must be explicit, not automatic.
- No frontend picker or general UI for V2 in this phase.
- No global migration of other characters.
- No replacement of current teaser worker contracts.
- `comic_panel_render_profile` remains the role grammar layer; for V2 it must not own checkpoint/LoRA family.

## Task 1: Add V2 registry contracts and failing tests

**Files:**
- Create: `backend/app/services/character_canon_v2_registry.py`
- Create: `backend/app/services/series_style_canon_registry.py`
- Create: `backend/app/services/character_series_binding_registry.py`
- Test: `backend/tests/test_character_canon_v2_registry.py`
- Test: `backend/tests/test_series_style_canon_registry.py`
- Test: `backend/tests/test_character_series_binding_registry.py`

- [ ] **Step 1: Write failing registry tests**

Add tests for:
- loading Camila V2 character canon by id
- loading one pilot series style canon by id
- loading one Camila binding by `(character_id, series_style_id)` or explicit binding id
- rejecting unknown ids
- ensuring style-loaded words like `glamour` do not appear in the V2 Camila identity anchor

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_character_canon_v2_registry.py \
  tests/test_series_style_canon_registry.py \
  tests/test_character_series_binding_registry.py
```

Expected: FAIL because registry files/functions do not exist yet.

- [ ] **Step 2: Add minimal typed registry implementations**

Implement code-backed registries with:
- `get_character_canon_v2(character_id: str) -> CharacterCanonV2Entry`
- `get_series_style_canon(series_style_id: str) -> SeriesStyleCanonEntry`
- `get_character_series_binding(binding_id: str) -> CharacterSeriesBindingEntry`
- optional list helpers only if tests need them

Seed only:
- Camila V2 character canon
- one pilot series style canon
- one alternate test-only series style canon with a different `teaser_motion_policy`
- one Camila pilot binding

- [ ] **Step 3: Re-run registry tests**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add \
  backend/app/services/character_canon_v2_registry.py \
  backend/app/services/series_style_canon_registry.py \
  backend/app/services/character_series_binding_registry.py \
  backend/tests/test_character_canon_v2_registry.py \
  backend/tests/test_series_style_canon_registry.py \
  backend/tests/test_character_series_binding_registry.py
git commit -m "feat(hollowforge): add v2 character and style registries"
```

## Task 2: Define resolver output contract and materialization logic

**Files:**
- Create: `backend/app/services/comic_render_v2_resolver.py`
- Test: `backend/tests/test_comic_render_v2_resolver.py`

- [ ] **Step 1: Write failing resolver tests**

Add tests for:
- materialized output contains exactly:
  - `identity_block`
  - `style_block`
  - `binding_block`
  - `role_block`
  - `execution_params`
  - `negative_rules`
- positive merge order is:
  - role
  - identity
  - style
  - binding
  - continuity/location
- negative accumulation order is:
  - style artifact
  - anti-drift
  - binding negative
  - role negative
- execution precedence is:
  - checkpoint/LoRA/step/cfg/sampler from style
  - lock strengths from binding
  - aspect/framing defaults from role profile

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q tests/test_comic_render_v2_resolver.py
```

Expected: FAIL because resolver does not exist yet.

- [ ] **Step 2: Implement minimal resolver**

Implement a single entrypoint such as:

```python
resolve_comic_render_v2_contract(
    *,
    character_id: str,
    series_style_id: str,
    binding_id: str,
    panel_type: str,
    location_label: str | None,
    continuity_notes: str | None,
    role_profile: ComicPanelRenderProfile,
) -> ComicRenderV2Contract
```

The resolver should:
- read the three V2 registries
- read the current panel role profile
- materialize the six output sections
- expose already-ordered `positive_segments` and `negative_segments` or equivalent stable shape for later assembly

- [ ] **Step 3: Re-run resolver tests**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add \
  backend/app/services/comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_resolver.py
git commit -m "feat(hollowforge): add comic render v2 resolver"
```

## Task 3: Add explicit Camila-only V2 opt-in persistence

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/services/comic_repository.py`
- Modify: `backend/app/routes/comic.py`
- Modify: `backend/app/services/comic_story_bridge_service.py`
- Modify: migration files in `backend/migrations/`
- Modify: `backend/app/db.py` only if migration registration requires it
- Test: `backend/tests/test_comic_repository.py`
- Test: `backend/tests/test_comic_routes.py`
- Test: `backend/tests/test_comic_story_bridge_service.py`
- Test: `backend/tests/test_comic_schema.py`
- Add migration in the repo’s existing migration style

- [ ] **Step 1: Write failing persistence/route tests**

Add tests for:
- comic episode import/create can persist optional:
  - `render_lane`
  - `series_style_id`
  - `character_series_binding_id`
- default lane remains `legacy`
- explicit V2 import with non-Camila ids is rejected
- explicit V2 import without both `series_style_id` and `character_series_binding_id` is rejected
- import-story-plan path preserves explicit V2 metadata through `build_comic_draft_from_story_plan(...)`
- schema contract includes the new episode-level fields

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_comic_repository.py \
  tests/test_comic_routes.py \
  tests/test_comic_story_bridge_service.py \
  tests/test_comic_schema.py
```

Expected: FAIL on new fields/validation paths.

- [ ] **Step 2: Add model fields and storage**

Update request/response models to include optional V2 fields.

Add episode-level persistence for:
- `render_lane` with values at least `legacy` and `character_canon_v2`
- `series_style_id`
- `character_series_binding_id`

Keep defaults backward compatible:
- legacy import/create path unchanged when fields are absent

- [ ] **Step 3: Add import bridge propagation**

Update the story-plan import path so explicit V2 metadata survives:
- request model parsing
- route handoff
- draft building

The import path must support:
- explicit `render_lane=character_canon_v2`
- explicit `series_style_id`
- explicit `character_series_binding_id`

without changing story semantics or defaulting any other character into V2.

- [ ] **Step 4: Add route validation**

In route/service validation:
- only allow V2 lane for `Camila Duarte`
- require both `series_style_id` and `character_series_binding_id`
- verify that binding belongs to Camila and the selected series style

- [ ] **Step 5: Re-run focused tests**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add \
  backend/migrations \
  backend/app/db.py \
  backend/app/models.py \
  backend/app/services/comic_repository.py \
  backend/app/routes/comic.py \
  backend/app/services/comic_story_bridge_service.py \
  backend/tests/test_comic_repository.py \
  backend/tests/test_comic_routes.py \
  backend/tests/test_comic_story_bridge_service.py \
  backend/tests/test_comic_schema.py
git commit -m "feat(hollowforge): persist camila v2 comic lane metadata"
```

## Task 4: Wire V2 resolver into comic render build path

**Files:**
- Modify: `backend/app/services/comic_render_service.py`
- Modify: `backend/app/services/comic_render_dispatch_service.py`
- Modify: `backend/app/services/comic_render_profiles.py` only if a small compatibility shim or explicit boundary assertion is required
- Test: `backend/tests/test_comic_render_service.py`
- Test: `backend/tests/test_comic_render_dispatch_service.py`
- Test: `backend/tests/test_comic_render_v2_integration.py`
- Test: `backend/tests/test_comic_render_profiles.py`

- [ ] **Step 1: Write failing render integration tests**

Add tests for:
- legacy lane continues to use current `character_version`-based prompt assembly
- V2 Camila lane uses resolver contract instead
- V2 render request source snapshot contains:
  - `render_lane`
  - `series_style_id`
  - `character_series_binding_id`
  - the resolver output sections or a serializable summary
- V2 lane uses style-owned checkpoint/LoRA/step/cfg/sampler and role-owned aspect ratio
- V2 lane does not use legacy-only profile ownership fields (`checkpoint_mode`, `workflow_lane_mode`, `lora_mode`) for final model-family selection

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_comic_render_service.py \
  tests/test_comic_render_dispatch_service.py \
  tests/test_comic_render_v2_integration.py \
  tests/test_comic_render_profiles.py
```

Expected: FAIL for V2-specific assertions.

- [ ] **Step 2: Implement V2 branching in render build**

In `comic_render_service.py`:
- load episode lane metadata from panel context
- branch:
  - `legacy` -> existing behavior unchanged
  - `character_canon_v2` -> call V2 resolver
- assemble final positive/negative prompt using resolver output contract
- keep current remote dispatch/callback contract intact

In `comic_render_dispatch_service.py`:
- carry V2 metadata in request snapshot/debug payload only
- do not change worker callback schema unless required for traceability

In `comic_render_profiles.py`:
- either make no behavioral change and add explicit boundary assertions in tests, or
- add only the minimum compatibility shim needed so V2 role profiles remain shot-grammar-only
- do not let this file re-take checkpoint/LoRA family ownership in V2

- [ ] **Step 3: Re-run focused render tests**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add \
  backend/app/services/comic_render_service.py \
  backend/app/services/comic_render_dispatch_service.py \
  backend/app/services/comic_render_profiles.py \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_dispatch_service.py \
  backend/tests/test_comic_render_v2_integration.py \
  backend/tests/test_comic_render_profiles.py
git commit -m "feat(hollowforge): render camila v2 comic lane"
```

## Task 5: Add bounded Camila pilot helpers

**Files:**
- Create: `backend/scripts/launch_camila_v2_comic_pilot.py`
- Create: `backend/scripts/launch_camila_v2_teaser_pilot.py`
- Test: `backend/tests/test_launch_camila_v2_comic_pilot.py`
- Test: `backend/tests/test_launch_camila_v2_teaser_pilot.py`

- [ ] **Step 1: Write failing script-layer tests**

Add tests for:
- comic pilot helper builds/imports a Camila V2 episode with explicit opt-in ids
- helper refuses non-Camila ids
- teaser pilot helper requires a completed selected render from a V2 episode
- comic pilot helper uses `candidate_count=3` for each panel
- teaser pilot helper maps execution from the selected `series_style_id` / `teaser_motion_policy`, not from a hardcoded preset or legacy default
- helpers emit stable output markers:
  - `episode_id`
  - `series_style_id`
  - `character_series_binding_id`
  - `selected_render_asset_storage_path`
  - `animation_job_id` / `animation_shot_id` when applicable

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_launch_camila_v2_comic_pilot.py \
  tests/test_launch_camila_v2_teaser_pilot.py
```

Expected: FAIL because helpers do not exist.

- [ ] **Step 2: Implement bounded pilot helpers**

Comic helper:
- imports/builds one Camila episode in V2 lane
- queues bounded render generation with `candidate_count=3`
- selects outputs
- optionally assembles/exports handoff

Teaser helper:
- reads selected render from V2 pilot episode
- resolves teaser motion policy from the pilot `series style canon`
- maps that policy to the currently executable teaser preset/workflow lane explicitly
- waits for completed mp4

The failing test should vary style canon selection so the helper must prove that teaser execution follows style-owned motion policy.

- [ ] **Step 3: Re-run script-layer tests**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add \
  backend/scripts/launch_camila_v2_comic_pilot.py \
  backend/scripts/launch_camila_v2_teaser_pilot.py \
  backend/tests/test_launch_camila_v2_comic_pilot.py \
  backend/tests/test_launch_camila_v2_teaser_pilot.py
git commit -m "feat(hollowforge): add camila v2 pilot helpers"
```

## Task 6: Run live Camila V2 pilot acceptance

**Files:**
- No code changes required initially
- If acceptance passes, modify:
  - `README.md`
  - `STATE.md`
  - `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 1: Run the full backend verification bundle**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./.venv/bin/python -m pytest -q \
  tests/test_character_canon_v2_registry.py \
  tests/test_series_style_canon_registry.py \
  tests/test_character_series_binding_registry.py \
  tests/test_comic_render_v2_resolver.py \
  tests/test_comic_repository.py \
  tests/test_comic_routes.py \
  tests/test_comic_story_bridge_service.py \
  tests/test_comic_schema.py \
  tests/test_comic_render_service.py \
  tests/test_comic_render_dispatch_service.py \
  tests/test_comic_render_v2_integration.py \
  tests/test_comic_render_profiles.py \
  tests/test_launch_camila_v2_comic_pilot.py \
  tests/test_launch_camila_v2_teaser_pilot.py
```

Expected: PASS.

- [ ] **Step 2: Run live Camila V2 comic pilot**

Run the helper against the local backend and worker.

Expected:
- one V2 episode created
- 4-panel one-shot generated
- panel당 candidate 3개 queued
- selected assets materialized
- handoff export available

- [ ] **Step 3: Inspect outputs directly**

Use direct image/video inspection for:
- same-person read across selected panels
- establish readability
- panel diversity
- teaser same-person read

Apply the rubric from the spec:
- 3/4 selected panels must read as same Camila
- establish must show at least 2 loft cues
- no near-identical portrait set
- no 2+ severe crop/anatomy/poster-glamour collapses

- [ ] **Step 4: If live acceptance fails, stop here**

Do **not** update docs.

Instead:
- capture episode id
- capture selected output paths
- capture failure mode against the rubric
- write the next bounded fix spec

- [ ] **Step 5: If live acceptance passes, update re-entry docs**

Update only the relevant note surfaces:
- `README.md`
- `STATE.md`
- `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

Document:
- Camila V2 pilot lane exists
- it is explicit opt-in
- legacy remains default

- [ ] **Step 6: Run diff hygiene and commit docs**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge
git diff --check
```

Expected: no diff formatting errors.

If docs changed:

```bash
git add README.md STATE.md docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): record camila v2 pilot lane"
```

## Final Verification

- [ ] **Step 1: Re-run focused frontend check only if any frontend file changed**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npx vitest run src/pages/ComicStudio.test.tsx
npm run lint
npm run build
```

Expected: PASS.

- [ ] **Step 2: Record final evidence**

Capture in the task handoff:
- spec path
- plan path
- commits per task
- V2 pilot episode id
- selected panel asset paths
- teaser mp4 path
- whether acceptance passed or failed

## Notes For Implementers

- Do not move all comic generation to V2.
- Do not add a general UI selector in this phase.
- Do not let legacy-only fields like `checkpoint_mode`, `workflow_lane_mode`, or `lora_mode` leak into the V2 `role_block`.
- Interpret `prompt order` in V2 as order *inside* the `role_block`, not permission to reorder the global positive assembly contract.
- Keep changes additive and reversible.
