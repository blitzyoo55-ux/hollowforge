# Local I2V Pipeline Plan

Date: 2026-03-12

## Summary

HollowForge can orchestrate animation jobs today, but it does not yet execute local image-to-video inference itself.

Current state:

- HollowForge animation orchestration exists.
- The current dispatch path is remote-worker oriented.
- ComfyUI on this machine already contains native node support for:
  - LTX-Video
  - Wan 2.1 / 2.2
  - Hunyuan Video / Hunyuan Video 1.5 I2V
  - Stable Video Diffusion (SVD)
- No local video model weights are installed yet.

Recommendation:

- Phase 1 local backend: `LTX-Video 2B distilled fp8`
- Phase 1 fallback backend: `SVD-XT 1.1`
- Phase 2 quality backend: `Wan2.2 TI2V-5B`
- Defer on this machine:
  - `LTX-2 19B / LTX-2.3 22B`
  - `Wan2.2 I2V-A14B`
  - `HunyuanVideo-I2V`
  - `CogVideoX` via extra wrapper

## Local Audit

### Machine

- Device backend: `mps`
- Unified memory total: `25.7 GB`
- Free at inspection time: about `3.4 GB`

Implication:

- Short local animation tests are possible.
- Heavy 14B-class I2V models are not a good first target on this Mac.
- Local video runs should not compete with a large image generation queue.

### ComfyUI Install

Running ComfyUI path:

- `$PINOKIO_COMFY_APP_DIR`
- fallback: `$PINOKIO_ROOT_DIR/api/comfy.git/app`
- if unset, HollowForge auto-detects `pinokio/` from the workspace root, then `~/AI_Projects/pinokio`, then `~/AI_projects/pinokio`

### Native ComfyUI Video Node Support Found

- LTX-Video nodes:
  - `$PINOKIO_COMFY_APP_DIR/comfy_extras/nodes_lt.py`
- Wan nodes:
  - `$PINOKIO_COMFY_APP_DIR/comfy_extras/nodes_wan.py`
- Hunyuan video nodes:
  - `$PINOKIO_COMFY_APP_DIR/comfy_extras/nodes_hunyuan.py`
- Stable Video Diffusion nodes:
  - `$PINOKIO_COMFY_APP_DIR/comfy_extras/nodes_video_model.py`

### Model Directories

ComfyUI model folders:

- diffusion models:
  - `$PINOKIO_COMFY_MODELS_DIR/diffusion_models`
- text encoders:
  - `$PINOKIO_COMFY_MODELS_DIR/text_encoders`
- vae:
  - `$PINOKIO_COMFY_MODELS_DIR/vae`
- clip vision:
  - `$PINOKIO_COMFY_MODELS_DIR/clip_vision`

Installed state at inspection time:

- no video diffusion models present
- no video text encoders present
- shared image VAEs are present
- shared image clip-vision assets are present
- no video-specific clip-vision assets are present for Hunyuan I2V

## Current Open Model Snapshot

This ranking is a practical inference based on:

- official repository popularity
- official ComfyUI native support
- official model release maturity
- local Apple Silicon feasibility on this machine

Practical ranking for this Mac:

1. `LTX-Video 2B distilled fp8`
2. `Wan2.2 TI2V-5B`
3. `SVD-XT 1.1`
4. `LTX-2 19B / LTX-2.3 22B`
5. `HunyuanVideo-I2V`

Interpretation:

- `LTX` and `Wan` are the strongest open families to anchor around right now.
- `LTX-2` and `LTX-2.3` are newer and stronger, but too large for a comfortable first local rollout on this Mac.
- `Wan2.2 TI2V-5B` is the best quality-oriented second step because it supports both text-to-video and image-to-video in one model line.
- `SVD-XT` is older, but still the best fallback when we care more about getting a worker contract stable than squeezing out the best motion quality.
- `HunyuanVideo-I2V` is officially strong, but its official runtime requirements put it outside the realistic local-first path here.

## Recommended Model Strategy

### Tier 1: Best Local First Pick

#### LTX-Video 2B distilled fp8

Why:

- best fit for this Mac
- official local repo explicitly mentions macOS MPS support
- ComfyUI core already has native LTX nodes
- quality is strong enough for a first production-grade local I2V path
- smaller and safer than the newer LTX-2 19B / LTX-2.3 22B line

Recommended profile:

- start with the 2B line, not 13B or 19B / 22B
- prefer short clips
- keep first implementation at lower motion / moderate frame counts

Required downloads:

1. LTX 2B diffusion checkpoint
   - preferred:
     - `ltxv-2b-0.9.8-distilled-fp8.safetensors`
   - compatibility fallback:
     - `ltx-video-2b-v0.9.5.safetensors`
2. text encoder
   - `t5xxl_fp16.safetensors`

Target locations:

- checkpoint:
  - `$PINOKIO_COMFY_MODELS_DIR/checkpoints`
- text encoder:
  - `$PINOKIO_COMFY_MODELS_DIR/text_encoders`

Notes:

- The checkpoint-style ComfyUI example is the safest starting path here.
- This avoids solving a bigger diffusers-folder import problem on day one.

### Tier 1 Fallback

#### Stable Video Diffusion XT 1.1

Why:

- easiest fallback path
- native ComfyUI support is already present
- very established image-to-video baseline
- useful when we want predictable short animations quickly

Tradeoff:

- lower ceiling than newer models
- shorter clip assumptions
- weaker motion realism than newer open video models

Use case:

- fast validation of the local worker contract
- emergency fallback when LTX fails

### Tier 2 Experimental

#### Wan2.2 TI2V-5B

Why:

- currently one of the most interesting open video families
- native ComfyUI support is already present locally
- official ComfyUI examples exist for both pure Wan2.2 I2V and the 5B TI2V hybrid
- much more realistic target than Wan2.2 I2V-A14B on this machine
- best second-stage backend if we want better motion and aesthetic ceiling than SVD

Required downloads:

1. `wan2.2_ti2v_5B_fp16.safetensors`
2. `umt5_xxl_fp8_e4m3fn_scaled.safetensors`
3. `wan2.2_vae.safetensors`

Target locations:

- diffusion model:
  - `$PINOKIO_COMFY_MODELS_DIR/diffusion_models`
- text encoder:
  - `$PINOKIO_COMFY_MODELS_DIR/text_encoders`
- vae:
  - `$PINOKIO_COMFY_MODELS_DIR/vae`

Why not Tier 1:

- higher memory risk than LTX 2B
- less confidence on Apple Silicon MPS as a first local production path
- should be validated only after LTX worker flow is stable

## Models To Avoid First On This Machine

### LTX-2 19B / LTX-2.3 22B

Reason:

- officially attractive and newer than LTX 0.9.x
- but much larger than the 2B path
- not a good first local rollout on a 25.7 GB unified-memory Mac
- better treated as a later experiment after the worker contract is stable

### Wan2.2 I2V-A14B

Reason:

- I2V path is 14B-class and much heavier than the TI2V-5B hybrid path
- not a good first target on a 25.7 GB unified-memory Mac

### HunyuanVideo-I2V

Reason:

- official repo documents Linux + CUDA
- official requirement is roughly 60 GB minimum for 720p I2V

### CogVideoX 1.5 I2V

Reason:

- attractive open model, but not the best first fit here
- current HollowForge / ComfyUI local stack does not already include the wrapper path
- official optimization notes are centered on NVIDIA A100/H100 and diffusers

Use later only if:

- we add a dedicated ComfyUI wrapper path
- or we move the video worker onto a Linux CUDA machine

## HollowForge Pipeline Shape

### Existing Responsibilities

HollowForge already covers:

- image generation
- selection / review
- animation job records
- animation dispatch contract
- callback ingestion

What is missing:

- a real local execution backend for I2V

### Recommended Execution Split

#### HollowForge

- create animation candidates
- create animation jobs
- store request metadata
- dispatch jobs to worker
- receive callback
- attach mp4 output to records

#### Local Animation Worker

- receive job request
- download source image from HollowForge
- map `target_tool` and `request_json` to a ComfyUI workflow
- enqueue workflow into local ComfyUI
- poll prompt execution
- move output video into worker output directory
- callback HollowForge with final status and output path

## Worker Contract

### Worker Input

Keep the current HollowForge contract and add a profile-oriented request payload:

```json
{
  "backend_family": "ltxv",
  "model_profile": "ltxv_2b_fast",
  "prompt": "long descriptive motion prompt",
  "negative_prompt": "default negative prompt",
  "width": 768,
  "height": 512,
  "frames": 49,
  "fps": 12,
  "steps": 24,
  "cfg": 3.5,
  "motion_strength": 0.55,
  "seed": 12345
}
```

Phase 1 routing note:

- HollowForge already supports `wan_i2v`, but it does not yet expose a dedicated `ltxv` target tool.
- The lowest-risk first implementation is:
  - `target_tool = "custom"`
  - `request_json.backend_family = "ltxv"`
  - `request_json.model_profile = "ltxv_2b_fast"`
- Once the worker path is stable, we can decide whether a first-class `ltxv_i2v` enum is worth adding.

### Initial Profiles

Start with only these:

- `ltxv_2b_fast`
- `ltxv_2b_quality`
- `svd_xt_fast`

Add later:

- `wan22_ti2v_5b_quality`

### Output

Worker returns:

- `status`
- `external_job_id`
- `output_path`
- optional `error_message`

## Implementation Order

### Step 1

Add a separate local worker service:

- project name suggestion:
  - `lab451-animation-worker`

### Step 2

Implement only one backend first:

- `ltxv_2b_fast`

### Step 3

Use a fixed ComfyUI workflow template:

- source image
- prompt / negative prompt
- LTX image-to-video nodes
- fixed short clip defaults

### Step 4

Add worker callback into HollowForge animation jobs.

### Step 5

Add `svd_xt_fast` fallback profile.

### Step 6

Only after that, test `wan22_ti2v_5b_quality`.

## First Download Set

If we want the smallest useful first install, download only:

1. `ltxv-2b-0.9.8-distilled-fp8.safetensors`
2. `t5xxl_fp16.safetensors`

Optional next:

3. `svd_xt.safetensors` or `stable-video-diffusion-img2vid-xt-1-1`
4. `wan2.2_ti2v_5B_fp16.safetensors`
5. `umt5_xxl_fp8_e4m3fn_scaled.safetensors`
6. `wan2.2_vae.safetensors`

Do not download first:

- LTX-2 19B / LTX-2.3 22B
- Wan2.2 14B I2V
- HunyuanVideo-I2V
- CogVideoX full stack

## Next Build Target

The next concrete implementation target should be:

- a local worker that accepts one HollowForge animation job
- runs `ltxv_2b_fast`
- generates a short mp4
- posts a callback back to HollowForge

Once that path is stable, we can widen the backend matrix.
