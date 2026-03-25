# Lab451 Animation Worker Setup

## Goal
- Keep HollowForge focused on orchestration
- Move GPU-heavy animation execution to a separate worker
- Preserve provider flexibility for future remote GPU hosts

## Separation of concerns

### HollowForge
- image generation
- ready-to-go approval
- publish queue
- engagement scoring
- animation candidate approval
- animation job creation and dispatch

### Animation Worker
- remote job intake
- execution backend selection
- progress updates
- output artifact hosting
- callback to HollowForge

## Implemented contract

### HollowForge → Worker
- `POST /api/v1/jobs`
- payload includes:
  - `hollowforge_job_id`
  - `generation_id`
  - `target_tool`
  - `executor_mode`
  - `executor_key`
  - `source_image_url`
  - `generation_metadata`
  - `request_json`
  - `callback_url`
  - `callback_token`

### Worker → HollowForge
- `POST /api/v1/animation/jobs/{job_id}/callback`
- callback carries:
  - `status`
  - `external_job_id`
  - `external_job_url`
  - `output_path`
  - `error_message`

## Recommended deployment modes

### Mode A — Same machine
- good for local contract testing
- use `stub` executor first

### Mode B — Remote VM / rented GPU
- recommended production direction
- run the worker near the GPU stack
- expose only worker API + output URLs

### Mode C — Container on GPU host
- suitable if the provider allows the target workload
- Runpod can host the worker container technically, but policy fit for the actual content must be checked before production use

## Minimum env

### HollowForge
- `HOLLOWFORGE_PUBLIC_API_BASE_URL`
- `HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL`
- `HOLLOWFORGE_ANIMATION_WORKER_API_TOKEN`
- `HOLLOWFORGE_ANIMATION_CALLBACK_TOKEN`

### Worker
- `WORKER_PUBLIC_BASE_URL`
- `WORKER_API_TOKEN`
- `WORKER_EXECUTOR_BACKEND`
- `WORKER_DATA_DIR`

## Current canonical worker lane

As of March 13, 2026, the recommended identity-first lane is:

- worker backend: `comfyui_pipeline`
- request family: `sdxl_ipadapter`
- preferred preset: `sdxl_ipadapter_microanim_v2`

This keeps the worker contract stable while allowing the actual rendering backend to change later on a stronger server.

## Recommended scripts

### Local validation
- `lab451-animation-worker/run_local_animation_worker.sh`
- `backend/scripts/check_local_animation_preflight.py`
- `backend/scripts/launch_animation_preset_smoke.py`

### Server deployment
- `lab451-animation-worker/run_server_animation_worker.sh`
- `lab451-animation-worker/.env.server.example`

The old `run_local_ltxv_worker.sh` remains as a compatibility wrapper only.

## Near-term next steps
- add worker auth hardening beyond shared bearer tokens
- add real executor backends behind the worker
- add template video / motion preset asset handoff
- add output pushback into HollowForge gallery records
