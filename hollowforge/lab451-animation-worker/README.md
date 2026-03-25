# Lab451 Animation Worker

Separate execution worker for HollowForge animation jobs.

## Purpose
- Accept animation jobs from HollowForge
- Execute them behind a pluggable backend
- Report status back through a callback contract
- Keep the execution layer swappable between local ComfyUI and remote GPU hosts

## Supported backends
- `stub`
  - accepts jobs
  - simulates submit / processing / completion
  - writes a dummy `.mp4` output file
  - calls back into HollowForge
- `comfyui_pipeline`
  - downloads the source still from HollowForge
  - uploads it into a local ComfyUI instance
  - selects the actual rendering family from `request_json.backend_family`
  - currently supports:
    - `ltxv`
    - `sdxl_ipadapter`
  - copies the rendered artifact into `data/outputs`
  - calls back into HollowForge with the worker output URL

Compatibility alias:
- `comfyui_ltxv`
  - still accepted as a legacy executor backend name

## Run
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8600 --reload
```

Convenience launcher:
```bash
./run_local_animation_worker.sh
```

Server-oriented launcher:
```bash
WORKER_PUBLIC_BASE_URL=https://animation-worker.example.com \
./run_server_animation_worker.sh
```

## Important env vars
- `WORKER_API_TOKEN`
- `WORKER_EXECUTOR_BACKEND`
- `WORKER_PUBLIC_BASE_URL`
- `WORKER_DATA_DIR`
- `WORKER_DEFAULT_NEGATIVE_PROMPT`

## ComfyUI backend env vars
- `WORKER_EXECUTOR_BACKEND=comfyui_pipeline`
- `WORKER_COMFYUI_URL=http://127.0.0.1:8188`
- `WORKER_COMFYUI_LTXV_CHECKPOINT=ltxv-2b-0.9.8-distilled-fp8.safetensors`
- `WORKER_COMFYUI_LTXV_CHECKPOINT_FALLBACK=ltx-video-2b-v0.9.5.safetensors`
- `WORKER_COMFYUI_LTXV_TEXT_ENCODER=t5xxl_fp16.safetensors`
- `WORKER_COMFYUI_IPADAPTER_MODEL=ipAdapterPlusSd15_ipAdapterPlusSdxlVit.safetensors`
- `WORKER_COMFYUI_CLIP_VISION_MODEL=CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`
- `WORKER_COMFYUI_POLL_INTERVAL_SEC=2.0`
- `WORKER_COMFYUI_TIMEOUT_SEC=1800`

## Required local ComfyUI assets for phase 1
- LTX-Video checkpoint
  - `ltxv-2b-0.9.8-distilled-fp8.safetensors`
  - or fallback `ltx-video-2b-v0.9.5.safetensors`
- Text encoder
  - `t5xxl_fp16.safetensors`
- Native nodes
  - `LTXVImgToVideo`
  - `LTXVConditioning`
  - `LTXVScheduler`
  - `ModelSamplingLTXV`
  - `CreateVideo`
  - `SaveVideo`

## Expected HollowForge payload for phase 1
- `target_tool="custom"`
- `request_json.backend_family`
  - `ltxv`
  - or `sdxl_ipadapter`
- `request_json.model_profile`
  - example: `ltxv_2b_fast`
  - example: `sdxl_ipadapter_microanim_v2`

Example request fragment:
```json
{
  "target_tool": "custom",
  "request_json": {
    "backend_family": "sdxl_ipadapter",
    "model_profile": "sdxl_ipadapter_microanim_v2",
    "inherit_generation_prompt": true,
    "prompt": "Preserve original character identity, micro-expression only, subtle breathing only",
    "negative_prompt": "child, teen, underage, school uniform, text, logo, watermark, blurry, lowres, deformed, cropped face",
    "width": 512,
    "height": 768,
    "frames": 9,
    "fps": 7,
    "steps": 30,
    "cfg": 4.8,
    "seed": 42
  }
}
```

## HollowForge env vars
- `HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL=http://127.0.0.1:8600`
- `HOLLOWFORGE_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`
- `HOLLOWFORGE_ANIMATION_WORKER_API_TOKEN=...`
- `HOLLOWFORGE_ANIMATION_CALLBACK_TOKEN=...`

## Expected flow
1. HollowForge creates `animation_jobs`
2. HollowForge dispatches one job to this worker
3. Worker processes it with the configured backend
4. Worker posts progress back to HollowForge callback URL
5. HollowForge updates `animation_jobs` and related candidate state

## Preflight
Use the backend helper before the first real test job:
```bash
cd ../backend
./.venv/bin/python scripts/check_local_animation_preflight.py
```

## Smoke test
Use the canonical preview lane and wait for completion:
```bash
cd ../backend
./.venv/bin/python scripts/launch_animation_preset_smoke.py \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --generation-id de613bbf-217c-4b2d-827e-a40b5d59fc9b
```
