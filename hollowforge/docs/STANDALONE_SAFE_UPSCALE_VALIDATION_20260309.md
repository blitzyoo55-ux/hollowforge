# Standalone Safe Upscale Validation - 2026-03-09

## Result

The new standalone `safe` upscale runner passed the representative validation set.

- samples tested: `5`
- profiles covered:
  - `anime-illustration` x2
  - `hybrid-clean` x1
  - `general-realistic` x2
- visual corruption: `not observed`

## Output Artifacts

- JSON summary:
  - `data/validation/upscale_safe_runner/standalone_safe_validation_20260309.json`
- contact sheet:
  - `data/validation/upscale_safe_runner/standalone_safe_contact_sheet_20260309.png`

## Sample Set

1. `ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors`
   - model: `RealESRGAN_x4plus_anime_6B.pth`
2. `waiIllustriousSDXL_v140.safetensors`
   - model: `RealESRGAN_x4plus_anime_6B.pth`
3. `akiumLumenILLBase_baseV2.safetensors`
   - model: `remacri_original.safetensors`
4. `lunarcherrymix_v24.safetensors`
   - model: `realesr-general-x4v3.pth`
5. `lunarcherrymix_v24.safetensors`
   - model: `realesr-general-x4v3.pth`

## Runtime Characteristics

- average processing time: `~67.8 sec / image`
- environment: local CPU runner with cached model instances

## Operational Assessment

The standalone runner fixes the corruption problem, but it is too slow for a large backlog.

At the observed rate:

- `798` favorites would take roughly `15 hours`

This is acceptable for:

- single-image manual upscale
- small daily batches of newly favorited images

This is not acceptable for:

- immediate bulk reprocessing of the full favorites backlog on the current Mac mini

## Recommended Policy

1. Keep `safe` routed to the standalone runner.
2. Keep `quality` disabled.
3. Keep full-backlog auto processing disabled.
4. Re-enable only `daily new favorites` in small controlled batches after approval.
