# Hollow Forge Quality Upscale Realistic / Hybrid Mix Validation

## Scope

Targeted validation was run against a mixed checkpoint set instead of the recent anime-heavy batch.

Target families:

- `juggernautXL_ragnarokBy`
- `realisticVisionV60B1_v51HyperVAE`
- `ponyRealism_V22`
- `lunarcherrymix_v24`
- `oneObsession_v19Atypical`
- `akiumLumenILLBase_baseV2`

Validation artifact:

- [quality_validation_realistic_mix_20260308.json](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/data/validation/upscale_quality/quality_validation_realistic_mix_20260308.json)

## Result

This run did **not** validate the staged quality path for the realistic/general family.

Observed outcome from the processed samples:

- `general-realistic` families:
  - `juggernautXL_ragnarokBy`
  - `realisticVisionV60B1_v51HyperVAE`
  - `lunarcherrymix_v24`
  - result: ComfyUI `400 Bad Request` on prompt submission
- `hybrid-clean` family:
  - `ponyRealism_V22`
  - result: ComfyUI `400 Bad Request` on prompt submission
- `anime-illustration` family inside the same set:
  - `oneObsession_v19Atypical`
  - result: `ok`

## Interpretation

The failure signal here is **not enough evidence to blame the upscale model**.

What it shows instead:

- the staged quality workflow is healthy for currently active anime/illustration checkpoints
- the current ComfyUI runtime does not reliably accept the realistic/hybrid checkpoint subset used in this test
- therefore realistic/hybrid quality validation is still blocked at the workflow runtime layer

## Policy Decision

### `anime-illustration`

- recommended model:
  - `RealESRGAN_x4plus_anime_6B.pth`
- recommended mode:
  - `quality` allowed as manual opt-in

### `hybrid-clean`

- recommended model:
  - `remacri_original.safetensors`
- recommended mode:
  - `safe`

### `general-realistic`

- recommended model:
  - `realesr-general-x4v3.pth`
- recommended mode:
  - `safe`

## Practical Conclusion

For realistic/general checkpoints, keep the model recommendation but do **not** promote `quality` as the preferred path yet.

The next requirement is not a new upscale model.
The next requirement is a ComfyUI runtime where those checkpoints can actually execute the staged quality graph.
