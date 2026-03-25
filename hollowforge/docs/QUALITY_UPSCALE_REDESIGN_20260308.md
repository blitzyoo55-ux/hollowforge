# Hollow Forge Quality Upscale Redesign

## Current Problem

- Recent `2x` upscale outputs show tearing, tile seams, and banding.
- Recent `4x` outputs are materially healthier.
- Current backend `quality` path is a single `UltimateSDUpscale` redraw workflow.
- Current backend `safe` path is the simpler `ImageUpscaleWithModel` path.

The working assumption is that the artifact source is not the `remacri_original.safetensors`
model itself, but the current `UltimateSDUpscale` redraw path at `2x`.

## Immediate Operating Position

- Keep `safe` as the only user-facing default.
- Keep `quality` disabled in server config.
- Keep favorite-triggered auto-upscale disabled.

This is already enforced with:

- `HOLLOWFORGE_AUTO_UPSCALE_FAVORITES=0`
- `HOLLOWFORGE_UPSCALE_USE_ULTIMATE=0`
- `HOLLOWFORGE_UPSCALE_QUALITY_ENABLED=0`

## Why The Current Quality Path Fails

Current `quality` is too tightly coupled:

1. ESRGAN-style upscale
2. Latent redraw
3. Tiled decode decisions
4. Seam behavior

All of that is hidden behind one `UltimateSDUpscale` node path. When it fails, the failure mode is
structural and visually catastrophic, not a mild quality drop.

## Proposed Replacement

Do not re-enable the current `UltimateSDUpscale` path.

Replace `quality upscale` with a staged workflow:

### Stage A: Deterministic Base Upscale

- Node path:
  - `LoadImage`
  - `UpscaleModelLoader`
  - `ImageUpscaleWithModel`
  - `SaveImage`
- Purpose:
  - Produce a clean, deterministic high-resolution base image.
- Scale:
  - Prefer `4x` base or `2x` only if output size constraints require it.

### Stage B: Optional Detail Recovery Pass

- Separate workflow, not the same graph as Stage A.
- Requirements:
  - Must use explicit latent encode/decode nodes.
  - Must use low denoise only.
  - Must be allowed to fail without replacing the Stage A result.
- Candidate shape:
  - `LoadImage`
  - `VAEEncode`
  - `KSampler` with low denoise
  - `VAEDecode`
  - `SaveImage`

### Stage C: Acceptance Gate

- Keep Stage A output.
- Only promote Stage B output if it passes manual validation or later automated image checks.
- If Stage B degrades structure, discard it and keep Stage A.

## Product Behavior

Expose two user intents:

- `Safe Upscale`
  - deterministic
  - default
  - always available when an upscale model exists
- `Quality Upscale`
  - experimental
  - only available when:
    - ComfyUI is reachable
    - required nodes are present
    - validation flag is enabled

## Installed Model Baseline

The local upscale model set is now:

- `RealESRGAN_x4plus_anime_6B.pth`
- `realesr-general-x4v3.pth`
- `remacri_original.safetensors`

Recommended usage:

- anime / illustration / stylized portraits:
  - `RealESRGAN_x4plus_anime_6B.pth`
- general / semi-real / mild cleanup:
  - `realesr-general-x4v3.pth`
- legacy fallback / compatibility:
  - `remacri_original.safetensors`

## Implementation Recommendation

1. Keep current `safe` implementation.
2. Remove `UltimateSDUpscale` from the default quality plan.
3. Add a new `build_quality_upscale_workflow()` builder instead of overloading
   `build_upscale_workflow(..., use_ultimate=True)`.
4. Add a per-workflow capability check:
   - `ImageUpscaleWithModel`
   - `VAEEncode`
   - `VAEDecode`
   - `KSampler`
5. Re-enable `quality` only after:
   - 3 to 5 sample images pass visual inspection
   - no tearing or seam artifacts appear
   - fallback behavior is explicit

## Decision

- `safe`: keep enabled
- `quality`: keep disabled
- `UltimateSDUpscale`: do not re-enable in production without a new validated workflow
