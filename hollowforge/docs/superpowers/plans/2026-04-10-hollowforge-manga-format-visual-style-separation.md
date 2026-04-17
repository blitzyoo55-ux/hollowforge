# HollowForge Manga Format / Visual Style Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate `manga format` from `visual style` in the Camila V2 establish lane, roll back the failed reference-guided establish generator, and restore a cleaner text-only establish contract that can be tuned without conflating layout semantics with art style.

**Architecture:** Treat `manga` as page/layout/reading metadata, not as a style shortcut in the image-generation prompt. Remove direct `manga panel` style signaling from establish generation, keep format cues as composition hints, and revert establish execution to a bounded text-only lane while leaving identity scoring and overlay rejection in place.

**Tech Stack:** Python, FastAPI backend services, Pydantic registries, pytest, ComfyUI worker, SDXL still workflows

---

## File Map

- Modify: `backend/app/services/comic_render_service.py`
  - Rework establish prompt assembly so format cues are composition-only and remove direct `manga style/panel` art-style phrasing.
- Modify: `backend/app/services/comic_render_v2_resolver.py`
  - Keep V2 contract ownership clean: character identity, visual style, binding, and format cues stay separate.
- Modify: `backend/app/services/series_style_canon_registry.py`
  - Remove or disable the current establish-only reference-guided override for the Camila pilot style.
- Modify: `backend/app/services/character_series_binding_registry.py`
  - Keep reference ownership intact for future use, but ensure the establish lane no longer depends on it for generation.
- Modify: `backend/tests/test_comic_render_service.py`
  - Cover prompt wording changes, rollback behavior, and selection metadata continuity.
- Modify: `backend/tests/test_comic_render_v2_resolver.py`
  - Cover contract separation between format cues and visual style, plus rollback to text-only establish execution.
- Modify: `backend/tests/test_series_style_canon_registry.py`
  - Cover the updated establish execution policy for the Camila pilot style canon.
- Modify: `backend/tests/test_comic_render_v2_integration.py`
  - Verify the establish lane emits the expected text-only execution payload after rollback.
- Optional modify: `backend/scripts/launch_camila_v2_comic_pilot.py`
  - Only if needed to improve live acceptance observability after rollback; avoid widening scope.
- Conditional docs update only after live acceptance improves:
  - `README.md`
  - `STATE.md`
  - `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

## Task 1: Add failing tests for format/style separation and establish rollback

**Files:**
- Modify: `backend/tests/test_comic_render_service.py`
- Modify: `backend/tests/test_comic_render_v2_resolver.py`
- Modify: `backend/tests/test_series_style_canon_registry.py`
- Modify: `backend/tests/test_comic_render_v2_integration.py`

- [ ] **Step 1: Write failing tests for prompt ownership**

Add focused assertions that the establish prompt contract uses composition language rather than direct art-style `manga` shorthand. Example expectations:

```python
assert "manga style" not in prompt.lower()
assert "japanese manga style" not in prompt.lower()
assert "wide room view" in prompt
assert "leave negative space for dialogue" in prompt
```

- [ ] **Step 2: Write failing tests for establish execution rollback**

Add tests proving:

```python
assert contract.execution_params.get("reference_guided") is not True
assert "still_backend_family" not in contract.execution_params
assert contract.execution_params["checkpoint"] == "akiumLumenILLBase_baseV2.safetensors"
```

for the bounded establish fallback lane.

- [ ] **Step 3: Run the focused failing bundle**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_series_style_canon_registry.py \
  backend/tests/test_comic_render_v2_integration.py -k "establish or format or manga"
```

Expected: FAIL because the current code still mixes format/style semantics and still routes establish through the experimental reference-guided lane.

- [ ] **Step 4: Keep the failures narrow**

If unrelated tests fail, trim the new assertions until the bundle isolates only the intended regression surface.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_series_style_canon_registry.py \
  backend/tests/test_comic_render_v2_integration.py
git commit -m "test(hollowforge): lock format-style separation contract"
```

## Task 2: Roll back the failed reference-guided establish generator

**Files:**
- Modify: `backend/app/services/series_style_canon_registry.py`
- Modify: `backend/app/services/comic_render_v2_resolver.py`
- Modify: `backend/app/services/character_series_binding_registry.py`

- [ ] **Step 1: Remove establish generator dependency on reference guidance**

Adjust the Camila pilot style canon so establish no longer opts into:

```python
"reference_guided": True
"still_backend_family": "sdxl_ipadapter_still"
```

Keep the establish-specific checkpoint override if it remains useful, but revert the generator contract to text-only still execution.

- [ ] **Step 2: Preserve reference ownership without consuming it**

Do not delete the binding-owned reference set. Keep it in `character_series_binding_registry.py` for future generator experiments, but ensure rollback means:

```python
binding.reference_sets
```

is not consumed by the active establish generation path.

- [ ] **Step 3: Re-run the focused rollback tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q \
  backend/tests/test_series_style_canon_registry.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_integration.py
```

Expected: PASS.

- [ ] **Step 4: Keep fallback ownership explicit**

Make sure the resolver still expresses:
- character owns identity
- style owns checkpoint/LoRA tone
- binding owns identity-preserving metadata
- format is not encoded as style

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/series_style_canon_registry.py \
  backend/app/services/comic_render_v2_resolver.py \
  backend/app/services/character_series_binding_registry.py \
  backend/tests/test_series_style_canon_registry.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_integration.py
git commit -m "fix(hollowforge): roll back failed reference-guided establish lane"
```

## Task 3: Separate format cues from visual style in establish prompt assembly

**Files:**
- Modify: `backend/app/services/comic_render_service.py`
- Modify: `backend/tests/test_comic_render_service.py`

- [ ] **Step 1: Introduce explicit format-cue language**

Refactor establish prompt assembly so format intent becomes composition-only language such as:

```python
"wide room view"
"single adult subject"
"subject secondary to environment"
"props readable"
"leave negative space for dialogue"
```

Avoid direct style phrases like:

```python
"manga style"
"anime manga panel"
"japanese manga style"
```

- [ ] **Step 2: Keep visual attractiveness in style/binding**

Do not let the establish prompt lose adult appeal. Keep attraction signals in `style canon` and `binding` only, not in format cues.

- [ ] **Step 3: Re-run focused service tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_service.py
```

Expected: PASS.

- [ ] **Step 4: Verify remote payload shape stays stable**

Confirm the remote payload still uses:

```python
backend_family == "sdxl_still"
```

for establish after rollback, and that no stale `reference_images` fields leak into the active path.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/comic_render_service.py \
  backend/tests/test_comic_render_service.py
git commit -m "feat(hollowforge): separate establish format cues from style prompts"
```

## Task 4: Run regression and live establish acceptance

**Files:**
- Read-only verification: `backend/scripts/launch_camila_v2_comic_pilot.py`
- Read-only verification: `data/outputs/*`

- [ ] **Step 1: Run the backend regression bundle**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q \
  backend/tests/test_character_canon_v2_registry.py \
  backend/tests/test_character_series_binding_registry.py \
  backend/tests/test_series_style_canon_registry.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_integration.py \
  backend/tests/test_comic_render_service.py
```

Expected: PASS.

- [ ] **Step 2: Restart the `8011/8611` bounded live lane if needed**

Reuse:

```bash
HOLLOWFORGE_BACKEND_PORT=8011 HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL=http://127.0.0.1:8611 HOLLOWFORGE_PUBLIC_API_BASE_URL=http://127.0.0.1:8011 ./run_local_backend.sh
WORKER_PORT=8611 WORKER_PUBLIC_BASE_URL=http://127.0.0.1:8611 ./run_local_animation_worker.sh
```

Only restart if the new rollback code is not already loaded.

- [ ] **Step 3: Run a fresh one-panel Camila establish acceptance**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python backend/scripts/launch_camila_v2_comic_pilot.py \
  --base-url http://127.0.0.1:8011
```

Expected:
- candidate generation completes
- obviously broken reference-guided artifacts do not appear because the lane is rolled back
- any remaining failure is attributable to text-only establish quality, not the abandoned IPAdapter lane

- [ ] **Step 4: Review the resulting candidate images directly**

Check:
- same-person hold
- room-first readability
- absence of `REC/viewfinder/random text` overlays
- adult attractiveness without school/uniform drift

If output is still poor, record exact output paths and failure type. Do not update docs yet.

- [ ] **Step 5: Commit only when tests are green and the rollback behavior is verified**

```bash
git add backend/app/services/series_style_canon_registry.py \
  backend/app/services/comic_render_v2_resolver.py \
  backend/app/services/comic_render_service.py \
  backend/tests/test_series_style_canon_registry.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_integration.py \
  backend/tests/test_comic_render_service.py
git commit -m "fix(hollowforge): separate manga format from establish style lane"
```

## Task 5: Update docs only if the rollback materially improves establish quality

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 1: Confirm acceptance is document-worthy**

Only proceed if live establish output is actually better than the failed reference-guided lane.

- [ ] **Step 2: Update operator guidance**

Document:
- `manga format` now means layout/reading metadata
- `visual style` owns appearance
- current establish lane is text-only fallback
- abandoned reference-guided establish lane remains non-stable

- [ ] **Step 3: Run a doc sanity check**

Run:

```bash
git diff --check
```

Expected: clean.

- [ ] **Step 4: Commit docs**

```bash
git add README.md STATE.md docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): document format-style separation"
```

- [ ] **Step 5: Stop if acceptance does not improve**

If establish quality is still not acceptable, skip doc changes and surface the next generator experiment instead of documenting a weak state.
