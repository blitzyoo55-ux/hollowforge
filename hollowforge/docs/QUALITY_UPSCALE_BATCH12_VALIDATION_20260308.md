# Hollow Forge Quality Upscale Batch-12 Validation

## Summary

- Validation scope: `12` recent completed generations
- Selection rule:
  - recent completed images
  - max `2` samples per checkpoint
- Result: `12 / 12 ok`
- Failure count: `0`
- Artifact class seen in this run:
  - tearing: `0`
  - tile breakage: `0`
  - blocked workflow: `0`

## Validation Artifact

- JSON result:
  - [quality_validation_batch12_20260308.json](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/data/validation/upscale_quality/quality_validation_batch12_20260308.json)

## Families Validated

### anime-illustration -> `RealESRGAN_x4plus_anime_6B.pth`

- `ultimateHentaiAnimeRXTRexAnime_rxV1`
- `waiIllustriousSDXL_v140`
- `waiIllustriousSDXL_v160`
- `autismmixSDXL_autismmixConfetti`
- `hassakuXLIllustrious_v34`
- `animayhemPaleRider_v2TrueGrit`
- `prefectIllustriousXL_v70`
- `illustrij_v20`

### hybrid-clean -> `remacri_original.safetensors`

- `akiumLumenILLBase_baseV2`

## What Changed In Recommendation Policy

The profile classifier is now more useful for actual Hollow Forge checkpoint families.

New profile buckets:

- `anime-illustration`
- `hybrid-clean`
- `general-realistic`
- `general-clean`

Important additions:

- `prefect`
- `illustrij`
- `autismmix`
- `oneObsession`
- `ultimateHentaiAnime`
- `akiumLumenILLBase`
- `ponyRealism`

This closes the earlier gap where several real-world checkpoints were being treated as generic models.

## Operational Decision

- `Safe Upscale`
  - keep as default
- `Quality Upscale`
  - keep enabled as manual opt-in
- `UltimateSDUpscale`
  - keep disabled
- favorite auto-upscale
  - keep disabled

## Model Inventory Decision

No additional upscale model is required right now.

Current installed set is sufficient for the validated families:

- `RealESRGAN_x4plus_anime_6B.pth`
- `realesr-general-x4v3.pth`
- `remacri_original.safetensors`

## Remaining Gap

This batch was still heavily weighted toward anime / illustrative SDXL families.

The next useful validation is not more anime samples.
It is a smaller targeted run on realistic/general checkpoints such as:

- `juggernautXL_ragnarokBy`
- `realisticVisionV60B1_v51HyperVAE`
- `ponyRealism_V22`

That will validate whether `general-realistic -> realesr-general-x4v3` should stay as-is or move toward `remacri` for some hybrid families.
