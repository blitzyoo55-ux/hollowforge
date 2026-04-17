# HollowForge Reference-Guided Comic Still Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Camila V2 establish-only reference-guided still lane that uses IPAdapter-style identity conditioning instead of pure text-to-image prompting.

**Architecture:** Keep the current text-only still lane as the default, then add an opt-in `reference_guided` branch for Camila V2 establish panels. The backend will resolve binding-owned reference assets into the comic render request, the worker will run a still-oriented IPAdapter workflow for those requests, and selection will keep the existing identity/quality gate on top of the new generator path.

**Tech Stack:** Python, FastAPI backend services, Pydantic registries, pytest, ComfyUI worker, SDXL IPAdapter workflow

---

## File Map

- Modify: `backend/app/services/character_series_binding_registry.py`
  - Add binding-owned reference set metadata for the Camila V2 pilot lane.
- Modify: `backend/app/services/comic_render_v2_resolver.py`
  - Resolve whether the current panel should stay on `sdxl_still` or switch to `reference_guided_still`.
- Modify: `backend/app/services/comic_render_service.py`
  - Build reference-guided request payloads while keeping prompt grammar focused on scene/action/composition.
- Modify: `backend/app/services/comic_render_dispatch_service.py`
  - Dispatch reference-guided still payloads to the worker without breaking the existing `comic_panel_still` contract.
- Modify: `backend/tests/test_character_series_binding_registry.py`
  - Cover Camila V2 reference set ownership and binding shape.
- Modify: `backend/tests/test_comic_render_v2_resolver.py`
  - Cover the establish-only branch into the reference-guided execution lane.
- Modify: `backend/tests/test_comic_render_service.py`
  - Verify request payload shape, prompt role changes, and fallback behavior.
- Modify: `backend/tests/test_comic_render_dispatch_service.py`
  - Verify the worker payload includes the new still-generation reference fields.
- Modify: `lab451-animation-worker/app/workflows.py`
  - Add a still-oriented IPAdapter request type and workflow builder.
- Modify: `lab451-animation-worker/app/executors.py`
  - Add a `comic_panel_still` reference-guided execution branch that reuses the worker’s existing IPAdapter-capable path.
- Modify: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`
  - Cover new request parsing, branch selection, and required-node checks.
- Read-only verification: `backend/scripts/launch_camila_v2_comic_pilot.py`
  - Reuse the existing one-panel helper for live acceptance.

### Task 1: Add Camila V2 binding-owned reference set metadata

**Files:**
- Modify: `backend/app/services/character_series_binding_registry.py`
- Test: `backend/tests/test_character_series_binding_registry.py`

- [ ] **Step 1: Write the failing binding test**

Add a focused test asserting the Camila V2 binding exposes a reference set for establish panels, for example:

```python
def test_camila_binding_exposes_establish_reference_set() -> None:
    binding = get_character_series_binding("camila_duarte", "camila_pilot_v1")
    assert binding.reference_sets["establish"]["primary"]
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_character_series_binding_registry.py -k reference_set
```

Expected: FAIL because binding-owned reference metadata does not exist yet.

- [ ] **Step 3: Add minimal reference-set support**

Extend the binding schema with a small, explicit reference set shape:

```python
reference_sets: Mapping[str, Mapping[str, Any]] = Field(default_factory=dict)
```

Populate only the Camila V2 pilot binding with establish references:

```python
"establish": {
    "primary": ["camila_v2_establish_anchor_hero.png"],
    "secondary": ["camila_v2_establish_anchor_halfbody.png"],
}
```

Keep other bindings empty.

- [ ] **Step 4: Re-run the focused binding test**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_character_series_binding_registry.py -k reference_set
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/character_series_binding_registry.py \
  backend/tests/test_character_series_binding_registry.py
git commit -m "feat(hollowforge): add camila v2 binding reference sets"
```

### Task 2: Teach the V2 resolver to opt into the reference-guided establish lane

**Files:**
- Modify: `backend/app/services/comic_render_v2_resolver.py`
- Test: `backend/tests/test_comic_render_v2_resolver.py`

- [ ] **Step 1: Write the failing resolver tests**

Add two explicit tests:

```python
def test_camila_v2_establish_uses_reference_guided_execution() -> None:
    ...

def test_non_establish_roles_keep_existing_execution_lane() -> None:
    ...
```

The first should assert the resolved contract exposes a still-generation mode or backend family that indicates `reference_guided_still` for Camila V2 establish. The second should prove beat/insert/closeup stay on the current lane.

- [ ] **Step 2: Run the focused resolver tests to verify failure**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_v2_resolver.py -k "reference_guided_execution or existing_execution_lane"
```

Expected: FAIL because the resolver only knows the current text-only still lane.

- [ ] **Step 3: Implement the minimal resolver branch**

Update the resolver so that all of the following are true before switching lanes:
- `character_id` is Camila Duarte
- `render_lane` is V2
- `panel_type` is `establish`
- binding has a non-empty establish reference set

When true, set a narrow execution marker, for example:

```python
resolved["still_backend_family"] = "sdxl_ipadapter_still"
resolved["reference_guided"] = True
```

Do not change non-establish roles.

- [ ] **Step 4: Re-run resolver tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q backend/tests/test_comic_render_v2_resolver.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/comic_render_v2_resolver.py \
  backend/tests/test_comic_render_v2_resolver.py
git commit -m "feat(hollowforge): route camila v2 establish to reference-guided lane"
```

### Task 3: Add reference-guided still request payload construction in the backend

**Files:**
- Modify: `backend/app/services/comic_render_service.py`
- Modify: `backend/app/services/comic_render_dispatch_service.py`
- Test: `backend/tests/test_comic_render_service.py`
- Test: `backend/tests/test_comic_render_dispatch_service.py`

- [ ] **Step 1: Write the failing backend tests**

Add focused tests that expect the request payload to include reference-guided fields for Camila V2 establish:

```python
assert payload["still_generation"]["reference_images"] == [...]
assert payload["still_generation"]["backend_family"] == "sdxl_ipadapter_still"
assert payload["still_generation"]["ipadapter_weight"] > 0
```

Add a fallback test proving non-establish roles still emit the old text-only shape.

- [ ] **Step 2: Run the focused backend tests to verify failure**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_dispatch_service.py -k "reference_guided or fallback"
```

Expected: FAIL because the backend does not yet emit reference image fields.

- [ ] **Step 3: Implement minimal request-shape changes**

In `comic_render_service.py`:
- resolve binding reference set for Camila V2 establish
- keep prompt structure but reduce identity-only text emphasis
- add still-generation fields such as:

```python
"backend_family": "sdxl_ipadapter_still",
"reference_images": [...],
"ipadapter_weight": 0.92,
"ipadapter_start_at": 0.0,
"ipadapter_end_at": 1.0,
```

In `comic_render_dispatch_service.py`:
- preserve the existing `target_tool="comic_panel_still"` envelope
- forward the new still-generation fields unchanged

Do not break current text-only requests.

- [ ] **Step 4: Re-run focused backend tests**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_dispatch_service.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/comic_render_service.py \
  backend/app/services/comic_render_dispatch_service.py \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_dispatch_service.py
git commit -m "feat(hollowforge): emit reference-guided comic still payloads"
```

### Task 4: Add a still-oriented IPAdapter execution branch in the worker

**Files:**
- Modify: `lab451-animation-worker/app/workflows.py`
- Modify: `lab451-animation-worker/app/executors.py`
- Test: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`

- [ ] **Step 1: Write the failing worker tests**

Add worker tests that expect a comic still job with `backend_family="sdxl_ipadapter_still"` to:
- parse the reference-guided payload
- require IPAdapter nodes
- execute a still image workflow instead of the current micro-anim MP4 path

Example:

```python
def test_comic_panel_still_reference_guided_uses_ipadapter_still_branch() -> None:
    ...
```

- [ ] **Step 2: Run the focused worker tests to verify failure**

Run:

```bash
../backend/.venv/bin/python -m pytest -q lab451-animation-worker/tests/test_comic_panel_still_worker.py -k reference_guided
```

Expected: FAIL because the worker only supports text-only still or IPAdapter animation.

- [ ] **Step 3: Implement the minimal worker branch**

In `workflows.py`:
- add a new request type or extend `SDXLIPAdapterRequest` for still use
- add a `build_sdxl_ipadapter_still_workflow(...)` that ends with `SaveImage`

In `executors.py`:
- for `target_tool="comic_panel_still"` and `backend_family="sdxl_ipadapter_still"`
  - download and upload the reference image
  - resolve IPAdapter and CLIP vision assets
  - submit the still-oriented IPAdapter workflow
  - wait for a single image asset
  - return a PNG `output_url`

Do not change teaser animation execution.

- [ ] **Step 4: Re-run focused worker coverage**

Run:

```bash
../backend/.venv/bin/python -m pytest -q lab451-animation-worker/tests/test_comic_panel_still_worker.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lab451-animation-worker/app/workflows.py \
  lab451-animation-worker/app/executors.py \
  lab451-animation-worker/tests/test_comic_panel_still_worker.py
git commit -m "feat(hollowforge): add reference-guided comic still worker branch"
```

### Task 5: Run focused regression and live Camila establish acceptance

**Files:**
- Read-only verification: `backend/scripts/launch_camila_v2_comic_pilot.py`
- Read-only verification: `backend/app/services/comic_render_service.py`
- Optional modify: `backend/scripts/launch_camila_v2_comic_pilot.py`

- [ ] **Step 1: Fix the helper default if it still mismatches the route contract**

If `DEFAULT_CANDIDATE_COUNT` is still `1`, change it to `2` first and add a tiny regression test. Keep this bounded to helper correctness.

- [ ] **Step 2: Run the focused regression bundle**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python -m pytest -q \
  backend/tests/test_character_series_binding_registry.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_dispatch_service.py \
  lab451-animation-worker/tests/test_comic_panel_still_worker.py
```

Expected: PASS.

- [ ] **Step 3: Restart or confirm the live worktree runtime**

Reuse the `8011` backend and `8611` worker if they already have the new code loaded. Restart only if needed.

- [ ] **Step 4: Run a fresh one-panel Camila establish acceptance**

Run:

```bash
PYTHONPATH=backend ./.venv/bin/python backend/scripts/launch_camila_v2_comic_pilot.py \
  --base-url http://127.0.0.1:8011 \
  --panel-multiplier 1 \
  --candidate-count 2 \
  --render-poll-attempts 240 \
  --render-poll-sec 1.0
```

Expected:
- at least one materialized establish candidate clears the identity gate
- or failure becomes clearly attributable to reference assets rather than prompt-only drift

- [ ] **Step 5: Review the resulting image directly before declaring success**

Check:
- same-person hold as Camila
- room-first establish readability
- reduced HUD / subtitle / random text artifacts
- reduced youth / school-uniform drift

If these do not improve, stop and record the output paths and failure mode. Do not update docs yet.

- [ ] **Step 6: Commit only if tests are green and live acceptance shows a real improvement**

```bash
git add backend/app/services/character_series_binding_registry.py \
  backend/app/services/comic_render_v2_resolver.py \
  backend/app/services/comic_render_service.py \
  backend/app/services/comic_render_dispatch_service.py \
  backend/tests/test_character_series_binding_registry.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_dispatch_service.py \
  lab451-animation-worker/app/workflows.py \
  lab451-animation-worker/app/executors.py \
  lab451-animation-worker/tests/test_comic_panel_still_worker.py
git commit -m "feat(hollowforge): add reference-guided camila establish lane"
```

### Task 6: Update docs only if live acceptance shows a meaningful gain

**Files:**
- Modify: `README.md`
- Modify: `STATE.md`
- Modify: `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 1: Confirm the acceptance evidence is worth documenting**

Require all of the following:
- same-person hold improved
- at least one establish candidate passed the identity gate
- output looks materially better than the current text-only lane

- [ ] **Step 2: Update operator-facing docs narrowly**

Document:
- Camila V2 establish now uses reference-guided still generation
- beat/insert/closeup remain on the current lane
- rollout is opt-in and fallback still exists

- [ ] **Step 3: Re-run doc hygiene**

Run:

```bash
git diff --check
```

Expected: no whitespace or merge-marker issues.

- [ ] **Step 4: Commit docs**

```bash
git add README.md STATE.md docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): document reference-guided camila establish lane"
```

## Notes for Implementers

- Do not delete or replace the existing text-only still lane.
- Do not broaden rollout beyond `Camila V2 establish`.
- Keep prompt structure readable and role-driven; do not move back to unstructured keyword dumps.
- If live output still fails, prefer diagnosing reference asset quality and worker workflow details before proposing more checkpoint swaps.
