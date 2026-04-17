# HollowForge Camila V2 Still Quality Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen the Camila-only `character_canon_v2` still lane so the same character holds across panels, panel roles read differently, and AI artifacts are reduced enough to qualify as a comic-grade pilot baseline.

**Architecture:** Keep the existing V2 layering contract intact and improve quality by enriching the V2 registries, the resolver’s composed quality policy, and the panel-role readability rules rather than widening scope or replacing the legacy lane. Preserve the existing bounded helper defaults, then use explicit helper overrides for a four-panel still acceptance run and a same-render teaser identity verification run.

**Tech Stack:** FastAPI backend services, Pydantic v2 registries, existing comic render profile system, pytest, existing remote still render pipeline, existing bounded Camila V2 pilot helpers.

---

## File Map

### Existing files to modify

- `backend/app/services/character_canon_v2_registry.py`
  - enrich Camila V2 identity fields so the canon is neutral but specific enough to prevent face and surface drift
- `backend/app/services/series_style_canon_registry.py`
  - add still-quality policy fields for line, shading, texture, readability, and anti-artifact guidance
- `backend/app/services/character_series_binding_registry.py`
  - add binding-level identity locks, wardrobe family, and binding negatives for the Camila pilot
- `backend/app/services/comic_render_v2_resolver.py`
  - materialize the richer V2 fields into the positive/negative contract and execution params without changing ownership boundaries
- `backend/app/services/comic_render_profiles.py`
  - add role-level `quality_selector_hints` or equivalent readability hints while keeping checkpoint ownership out of profiles
- `backend/app/services/comic_render_service.py`
  - integrate the richer V2 quality inputs into prompt/negative assembly and any candidate selection heuristics used by the still lane
- `backend/scripts/launch_camila_v2_comic_pilot.py`
  - keep bounded defaults, but ensure explicit override flags can run a four-panel acceptance pass without changing the default lane
- `backend/scripts/launch_camila_v2_teaser_pilot.py`
  - preserve the explicit selected-render verification path used after still acceptance
- `backend/tests/test_character_canon_v2_registry.py`
- `backend/tests/test_series_style_canon_registry.py`
- `backend/tests/test_character_series_binding_registry.py`
- `backend/tests/test_comic_render_v2_resolver.py`
- `backend/tests/test_comic_render_v2_integration.py`
- `backend/tests/test_comic_render_profiles.py`
- `backend/tests/test_comic_render_service.py`
- `backend/tests/test_launch_camila_v2_comic_pilot.py`
- `backend/tests/test_launch_camila_v2_teaser_pilot.py`
- `README.md`
- `STATE.md`
- `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

### Runtime note

- This worktree does not rely on a local `.venv` under its own `backend/`.
- Use the stable repo interpreter explicitly for tests:
  - `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python`

## Scope Guardrails

- Keep `character_canon_v2` Camila-only.
- Do not replace the legacy comic lane.
- Do not add new frontend UX in this phase.
- Do not start a full model/LoRA benchmark sweep.
- Do not make teaser a separate style-tuning project; only verify same-person hold after still acceptance.
- Do not update README/STATE/SOP unless the live still acceptance passes.

## Task 1: Enrich the V2 registries with quality-control fields

**Files:**
- Modify: `backend/app/services/character_canon_v2_registry.py`
- Modify: `backend/app/services/series_style_canon_registry.py`
- Modify: `backend/app/services/character_series_binding_registry.py`
- Test: `backend/tests/test_character_canon_v2_registry.py`
- Test: `backend/tests/test_series_style_canon_registry.py`
- Test: `backend/tests/test_character_series_binding_registry.py`

- [ ] **Step 1: Extend the failing registry tests**

Add expectations for:
- Camila V2 canon exposing specific identity fields:
  - `face_structure_notes`
  - `eye_signature`
  - `hair_signature`
  - `skin_surface_policy`
  - `body_signature`
  - `expression_range`
  - `identity_negative_rules`
- Camila V2 identity staying style-neutral:
  - no `glamour`
  - no `editorial`
  - no `resort`
- pilot series style canon exposing still-quality policy fields:
  - `line_policy`
  - `shading_policy`
  - `surface_texture_policy`
  - `panel_readability_policy`
  - `artifact_avoidance_policy`
  - `hand_face_reliability_policy`
- pilot binding exposing quality-control fields:
  - `identity_lock_strength`
  - `hair_lock_strength`
  - `face_lock_strength`
  - `allowed_wardrobe_family`
  - `binding_negative_rules`
  - `do_not_mutate`

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_character_canon_v2_registry.py \
  tests/test_series_style_canon_registry.py \
  tests/test_character_series_binding_registry.py
```

Expected: FAIL because the new fields do not exist yet.

- [ ] **Step 2: Implement the registry enrichments**

Add the minimal new Pydantic fields and seed values.

Implementation rules:
- keep Camila identity neutral, specific, and anti-drift
- keep style canon responsible for quality policy, not role grammar
- keep binding responsible for style-safe identity retention, not checkpoint ownership

- [ ] **Step 3: Re-run the registry tests**

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
git commit -m "feat(hollowforge): enrich camila v2 quality registries"
```

## Task 2: Materialize the richer quality contract in the V2 resolver

**Files:**
- Modify: `backend/app/services/comic_render_v2_resolver.py`
- Test: `backend/tests/test_comic_render_v2_resolver.py`
- Test: `backend/tests/test_comic_render_v2_integration.py`

- [ ] **Step 1: Extend resolver tests to cover the new quality contract**

Add tests for:
- `identity_block` containing the new identity-specific entries
- `style_block` containing still-quality policy fragments
- `binding_block` containing identity lock and wardrobe constraints
- `negative_rules` accumulating:
  - style artifact avoidance
  - identity anti-drift
  - binding negatives
  - role negatives
- `execution_params` keeping the same ownership boundaries:
  - checkpoint/LoRA/steps/cfg/sampler from style
  - lock strengths from binding
  - width/height/framing from role profile

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_comic_render_v2_resolver.py \
  tests/test_comic_render_v2_integration.py
```

Expected: FAIL because the resolver still materializes only the thin V2 contract.

- [ ] **Step 2: Implement the richer resolver**

Update the resolver so it:
- lifts the new registry fields into the materialized V2 contract
- keeps positive merge order unchanged:
  - role
  - identity
  - style
  - binding
  - continuity/location
- keeps negative accumulation order unchanged
- exposes enough structured segments for downstream prompt assembly

- [ ] **Step 3: Re-run the resolver tests**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add \
  backend/app/services/comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_integration.py
git commit -m "feat(hollowforge): enrich camila v2 render contract"
```

## Task 3: Make panel-role quality rules selection-aware

**Files:**
- Modify: `backend/app/services/comic_render_profiles.py`
- Modify: `backend/app/services/comic_render_service.py`
- Test: `backend/tests/test_comic_render_profiles.py`
- Test: `backend/tests/test_comic_render_service.py`

- [ ] **Step 1: Add failing tests for quality-aware role hints**

Add tests covering:
- role profiles exposing `quality_selector_hints` or equivalent stable fields
- `establish` prioritizing room readability and reduced subject occupancy
- `beat` prioritizing expression readability and natural body pose
- `insert` prioritizing prop/action readability
- `closeup` prioritizing emotion clarity and artifact suppression
- role negatives penalizing glamour-poster failure patterns

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_comic_render_profiles.py \
  tests/test_comic_render_service.py
```

Expected: FAIL because the quality hints and stronger role rules do not exist yet.

- [ ] **Step 2: Implement the profile and render-service changes**

Update:
- `comic_render_profiles.py` to encode quality-selector hints per role
- `comic_render_service.py` to use the richer V2 contract and role hints when composing prompt/negative text and selecting/assessing candidates

Rules:
- do not move checkpoint/LoRA ownership into profiles
- do not make selection a beauty-first heuristic
- do penalize:
  - waxy skin
  - dead eyes
  - malformed hands
  - floating props
  - empty establish rooms
  - portrait pull on non-closeup roles

- [ ] **Step 3: Re-run the profile/service tests**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add \
  backend/app/services/comic_render_profiles.py \
  backend/app/services/comic_render_service.py \
  backend/tests/test_comic_render_profiles.py \
  backend/tests/test_comic_render_service.py
git commit -m "feat(hollowforge): add camila v2 still quality rules"
```

## Task 4: Harden the bounded pilot helpers for still-quality acceptance

**Files:**
- Modify: `backend/scripts/launch_camila_v2_comic_pilot.py`
- Modify: `backend/scripts/launch_camila_v2_teaser_pilot.py`
- Test: `backend/tests/test_launch_camila_v2_comic_pilot.py`
- Test: `backend/tests/test_launch_camila_v2_teaser_pilot.py`

- [ ] **Step 1: Extend the helper tests for quality-pass overrides**

Add tests ensuring:
- comic helper keeps bounded defaults:
  - `candidate_count=1`
  - `execution_mode=remote_worker`
  - `panel_limit=1`
- explicit CLI overrides can run a four-panel quality pass without changing defaults
- teaser helper still accepts explicit selected-render context and does not regress the same-person verification path

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_launch_camila_v2_comic_pilot.py \
  tests/test_launch_camila_v2_teaser_pilot.py
```

Expected: FAIL if override coverage or helper output markers are insufficient.

- [ ] **Step 2: Implement the helper adjustments**

If needed:
- expose/normalize override flags for a four-panel still pass
- keep the default bounded lane unchanged
- preserve explicit selected-render outputs for downstream teaser verification

- [ ] **Step 3: Re-run the helper tests**

Run the same pytest command.

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add \
  backend/scripts/launch_camila_v2_comic_pilot.py \
  backend/scripts/launch_camila_v2_teaser_pilot.py \
  backend/tests/test_launch_camila_v2_comic_pilot.py \
  backend/tests/test_launch_camila_v2_teaser_pilot.py
git commit -m "fix(hollowforge): harden camila v2 quality acceptance helpers"
```

## Task 5: Run live still acceptance and gated teaser verification

**Files:**
- Modify only if acceptance passes:
  - `README.md`
  - `STATE.md`
  - `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 1: Run the focused backend regression bundle**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_character_canon_v2_registry.py \
  tests/test_series_style_canon_registry.py \
  tests/test_character_series_binding_registry.py \
  tests/test_comic_render_v2_resolver.py \
  tests/test_comic_render_v2_integration.py \
  tests/test_comic_render_profiles.py \
  tests/test_comic_render_service.py \
  tests/test_launch_camila_v2_comic_pilot.py \
  tests/test_launch_camila_v2_teaser_pilot.py
```

Expected: PASS.

- [ ] **Step 2: Run the four-panel still acceptance**

Use the bounded helper with explicit overrides:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python \
  scripts/launch_camila_v2_comic_pilot.py \
  --base-url http://127.0.0.1:8011 \
  --panel-limit 4 \
  --candidate-count 2 \
  --render-poll-attempts 420
```

Expected:
- helper returns `overall_success: true`
- explicit selected-render markers are printed
- operator can manually inspect the resulting four panels for:
  - same-person hold
  - role diversity
  - establish room readability
  - reduced AI artifact severity

- [ ] **Step 3: Only if still acceptance passes, run teaser identity verification**

Use the selected render context from the still acceptance output:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python \
  scripts/launch_camila_v2_teaser_pilot.py \
  --base-url http://127.0.0.1:8011 \
  --episode-id <episode_id> \
  --selected-scene-panel-id <panel_id> \
  --selected-render-asset-id <asset_id> \
  --selected-render-generation-id <generation_id> \
  --selected-render-asset-storage-path <storage_path> \
  --timeout-sec 1800
```

Expected:
- `overall_success: true`
- a completed animation job
- a reachable mp4 served by the worker runtime
- same-person hold confirmed against the selected still

- [ ] **Step 4: If live acceptance passes, update runtime docs**

Update:
- `README.md`
- `STATE.md`
- `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

Document:
- the accepted quality-pass commands
- the latest validated episode/job ids
- any acceptance-specific helper overrides that are now canonical

- [ ] **Step 5: Re-run doc sanity and commit**

Run:

```bash
git diff --check
```

Expected: PASS.

Then:

```bash
git add \
  README.md \
  STATE.md \
  docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): record camila v2 still quality pass"
```

## Final Verification Gate

- [ ] **Step 1: Confirm working tree is clean except runtime artifacts**

Run:

```bash
git status --short
```

Expected:
- only untracked `data/` runtime artifacts remain
- no unintended tracked changes are left behind

- [ ] **Step 2: Summarize acceptance against the spec**

Report explicitly:
- whether the same Camila holds across the accepted stills
- whether establish/beat/insert/closeup read differently
- whether AI artifact severity is reduced
- whether teaser preserved same-person hold
- whether the V2 lane is ready for stable promotion or needs one more bounded pass
