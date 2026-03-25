# Hollow Forge Quality Upscale Validation

## Summary

The redesigned `quality upscale` path is now stable enough to re-open as an explicit opt-in mode.

Follow-up validation after the initial 3-sample pass:

- `12 / 12` recent cross-checkpoint samples completed successfully
- batch result:
  - `data/validation/upscale_quality/quality_validation_batch12_20260308.json`
- summary:
  - `docs/QUALITY_UPSCALE_BATCH12_VALIDATION_20260308.md`

Current state:

- direct ComfyUI connectivity: restored
- model registration in Pinokio ComfyUI: restored
- staged quality workflow: executes successfully across a 3-sample validation batch
- batch-stable validation: achieved for the current MPS-safe configuration

## What Was Fixed

### 1. Direct ComfyUI Validation Path

The first validation failures were not purely workflow issues.

Root causes that were fixed:

- stale process holding port `8188`
- launch agent restart loop
- new upscale models present in Hollow Forge only, not in the resolved Pinokio ComfyUI model path (`$PINOKIO_COMFY_MODELS_DIR` or auto-detected fallback)

Actions taken:

- stale listener on `127.0.0.1:8188` was cleared
- `com.mori.hollowforge.comfyui.pinokio` was restarted
- the new Real-ESRGAN models were linked into the resolved Pinokio `upscale_models` directory (`$PINOKIO_PEERS_DIR/<peer>/upscale_models`)

### 2. Workflow Order

The original staged design used:

1. upscale
2. latent redraw

That caused MPS OOM on VAE encode.

The workflow was changed to:

1. latent redraw at source resolution
2. deterministic model upscale

This is now the active quality-workflow design in code.

### 3. MPS-Safe Clamp

The staged quality path was reduced further to stabilize repeated runs on Apple MPS:

- pre-redraw `ImageScale` down to a `1024` max side
- current 832x1216 samples redraw at `640x1024`
- redraw clamp:
  - `steps <= 10`
  - `cfg <= 5.0`
  - `denoise <= 0.16`

## Validation Evidence

### Successful Batch Output

Three redesigned quality samples completed sequentially and were written to:

- `data/validation/upscale_quality/c996c2ef-049c-4afd-b816-40cc29ceaac9_quality.png`
- `data/validation/upscale_quality/8c3fb245-658b-4c03-8b51-db25aa2d2d31_quality.png`
- `data/validation/upscale_quality/0e6c5bb8-d9c3-4366-abcf-da9939c0432c_quality.png`

Batch result JSON:

- `data/validation/upscale_quality/quality_validation_mpssafe_20260308.json`

Side-by-side comparisons:

- `data/validation/upscale_quality/c996_compare_quality.png`
- `data/validation/upscale_quality/quality_compare_triptych_20260308.png`

Visual result:

- the old broken `2x` redraw path remains clearly worse
- the redesigned quality path no longer shows tearing or tile breakage in the validation batch
- the new quality output is cleaner and more coherent than the broken redraw output

## Automatic Model Selection

Checkpoint-based recommendation is now implemented.

Current mapping:

- anime / illustration families -> `RealESRGAN_x4plus_anime_6B.pth`
- realistic / general families -> `realesr-general-x4v3.pth`
- legacy fallback -> `remacri_original.safetensors`

Sample mapping validated:

- `prefectIllustriousXL_v70.safetensors` -> `RealESRGAN_x4plus_anime_6B.pth`
- `animayhemPaleRider_v2TrueGrit.safetensors` -> `RealESRGAN_x4plus_anime_6B.pth`
- `waiIllustriousSDXL_v160.safetensors` -> `RealESRGAN_x4plus_anime_6B.pth`

## Decision

- `safe upscale`: keep enabled as the default path
- `auto model selection`: keep enabled
- `quality upscale`: re-enable as an explicit opt-in path
- `auto upscale on favorite`: keep disabled
- `UltimateSDUpscale`: keep disabled

## Residual Risk

The current validation proves the redesigned path is good enough to reopen carefully, but not to make it the default.

Remaining constraints:

- the validation set is still small
- Apple MPS memory behavior can still drift under heavier mixed workloads
- `safe` remains the lower-risk path for bulk queue usage

So the correct operating model is:

- `safe` for default and bulk use
- `quality` for deliberate, manual per-image enhancement
