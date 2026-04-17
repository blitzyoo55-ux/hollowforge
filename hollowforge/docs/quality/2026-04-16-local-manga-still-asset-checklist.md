# Local Manga Still Asset Checklist

Date: 2026-04-16

Use this checklist after syncing the local ComfyUI model folder for the manga still lane.
The existing general IPAdapter asset is still required by preflight and stays unchanged.

## Required

- [ ] `models/ipadapter/ip-adapter-plus-face_sdxl_vit-h.safetensors`
  - Install target: `models/ipadapter/`
  - Purpose: required plus-face SDXL adapter for the local face-repair lane

## Optional Visibility Only

- [ ] `models/ipadapter/ip-adapter-faceid-plusv2_sdxl.bin`
  - Install target: `models/ipadapter/`
  - Purpose: FaceID adapter visibility check only

- [ ] `models/loras/ip-adapter-faceid-plusv2_sdxl_lora.safetensors`
  - Install target: `models/loras/`
  - Purpose: FaceID LoRA visibility check only

- [ ] `models/checkpoints/noobaiXLNAIXL_vPred10Version.safetensors`
  - Install target: `models/checkpoints/`
  - Purpose: optional benchmark checkpoint visibility check

## Install Order

1. Install the required plus-face SDXL IPAdapter.
2. Install the optional FaceID adapter and FaceID LoRA if you want the source-image repair lane.
3. Install the NoobAI-XL checkpoint only if you want to compare the alternate checkpoint family.

## Benchmark Order After Install

Run the benchmark comparison in this order:

1. `prefectIllustriousXL_v70`
2. `hassakuXLIllustrious_v34`
3. `NoobAI-XL`

If the required plus-face file is still missing, stop before benchmarking and fix the model install first.
