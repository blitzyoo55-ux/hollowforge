# Upscale Artifact Diagnosis

Date: 2026-03-07

## Immediate actions taken

- Cancelled all active upscale postprocess jobs in `data/hollowforge.db`
  - `queued/running -> failed`
  - affected rows: `789`
- Restarted the HollowForge backend worker to flush the in-memory queue.
- Added temporary safeguards:
  - disabled favorite-triggered auto-upscale by default
  - disabled `UltimateSDUpscale` by default

## What was observed

- Recent upscale results split into two distinct groups:
  - `4x` outputs: visually mostly intact
  - `2x` outputs: severe tearing / banding / tile corruption
- Sample comparison showed the corruption pattern only on `2x` outputs.
- In the most recent sample set checked, scale distribution was:
  - `4x`: 7 files
  - `2x`: 7 files

## Working hypothesis

- The artifact is not primarily the ESRGAN model file itself.
- The likely problem is the ComfyUI `UltimateSDUpscale` path used for `2x` jobs.
- The safer outputs appear to come from the simpler ESRGAN path or CPU fallback path, which preserves the model-native `4x` result.

## Code changes applied

- `backend/app/config.py`
  - `HOLLOWFORGE_AUTO_UPSCALE_FAVORITES` default `false`
  - `HOLLOWFORGE_UPSCALE_USE_ULTIMATE` default `false`
  - `HOLLOWFORGE_UPSCALE_QUALITY_ENABLED` default `false`
- `backend/app/routes/favorites.py`
  - favorite toggle no longer auto-queues upscale unless explicitly enabled
- `backend/app/services/generation_service.py`
  - `UltimateSDUpscale` is now opt-in, not default
  - upscale flow now separates:
    - `safe`: model-only path
    - `quality`: redraw path, currently guarded
- `backend/app/routes/system.py`
  - upscale capability response now exposes whether quality mode is enabled
- `frontend/src/pages/ImageDetail.tsx`
  - UI now separates `Safe Upscale` and `Quality Upscale`

## Operational conclusion

- Current upscale queue has been stopped.
- Auto-refill from favorites has been blocked.
- The highest-confidence short-term mitigation is:
  - keep `UltimateSDUpscale` and `quality` mode off
  - use only `Safe Upscale` until a dedicated ComfyUI redraw workflow is rebuilt and validated

## Remaining work

- Re-validate one sample end-to-end after ComfyUI connectivity is stable.
- Build a dedicated upscale workflow that avoids latent/tile redraw corruption.
- If needed, split modes:
  - `safe upscale`: ESRGAN only
  - `quality upscale`: optional ComfyUI redraw path after validation
