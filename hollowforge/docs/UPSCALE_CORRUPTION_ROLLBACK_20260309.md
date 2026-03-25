# Hollow Forge Upscale Corruption Rollback - 2026-03-09

## Summary

All current upscale outputs were rolled back after confirming a consistent corruption pattern in the active `safe` ComfyUI upscale path.

## Confirmed Symptoms

- Original generated images are normal.
- Upscaled images show severe horizontal line interleaving / striping.
- The corruption appears in both:
  - `RealESRGAN_x4plus_anime_6B.pth`
  - `remacri_original.safetensors`
- The corruption is present in both full PNG outputs and `_upscaled.jpg` previews.

## Key Evidence

Sample comparisons:

- Corrupted ComfyUI safe upscale:
  - `data/images/upscaled/3a6913f6-93eb-4a6d-930a-066008c395f4.png`
  - `data/images/upscaled/91479612-1a39-48ba-947c-3002d9144916.png`
- Clean original sources:
  - `data/images/2026/03/03/3a6913f6-93eb-4a6d-930a-066008c395f4.png`
  - `data/images/2026/03/03/91479612-1a39-48ba-947c-3002d9144916.png`
- Clean CPU fallback on the same source:
  - `data/diagnostics/upscale_compare/3d1d820d-ac91-4264-b0b9-4347f20aedea_cpu_safe.png`

## Root Cause Assessment

The failure is not tied to one ESRGAN model. The same artifact reproduces across multiple upscale models.

The failure is isolated to the active ComfyUI safe upscale path:

- workflow node path: `LoadImage -> UpscaleModelLoader -> ImageUpscaleWithModel -> SaveImage`
- runtime: Pinokio ComfyUI on local MPS

The strongest current conclusion is:

> `ImageUpscaleWithModel` in the current Pinokio ComfyUI + MPS runtime is producing corrupted image output, while the local CPU fallback path remains clean.

This means the current issue is runtime/path specific, not a favorite queue policy issue and not a model recommendation issue.

## Rollback Actions Applied

- Disabled favorite daily auto-upscale.
- Disabled quality upscale.
- Forced safe upscale to bypass ComfyUI and use CPU fallback only.
- Restarted the backend to clear in-memory upscale work.
- Cleared all `upscaled_image_path` / `upscaled_preview_path` references.
- Deleted all generated upscaled PNG/JPG files.

## State After Rollback

- favorite upscaled done: `0`
- favorite queued: `0`
- favorite running: `0`
- favorite pending: `798`
- daily scheduler: `disabled`

## Recommended Next Steps

### Immediate

1. Keep automatic favorite upscale disabled.
2. Keep quality upscale disabled.
3. Use CPU fallback only for single-image manual validation.

### Short-Term

1. Build a standalone non-ComfyUI upscale runner as the primary `safe` engine.
2. Revalidate 3-5 samples across anime and realistic checkpoints.
3. Only re-enable favorite batch processing after those samples are visually clean.

### Medium-Term

1. Separate `safe` and `quality` engines completely.
2. Do not use the current ComfyUI `ImageUpscaleWithModel` path on MPS for production backlog processing.
3. If ComfyUI upscale must stay, move it to a runtime that is known-good for ESRGAN inference instead of the current local MPS path.
