# HollowForge Local Manga Still Stack Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the local Mac mini manga/anime still stack by adding face-specific IPAdapter support, a two-stage face-repair lane, and a narrow checkpoint expansion path centered on NoobAI-XL.

**Architecture:** Keep the existing SDXL / Illustrious still path as the base generation layer, then add a separate low-denoise repair workflow that uses face-specific IPAdapter assets against a source still. Backend still generation stays role-aware, but worker execution gains explicit adapter-profile and repair-lane support so we can benchmark `prefect`, `hassaku`, and `NoobAI-XL` without replacing the current stack.

**Tech Stack:** Python, FastAPI backend services, ComfyUI worker, sqlite3, JSON/env config, pytest

---

## File Map

- Modify: `backend/scripts/check_local_animation_preflight.py`
  - Validate new face-specific IPAdapter assets and the optional NoobAI checkpoint.
- Modify: `backend/app/config.py`
  - Expose backend-level config for the preferred repair adapter profile and optional benchmark checkpoint.
- Modify: `backend/app/services/comic_render_service.py`
  - Emit explicit worker payload fields for adapter profile selection and optional repair generation metadata.
- Modify: `backend/app/services/comic_render_v2_resolver.py`
  - Add a narrow benchmark-friendly checkpoint family hook without replacing the active production defaults.
- Modify: `backend/scripts/launch_camila_v2_comic_pilot.py`
  - Add flags to run base-only vs base-plus-repair still probes and to override the benchmark checkpoint.
- Modify: `backend/tests/test_comic_render_service.py`
  - Cover worker payload generation for face adapter selection and repair metadata.
- Modify: `backend/tests/test_comic_render_v2_resolver.py`
  - Cover narrow benchmark checkpoint overrides that do not disturb the default path.
- Modify: `backend/tests/test_launch_camila_v2_comic_pilot.py`
  - Cover new pilot script flags and payload emission.
- Modify: `lab451-animation-worker/app/config.py`
  - Add env-backed settings for general SDXL IPAdapter, plus-face SDXL IPAdapter, optional FaceID assets, and repair defaults.
- Modify: `lab451-animation-worker/app/workflows.py`
  - Parse adapter profile selection, add a repair request shape, and build a source-image face-repair workflow.
- Modify: `lab451-animation-worker/app/executors.py`
  - Resolve the right IPAdapter asset, enforce optional FaceID availability, and route comic still requests to base vs repair workflows.
- Modify: `lab451-animation-worker/.env.example`
  - Document new worker env vars for plus-face and FaceID assets.
- Modify: `lab451-animation-worker/README.md`
  - Document new local assets, install paths, and the two-stage still flow.
- Modify: `lab451-animation-worker/run_local_animation_worker.sh`
  - Export the new env vars with safe defaults.
- Modify: `lab451-animation-worker/run_server_animation_worker.sh`
  - Export the new env vars with safe defaults.
- Modify: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`
  - Cover parsing, workflow construction, and executor routing for plus-face and repair jobs.
- Create: `docs/quality/2026-04-16-local-manga-still-asset-checklist.md`
  - Pin the exact asset filenames, install directories, and benchmark order for the local operator.

### Task 1: Add local asset checklist and preflight coverage

**Files:**
- Create: `docs/quality/2026-04-16-local-manga-still-asset-checklist.md`
- Modify: `backend/scripts/check_local_animation_preflight.py`

- [ ] **Step 1: Write the asset checklist doc**

Create a small operator-facing checklist that pins the exact filenames and install targets:

```text
models/ipadapter/ip-adapter-plus-face_sdxl_vit-h.safetensors
models/ipadapter/ip-adapter-faceid-plusv2_sdxl.bin
models/loras/ip-adapter-faceid-plusv2_sdxl_lora.safetensors
models/checkpoints/noobaiXLNAIXL_vPred10Version.safetensors
```

Include:
- which assets are required vs optional
- where each file goes
- which benchmark order to run after install

- [ ] **Step 2: Extend the preflight script with new checks**

Update `backend/scripts/check_local_animation_preflight.py` to:
- keep the current general IPAdapter check
- add an explicit pass/fail check for `plus-face SDXL`
- add optional visibility checks for FaceID + LoRA
- add an optional visibility check for `NoobAI-XL`

- [ ] **Step 3: Run the preflight script**

Run:

```bash
PYTHONPATH=backend python3 backend/scripts/check_local_animation_preflight.py
```

Expected:
- current installed assets still pass
- new checks show missing face assets until they are installed
- script output remains human-readable

- [ ] **Step 4: Commit**

```bash
git add docs/quality/2026-04-16-local-manga-still-asset-checklist.md backend/scripts/check_local_animation_preflight.py
git commit -m "docs: add local manga still asset checklist"
```

### Task 2: Add worker config for adapter profiles

**Files:**
- Modify: `lab451-animation-worker/app/config.py`
- Modify: `lab451-animation-worker/.env.example`
- Modify: `lab451-animation-worker/run_local_animation_worker.sh`
- Modify: `lab451-animation-worker/run_server_animation_worker.sh`
- Modify: `lab451-animation-worker/README.md`
- Test: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`

- [ ] **Step 1: Write the failing worker config test**

Add focused tests proving the still worker can resolve distinct adapter assets:

```python
assert request.ipadapter_file == "ip-adapter-plus-face_sdxl_vit-h.safetensors"
assert request.adapter_profile == "plus_face"
```

Also add a failure assertion for unsupported adapter profiles.

- [ ] **Step 2: Run the focused worker test to verify failure**

Run:

```bash
python3 -m pytest -q lab451-animation-worker/tests/test_comic_panel_still_worker.py -k "adapter_profile or plus_face"
```

Expected: FAIL because the worker only knows one IPAdapter asset today.

- [ ] **Step 3: Add the minimal config surface**

Add worker settings and env docs for:

```text
WORKER_COMFYUI_IPADAPTER_MODEL
WORKER_COMFYUI_IPADAPTER_PLUS_FACE_MODEL
WORKER_COMFYUI_IPADAPTER_FACEID_MODEL
WORKER_COMFYUI_IPADAPTER_FACEID_LORA
```

Document that:
- general model stays the default for broad composition guidance
- plus-face is the preferred still repair asset
- FaceID remains optional

- [ ] **Step 4: Re-run the focused worker test**

Run:

```bash
python3 -m pytest -q lab451-animation-worker/tests/test_comic_panel_still_worker.py -k "adapter_profile or plus_face"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lab451-animation-worker/app/config.py lab451-animation-worker/.env.example lab451-animation-worker/run_local_animation_worker.sh lab451-animation-worker/run_server_animation_worker.sh lab451-animation-worker/README.md lab451-animation-worker/tests/test_comic_panel_still_worker.py
git commit -m "feat: add worker adapter profile config"
```

### Task 3: Add a source-image face-repair workflow in the worker

**Files:**
- Modify: `lab451-animation-worker/app/workflows.py`
- Modify: `lab451-animation-worker/app/executors.py`
- Test: `lab451-animation-worker/tests/test_comic_panel_still_worker.py`

- [ ] **Step 1: Write the failing repair workflow tests**

Add tests covering:

```python
request, refs = parse_sdxl_ipadapter_still_payload(payload, ...)
assert request.adapter_profile == "plus_face"
assert request.repair_enabled is True
assert request.repair_denoise == pytest.approx(0.28)
```

Add a workflow test asserting the repair builder uses:
- `LoadImage`
- `VAEEncode`
- `IPAdapterAdvanced`
- `KSampler` with low denoise
- `SaveImage`

- [ ] **Step 2: Run the focused repair tests to verify failure**

Run:

```bash
python3 -m pytest -q lab451-animation-worker/tests/test_comic_panel_still_worker.py -k "repair_workflow or repair_enabled"
```

Expected: FAIL because no repair request or workflow exists yet.

- [ ] **Step 3: Add the minimal repair request shape**

Extend `SDXLIPAdapterRequest` with narrow still-only fields:

```python
adapter_profile: str
repair_enabled: bool
repair_denoise: float
repair_strength: float
```

Only support:
- `general`
- `plus_face`
- `faceid_plus_v2`

Reject unknown profiles early.

- [ ] **Step 4: Implement the repair workflow builder**

Add a new workflow builder that:
- loads a source image
- optionally rescales it
- VAE-encodes the source image
- applies the selected face IPAdapter
- runs low-denoise sampling
- saves a repaired still

Do not add ControlNet or ADetailer in this task.

- [ ] **Step 5: Route executor handling**

Update `lab451-animation-worker/app/executors.py` so comic still jobs can:
- continue using the current empty-latent still path when `repair_enabled` is false
- require `source_image_url` when `repair_enabled` is true
- resolve the correct adapter file from `adapter_profile`

- [ ] **Step 6: Re-run the focused repair tests**

Run:

```bash
python3 -m pytest -q lab451-animation-worker/tests/test_comic_panel_still_worker.py -k "repair_workflow or repair_enabled"
```

Expected: PASS.

- [ ] **Step 7: Run the full worker still test file**

Run:

```bash
python3 -m pytest -q lab451-animation-worker/tests/test_comic_panel_still_worker.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add lab451-animation-worker/app/workflows.py lab451-animation-worker/app/executors.py lab451-animation-worker/tests/test_comic_panel_still_worker.py
git commit -m "feat: add comic still face repair workflow"
```

### Task 4: Emit adapter-profile and repair metadata from the backend

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/comic_render_service.py`
- Test: `backend/tests/test_comic_render_service.py`

- [ ] **Step 1: Write the failing backend payload tests**

Add focused tests that assert the comic render service emits worker payload metadata like:

```python
assert request_json["adapter_profile"] == "plus_face"
assert request_json["repair_enabled"] is True
assert request_json["repair_denoise"] == pytest.approx(0.28)
```

Keep a separate assertion proving the current base path still emits no repair metadata by default.

- [ ] **Step 2: Run the focused backend tests to verify failure**

Run:

```bash
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_comic_render_service.py -k "adapter_profile or repair_enabled"
```

Expected: FAIL because backend payloads do not include these fields yet.

- [ ] **Step 3: Add narrow backend config**

Expose only the minimal settings needed for the backend to choose defaults:

```text
HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_ENABLED
HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_ADAPTER_PROFILE
HOLLOWFORGE_REFERENCE_GUIDED_REPAIR_DENOISE
```

Do not add a large repair policy matrix in this task.

- [ ] **Step 4: Emit repair metadata minimally**

Update `backend/app/services/comic_render_service.py` so reference-guided still payloads can include:
- `adapter_profile`
- `repair_enabled`
- `repair_denoise`

Keep the current base still generation contract intact when the feature is off.

- [ ] **Step 5: Re-run the focused backend tests**

Run:

```bash
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_comic_render_service.py -k "adapter_profile or repair_enabled"
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/services/comic_render_service.py backend/tests/test_comic_render_service.py
git commit -m "feat: emit still repair metadata"
```

### Task 5: Add a narrow benchmark checkpoint override path

**Files:**
- Modify: `backend/app/services/comic_render_v2_resolver.py`
- Test: `backend/tests/test_comic_render_v2_resolver.py`

- [ ] **Step 1: Write the failing resolver tests**

Add a test proving the resolver keeps the current defaults unless an explicit benchmark override is present:

```python
assert contract.execution_params["checkpoint"] == "prefectIllustriousXL_v70.safetensors"
```

Add a second test proving an explicit benchmark override can switch to `NoobAI-XL` without mutating the default resolver registry.

- [ ] **Step 2: Run the focused resolver tests to verify failure**

Run:

```bash
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_comic_render_v2_resolver.py -k "benchmark_override or noobai"
```

Expected: FAIL because the resolver does not support a narrow benchmark override path yet.

- [ ] **Step 3: Implement the minimal override hook**

Add a resolver-level hook that:
- keeps current production defaults untouched
- allows the pilot path to request a known benchmark checkpoint by id
- only supports a tiny allowlist in this task:
  - `prefect_v70`
  - `hassaku_v34`
  - `noobai_xl`

- [ ] **Step 4: Re-run the focused resolver tests**

Run:

```bash
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_comic_render_v2_resolver.py -k "benchmark_override or noobai"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/comic_render_v2_resolver.py backend/tests/test_comic_render_v2_resolver.py
git commit -m "feat: add narrow still benchmark checkpoint override"
```

### Task 6: Upgrade the Camila pilot launcher for base-vs-repair and checkpoint A/B runs

**Files:**
- Modify: `backend/scripts/launch_camila_v2_comic_pilot.py`
- Test: `backend/tests/test_launch_camila_v2_comic_pilot.py`

- [ ] **Step 1: Write the failing pilot script tests**

Add tests for new CLI flags such as:

```python
--benchmark-checkpoint noobai_xl
--repair-pass on
--repair-pass off
```

Assert the script sends the expected request payload fields and does not break the current default run shape.

- [ ] **Step 2: Run the focused pilot tests to verify failure**

Run:

```bash
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_launch_camila_v2_comic_pilot.py -k "benchmark_checkpoint or repair_pass"
```

Expected: FAIL because the script does not expose those flags yet.

- [ ] **Step 3: Add the minimal CLI surface**

Teach the pilot launcher to:
- choose one of the allowed benchmark checkpoints
- toggle repair metadata on/off
- print those selections in the run markers

Do not add a generic arbitrary checkpoint flag in this task.

- [ ] **Step 4: Re-run the focused pilot tests**

Run:

```bash
PYTHONPATH=backend python3 -m pytest -q backend/tests/test_launch_camila_v2_comic_pilot.py -k "benchmark_checkpoint or repair_pass"
```

Expected: PASS.

- [ ] **Step 5: Run the broader backend verification slice**

Run:

```bash
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_launch_camila_v2_comic_pilot.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/launch_camila_v2_comic_pilot.py backend/tests/test_launch_camila_v2_comic_pilot.py backend/tests/test_comic_render_service.py backend/tests/test_comic_render_v2_resolver.py
git commit -m "feat: add local manga still benchmark controls"
```

### Task 7: Run the first local validation matrix

**Files:**
- No code changes expected

- [ ] **Step 1: Install the required asset files**

Place:

```text
ip-adapter-plus-face_sdxl_vit-h.safetensors -> models/ipadapter
noobaiXLNAIXL_vPred10Version.safetensors -> models/checkpoints
```

Optionally place:

```text
ip-adapter-faceid-plusv2_sdxl.bin -> models/ipadapter
ip-adapter-faceid-plusv2_sdxl_lora.safetensors -> models/loras
```

- [ ] **Step 2: Re-run preflight**

Run:

```bash
PYTHONPATH=backend python3 backend/scripts/check_local_animation_preflight.py
```

Expected: required new assets show as present.

- [ ] **Step 3: Restart the local worker with the new asset env vars**

Run:

```bash
./run_local_animation_worker.sh
```

Expected: worker starts and logs the configured plus-face adapter name.

- [ ] **Step 4: Run the first benchmark matrix**

Run:

```bash
python3 scripts/launch_camila_v2_comic_pilot.py --base-url http://127.0.0.1:8012 --benchmark-checkpoint prefect_v70 --repair-pass off
python3 scripts/launch_camila_v2_comic_pilot.py --base-url http://127.0.0.1:8012 --benchmark-checkpoint hassaku_v34 --repair-pass off
python3 scripts/launch_camila_v2_comic_pilot.py --base-url http://127.0.0.1:8012 --benchmark-checkpoint noobai_xl --repair-pass off
python3 scripts/launch_camila_v2_comic_pilot.py --base-url http://127.0.0.1:8012 --benchmark-checkpoint prefect_v70 --repair-pass on
```

Expected:
- all runs complete
- repair-enabled run materializes a repaired still
- establish outputs can be compared visually

- [ ] **Step 5: Capture the results in a short note**

Record:
- which checkpoint produced the best face appeal
- whether plus-face reduced hair/skin drift
- whether establish room readability stayed intact

### Task 8: Final verification and handoff

**Files:**
- Modify if needed: `lab451-animation-worker/README.md`
- Modify if needed: `docs/quality/2026-04-16-local-manga-still-asset-checklist.md`

- [ ] **Step 1: Run the worker test suite one final time**

Run:

```bash
python3 -m pytest -q lab451-animation-worker/tests/test_comic_panel_still_worker.py
```

Expected: PASS.

- [ ] **Step 2: Run the focused backend suite one final time**

Run:

```bash
PYTHONPATH=backend python3 -m pytest -q \
  backend/tests/test_comic_render_service.py \
  backend/tests/test_comic_render_v2_resolver.py \
  backend/tests/test_launch_camila_v2_comic_pilot.py
```

Expected: PASS.

- [ ] **Step 3: Update docs if the install filenames or benchmark ids changed**

Keep the operator checklist and README aligned with the final implementation.

- [ ] **Step 4: Commit**

```bash
git add lab451-animation-worker/README.md docs/quality/2026-04-16-local-manga-still-asset-checklist.md
git commit -m "docs: finalize local manga still upgrade runbook"
```
