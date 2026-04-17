# HollowForge Establish-Only Style Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an establish-only execution override for the Camila V2 style canon so establish panels use a different checkpoint while beat, insert, and closeup keep the current favorite-quality stack.

**Architecture:** Keep series style canon as the owner of checkpoint and LoRA execution policy, then teach the V2 resolver to merge optional role-specific execution overrides on top of the base style execution. Limit the first rollout to `camila_pilot_v1` establish panels only, validate it with focused resolver/integration tests, then rerun a live one-panel Camila establish acceptance pass.

**Tech Stack:** Python, FastAPI backend services, Pydantic registries, pytest, ComfyUI-backed animation worker scripts

---

## File Map

- Modify: `backend/app/services/series_style_canon_registry.py`
  - Extend `SeriesStyleCanonEntry` so a style canon can declare optional role-specific execution overrides.
- Modify: `backend/app/services/comic_render_v2_resolver.py`
  - Merge establish-only execution overrides into the resolved execution params without changing non-establish roles.
- Modify: `backend/tests/test_comic_render_v2_resolver.py`
  - Cover role override merge precedence and non-establish stability.
- Modify: `backend/tests/test_comic_render_v2_integration.py`
  - Verify the V2 lane sends the establish override checkpoint into generation payloads while other roles stay on the base stack.
- Modify: `backend/tests/test_comic_render_service.py`
  - Add a narrow regression if needed to prove establish prompt assembly still uses the same scoring and selection path after execution override merge.
- Read-only verification: `backend/scripts/launch_camila_v2_comic_pilot.py`
  - Reuse the existing one-panel Camila pilot helper for live acceptance after tests pass.

### Task 1: Add role-aware execution fields to the series style canon

**Files:**
- Modify: `backend/app/services/series_style_canon_registry.py`
- Test: `backend/tests/test_comic_render_v2_resolver.py`

- [ ] **Step 1: Write the failing test for role override data**

Add a focused test that expects `camila_pilot_v1` to expose an `establish` execution override and `camila_motion_test_v1` to remain valid without one.

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_v2_resolver.py -k role_override
```

Expected: FAIL because `SeriesStyleCanonEntry` does not yet model role-specific execution overrides.

- [ ] **Step 3: Extend the style canon schema minimally**

Update `SeriesStyleCanonEntry` to support an optional role override map. Keep the schema small:

```python
role_execution_overrides: Mapping[str, Mapping[str, Any]] = Field(default_factory=dict)
```

Add the first override only to `camila_pilot_v1`:

```python
"establish": {
    "checkpoint": "akiumLumenILLBase_baseV2.safetensors",
    "loras": (),
}
```

Keep all other execution knobs inherited from the base style unless the override explicitly sets them.

- [ ] **Step 4: Re-run the focused test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_v2_resolver.py -k role_override
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/series_style_canon_registry.py backend/tests/test_comic_render_v2_resolver.py
git commit -m "feat(hollowforge): add establish execution override to style canon"
```

### Task 2: Merge establish execution overrides in the V2 resolver

**Files:**
- Modify: `backend/app/services/comic_render_v2_resolver.py`
- Test: `backend/tests/test_comic_render_v2_resolver.py`

- [ ] **Step 1: Write the failing resolver tests**

Add two explicit tests:

```python
def test_establish_role_uses_style_execution_override() -> None:
    ...

def test_non_establish_roles_keep_base_style_execution() -> None:
    ...
```

The first should assert that `panel_type="establish"` resolves to `akiumLumenILLBase_baseV2.safetensors` with no LoRAs. The second should assert that `beat` keeps `prefectIllustriousXL_v70.safetensors` and the favorite-quality LoRAs.

- [ ] **Step 2: Run the focused resolver tests to verify failure**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_v2_resolver.py -k "establish_role_uses_style_execution_override or non_establish_roles_keep_base_style_execution"
```

Expected: FAIL because the resolver only reads base style execution.

- [ ] **Step 3: Implement the minimal merge logic**

In `comic_render_v2_resolver.py`:
- add a helper that deep-copies base execution
- if `panel_type` has a role override in the style canon, merge only the override keys into that copy
- keep precedence order explicit:
  1. style base execution
  2. style role override
  3. binding lock strengths
  4. role-owned width/height/framing

Do not move ownership of execution policy out of the style canon.

- [ ] **Step 4: Re-run resolver tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_v2_resolver.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/comic_render_v2_resolver.py backend/tests/test_comic_render_v2_resolver.py
git commit -m "feat(hollowforge): merge establish style overrides in v2 resolver"
```

### Task 3: Verify the V2 lane uses the establish override in generation payloads

**Files:**
- Modify: `backend/tests/test_comic_render_v2_integration.py`
- Optional modify: `backend/tests/test_comic_render_service.py`

- [ ] **Step 1: Write the failing integration test**

Add a narrow integration test that creates a V2 establish panel fixture and asserts the queued generation payload uses:

```python
assert payload["checkpoint"] == "akiumLumenILLBase_baseV2.safetensors"
assert payload["loras"] == []
```

Also keep an explicit beat-panel assertion proving the favorite stack remains intact.

- [ ] **Step 2: Run the focused integration test to verify failure**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_v2_integration.py -k "establish_override or beat_panel_keeps_base_style"
```

Expected: FAIL because establish payloads still use the base favorite stack.

- [ ] **Step 3: Adjust any fixture or assertion glue only as needed**

If the resolver merge already makes the integration test pass, keep this step empty except for small fixture adjustments. Do not broaden the implementation scope.

- [ ] **Step 4: Re-run focused integration coverage**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_v2_integration.py backend/tests/test_comic_render_v2_resolver.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_comic_render_v2_integration.py backend/tests/test_comic_render_v2_resolver.py
git commit -m "test(hollowforge): cover establish style split in v2 lane"
```

### Task 4: Run focused regression and live acceptance

**Files:**
- Read-only verification: `backend/scripts/launch_camila_v2_comic_pilot.py`
- Read-only verification: `backend/app/services/comic_render_service.py`

- [ ] **Step 1: Run the focused backend regression bundle**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_integration.py \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_character_canon_v2_registry.py
```

Expected: PASS.

- [ ] **Step 2: Restart or confirm the live Camila V2 backend lane**

Reuse the existing worktree runtime on `8011` and worker on `8611`. Only restart processes if the new code is not loaded.

- [ ] **Step 3: Run a fresh one-panel Camila establish acceptance**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python backend/scripts/launch_camila_v2_comic_pilot.py \
  --base-url http://127.0.0.1:8011 \
  --panel-multiplier 1 \
  --render-poll-attempts 240 \
  --render-poll-sec 1.0
```

Expected:
- either a selected establish asset is produced using the establish-only checkpoint
- or bad candidates are rejected, but with evidence that the new checkpoint was used

- [ ] **Step 4: Directly review the selected or rejected establish outputs**

Check:
- same-person hold versus Camila V2
- reduced schoolgirl/classroom drift
- reduced portrait/glamour pull
- reduced HUD or lower-third text artifacts

If the live output still fails identity or readability, stop here and record the exact output paths and failure mode. Do not update docs yet.

- [ ] **Step 5: Commit only if code and tests are green**

```bash
git add backend/app/services/series_style_canon_registry.py \
  backend/app/services/comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_integration.py
git commit -m "feat(hollowforge): split establish execution for camila v2"
```

### Task 5: Update docs only if live acceptance shows a real improvement

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 1: Confirm live acceptance evidence is worth documenting**

Require at least:
- proof that establish panels used the new checkpoint
- proof that non-establish roles still use the favorite stack
- direct image review notes showing the split helped

- [ ] **Step 2: Document the new establish-only split briefly**

Update docs with:
- establish-only style split intent
- checkpoint ownership staying under series style canon
- current status as an in-progress quality pass, not a final stable default

- [ ] **Step 3: Run doc hygiene check**

Run:

```bash
git diff --check
```

Expected: no whitespace or conflict issues.

- [ ] **Step 4: Commit docs**

```bash
git add README.md STATE.md docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): record establish-only style split status"
```

## Acceptance Summary

This plan is complete when all of the following are true:
- `camila_pilot_v1` can declare an establish-only execution override
- the V2 resolver applies that override only to `establish`
- `beat / insert / closeup` continue to resolve to the current favorite-quality stack
- focused regressions pass
- a live Camila one-panel establish run provides direct evidence that the new establish checkpoint is in use
- docs are updated only if the live output meaningfully improves
