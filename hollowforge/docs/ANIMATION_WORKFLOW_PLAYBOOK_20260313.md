# Animation Workflow Playbook

## Goal

As of March 13, 2026, the priority is not squeezing maximum motion out of the local Mac.
The priority is keeping a clean, testable animation workflow that:

- preserves character identity
- can be validated locally
- can be moved to a stronger remote worker later without changing the HollowForge job contract

## Current Recommendation

Use the `sdxl_ipadapter` lane as the canonical identity-first workflow.

- `sdxl_ipadapter_microanim_v1`
  - stable baseline
  - very conservative motion
- `sdxl_ipadapter_microanim_v2`
  - current preferred local preview lane
  - keeps identity while adding slightly stronger blink / head settle / breathing / hair sway

Treat the `ltxv_*` presets as experimental motion probes, not as the main quality lane for favorite-character animation.

## Why This Lane

The local `LTX` path can produce motion, but it drifts too far from the source character.
The local `SDXL + IPAdapter` path is slower and subtler, but it keeps face, hair, outfit, and framing materially closer to the source image.

That makes it a better workflow foundation:

- same source image contract
- same preset launch flow
- same remote worker callback flow
- only the worker execution backend needs to change later on a stronger server

## Contract

The reusable contract is already in place:

1. HollowForge creates an animation job with `request_json`
2. backend dispatches to `remote_worker`
3. worker receives:
   - `source_image_url`
   - `generation_metadata`
   - `request_json`
4. worker executes and calls back with `status`, `output_path`, and errors if any

For later server migration, keep the same `request_json` shape and swap worker capacity or backend implementation underneath it.

## Local Validation Evidence

Favorite source used for validation:

- generation: `de613bbf-217c-4b2d-827e-a40b5d59fc9b`
- source image: `data/images/2026/03/12/de613bbf-217c-4b2d-827e-a40b5d59fc9b.png`

Validated jobs:

- `sdxl_ipadapter_microanim_v1`
  - animation job: `915825f9-84dc-4e2e-aa7d-c00148a1efdc`
  - output: `lab451-animation-worker/data/outputs/c3abbbc6-b211-481f-8d24-8b169f9bff64.mp4`
  - result: identity good, motion too weak
- `sdxl_ipadapter_microanim_v2`
  - animation job: `18b7baf8-7a34-47f2-a32b-fd7770e32bd6`
  - output: `lab451-animation-worker/data/outputs/cc65c283-64c9-4bc7-8e85-16c33bf2adcd.mp4`
  - result: identity still good, motion slightly stronger, still preview-grade

## Canonical Checks

Run preflight:

```bash
cd backend
.venv/bin/python scripts/check_local_animation_preflight.py
```

Smoke-test a preset launch:

```bash
cd backend
.venv/bin/python scripts/launch_animation_preset_smoke.py \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --generation-id de613bbf-217c-4b2d-827e-a40b5d59fc9b
```

Watch an existing job:

```bash
cd backend
.venv/bin/python scripts/launch_animation_preset_smoke.py \
  --job-id 18b7baf8-7a34-47f2-a32b-fd7770e32bd6
```

## Canonical Runtime Entry Points

Local preview worker:

```bash
cd lab451-animation-worker
./run_local_animation_worker.sh
```

Server worker:

```bash
cd lab451-animation-worker
cp .env.server.example .env.server
set -a
source .env.server
set +a
./run_server_animation_worker.sh
```

Legacy compatibility entrypoint:

```bash
cd lab451-animation-worker
./run_local_ltxv_worker.sh
```

Use it only for backward compatibility. The canonical name is now `run_local_animation_worker.sh`.

## Server Migration Rule

If local output remains below release quality, stop spending time on local motion tuning and move the same workflow contract to server execution.

Server migration should preserve:

- same preset id or same `request_json` schema
- same backend route and launch flow
- same callback contract

Server migration may change:

- worker hardware
- worker executor backend
- model family actually used under the hood
- frame interpolation or post-processing

## Decision Rule Going Forward

- Local Mac:
  - use `sdxl_ipadapter_microanim_v2` as the default preview lane
  - use local runs for contract validation and rough motion review
- Remote GPU server:
  - use when motion quality, fidelity, or render speed becomes the bottleneck
  - keep the HollowForge orchestration contract unchanged wherever possible
