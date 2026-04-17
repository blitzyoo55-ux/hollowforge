# Lab451 Animation Worker

Separate execution worker for HollowForge animation and comic still jobs.

## Purpose
- Accept animation jobs from HollowForge
- Accept comic still jobs from HollowForge
- Execute them behind a pluggable backend
- Report status back through a callback contract
- Keep the execution layer swappable between local ComfyUI and remote GPU hosts

## Supported backends
- `stub`
  - accepts jobs
  - simulates submit / processing / completion
  - writes a dummy `.mp4` for animation jobs or `.png` for comic still jobs
  - calls back into HollowForge
- `comfyui_pipeline`
  - runs animation image-to-video jobs or comic still text-to-image jobs
  - downloads the source still from HollowForge when the job needs one
  - selects the actual rendering family from `request_json.backend_family`
  - currently supports:
    - `ltxv`
    - `sdxl_ipadapter`
    - `sdxl_still`
  - copies the rendered artifact into `data/outputs`
  - keeps `output_url` in the worker API as a full public worker URL
  - calls back into HollowForge with a data-relative `output_path`

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
- `WORKER_CF_ACCESS_CLIENT_ID`
- `WORKER_CF_ACCESS_CLIENT_SECRET`
- `WORKER_EXECUTOR_BACKEND`
- `WORKER_PUBLIC_BASE_URL`
- `WORKER_DATA_DIR`
- `WORKER_DEFAULT_NEGATIVE_PROMPT`
- `WORKER_FFMPEG_BIN`

Default storage root:
- if `WORKER_DATA_DIR` is unset, the worker uses the shared repo data root at `../data`
- in this repo layout that matches HollowForge backend `DATA_DIR`, so callback `output_path` values like `outputs/<file>` resolve against the same filesystem root

## Supported job payloads
- Animation jobs
  - `target_tool="custom"`
  - `source_image_url` is required
  - `request_json.backend_family`
    - `ltxv`
    - `sdxl_ipadapter`
- Comic still jobs
  - `target_tool="comic_panel_still"`
  - `source_image_url` is optional
  - `request_json` is required
  - `request_json.backend_family` must be `sdxl_still`
  - `request_json.still_generation` carries the text-to-image prompt and sampler settings

## ComfyUI backend env vars
- `WORKER_EXECUTOR_BACKEND=comfyui_pipeline`
- `WORKER_COMFYUI_URL=http://127.0.0.1:8188`
- `WORKER_COMFYUI_LTXV_CHECKPOINT=ltxv-2b-0.9.8-distilled-fp8.safetensors`
- `WORKER_COMFYUI_LTXV_CHECKPOINT_FALLBACK=ltx-video-2b-v0.9.5.safetensors`
- `WORKER_COMFYUI_LTXV_TEXT_ENCODER=t5xxl_fp16.safetensors`
- `WORKER_COMFYUI_IPADAPTER_MODEL=ipAdapterPlusSd15_ipAdapterPlusSdxlVit.safetensors`
- `WORKER_COMFYUI_IPADAPTER_PLUS_FACE_MODEL=ip-adapter-plus-face_sdxl_vit-h.safetensors`
- `WORKER_COMFYUI_IPADAPTER_FACEID_MODEL=ip-adapter-faceid-plusv2_sdxl.bin`
- `WORKER_COMFYUI_IPADAPTER_FACEID_LORA=ip-adapter-faceid-plusv2_sdxl_lora.safetensors`
- `WORKER_COMFYUI_CLIP_VISION_MODEL=CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`
- `WORKER_COMFYUI_POLL_INTERVAL_SEC=2.0`
- `WORKER_COMFYUI_TIMEOUT_SEC=1800`
- `WORKER_FFMPEG_BIN=/opt/homebrew/bin/ffmpeg`

Still adapter profile guidance:
- `general`
  - uses `WORKER_COMFYUI_IPADAPTER_MODEL`
  - keep this as the broad composition guidance default
- `plus_face`
  - uses `WORKER_COMFYUI_IPADAPTER_PLUS_FACE_MODEL`
  - use this as the preferred still-repair adapter once the face-specific asset is installed
- `faceid_plus_v2`
  - uses `WORKER_COMFYUI_IPADAPTER_FACEID_MODEL`
  - keep this optional until the FaceID asset pair is installed and the repair lane is enabled

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

## Expected comic still payload
- `target_tool="comic_panel_still"`
- `source_image_url` may be omitted
- `request_json` is required
- `request_json.backend_family` must be `sdxl_still`
- `request_json.still_generation`
  - `prompt`
  - `negative_prompt`
  - `checkpoint`
  - `loras`
  - `steps`
  - `cfg`
  - `width`
  - `height`
  - `sampler`
  - `scheduler`
  - `seed`

Example request fragment:
```json
{
  "hollowforge_job_id": "comic-job-1",
  "generation_id": "gen-1",
  "target_tool": "comic_panel_still",
  "executor_mode": "remote_worker",
  "executor_key": "default",
  "request_json": {
    "backend_family": "sdxl_still",
    "model_profile": "comic_panel_sdxl_v1",
    "still_generation": {
      "prompt": "waist-up manga panel, Kaede at the station platform, night rain, dramatic rim light",
      "negative_prompt": "child, teen, underage, text, logo, watermark, blurry, lowres",
      "checkpoint": "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
      "loras": [
        {
          "filename": "kaede_face.safetensors",
          "strength": 0.85
        }
      ],
      "width": 832,
      "height": 1216,
      "steps": 34,
      "cfg": 5.5,
      "sampler": "euler_ancestral",
      "scheduler": "normal",
      "seed": 77
    },
    "comic": {
      "scene_panel_id": "panel-1",
      "render_asset_id": "asset-1",
      "character_version_id": "charver_kaede_ren_still_v1"
    }
  }
}
```

## HollowForge env vars
- `HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL=http://127.0.0.1:8600`
- `HOLLOWFORGE_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`
- `HOLLOWFORGE_ANIMATION_WORKER_API_TOKEN=...`
- `HOLLOWFORGE_ANIMATION_CALLBACK_TOKEN=...`

## Expected flow
1. HollowForge creates an execution job in its own domain model
2. HollowForge dispatches one animation job or one comic render job (`target_tool="comic_panel_still"`) to this worker
3. Worker processes it with the configured backend
4. Worker posts progress back to HollowForge callback URL
5. HollowForge updates the job row and stores the returned `output_path`

Cloudflare Access note:
- if `HOLLOWFORGE_PUBLIC_API_BASE_URL` points to a hostname protected by
  Cloudflare Access, keep `callback_token` for the HollowForge callback route
  and also set `WORKER_CF_ACCESS_CLIENT_ID` plus
  `WORKER_CF_ACCESS_CLIENT_SECRET` so the worker can pass the Access layer for
  both HollowForge callbacks and source image downloads on that same trusted
  HollowForge host; the worker also rejects non-image source download responses
  before writing them into `data/inputs`

Comic still completion behavior:
- this flow is for comic render jobs using `target_tool="comic_panel_still"`, not `animation_jobs`
- the worker writes a standard image artifact into `data/outputs/{worker_job_id}.png`
- the callback payload uses the existing fields:
  - `status`
  - `external_job_id`
  - `external_job_url`
  - `output_path` as a data-relative path such as `outputs/{worker_job_id}.png`
- the worker job API still exposes `output_url` as the full public worker URL

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

## Focused verification for comic still support
```bash
../backend/.venv/bin/python -m pytest tests/test_comic_panel_still_worker.py -q
```
