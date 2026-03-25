# Hollow Forge Safe Upscale Revalidation

## Outcome

- `safe upscale` remains the only production-safe mode.
- `quality upscale` remains disabled.
- `UltimateSDUpscale` remains disabled.
- Favorite-triggered auto-upscale remains disabled.

## What Was Checked

### 1. Existing Artifact Review

Recent upscale outputs were reviewed again from the existing comparison sheet:

- healthy group: recent `4x` outputs
- broken group: recent `2x` outputs

Observed failure pattern on the broken group:

- horizontal tearing
- seam-like tiling artifacts
- severe banding
- partial redraw corruption

This is consistent with a redraw/tiled latent workflow failure, not a simple ESRGAN quality miss.

### 2. Safe Validation Harness Added

New script:

- `backend/scripts/validate_safe_upscale_samples.py`

Purpose:

- take known broken samples
- rerun them through the deterministic CPU safe path
- save comparison outputs under `data/validation/upscale_safe/`

### 3. CPU Fallback Cost Observation

The deterministic CPU fallback path is operational but extremely expensive on the current local
machine path:

- process memory grew into the multi-GB range
- runtime exceeded several minutes before even the first sample completed

That means:

- the CPU path is still useful as an emergency fallback
- it is not a practical batch validation or default operating path for repeated manual review

## Decision

### Keep

- `safe` mode as the default user-facing path
- local CPU fallback as a hard emergency fallback only

### Do Not Re-enable

- current `quality` redraw path
- current `UltimateSDUpscale` production path
- favorite-triggered auto-upscale

## Operational Flags

The backend runtime is now pinned to:

- `HOLLOWFORGE_AUTO_UPSCALE_FAVORITES=0`
- `HOLLOWFORGE_UPSCALE_USE_ULTIMATE=0`
- `HOLLOWFORGE_UPSCALE_QUALITY_ENABLED=0`

## Recommended Next Step

Rebuild `quality upscale` as a separate staged workflow:

1. deterministic model upscale
2. optional low-denoise detail recovery pass
3. acceptance gate before promotion

This redesign is documented in:

- `QUALITY_UPSCALE_REDESIGN_20260308.md`
