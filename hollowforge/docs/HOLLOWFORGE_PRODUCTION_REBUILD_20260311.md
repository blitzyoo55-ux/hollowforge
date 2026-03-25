# HollowForge Production Rebuild — 2026-03-11

## Summary

- HollowForge now pivots to a lane-based generation path instead of a single generic SDXL-style graph.
- Phase 1 keeps the current local checkpoint stack and upgrades the SDXL production lane first.
- No new model download is required for Phase 1.
- Low-signal local checkpoint `oneObsession_v19Atypical.safetensors` has been removed from the active inventory.

## Current Local Inventory

### Checkpoints currently present in ComfyUI

- `akiumLumenILLBase_baseV2.safetensors`
- `animayhemPaleRider_v2TrueGrit.safetensors`
- `autismmixSDXL_autismmixConfetti.safetensors`
- `hassakuXLIllustrious_v34.safetensors`
- `illustrij_v20.safetensors`
- `prefectIllustriousXL_v70.safetensors`
- `ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors`
- `waiIllustriousSDXL_v140.safetensors`
- `waiIllustriousSDXL_v160.safetensors`

### LoRA / VAE state

- Local LoRAs: `47`
- Local VAE present: `sdxl_vae.safetensors`
- Missing architecture stacks for future lanes:
  - `SDXL refiner`
  - `Qwen-Image` diffusion/text-encoder stack
  - `FLUX` stack

## Keep / Secondary / Prune

### Keep — production core

These checkpoints already have enough favorite support to stay in the main benchmark pool.

- `waiIllustriousSDXL_v160.safetensors` — `564 total / 184 favorites / 15 ready`
- `prefectIllustriousXL_v70.safetensors` — `297 total / 120 favorites / 5 ready`
- `animayhemPaleRider_v2TrueGrit.safetensors` — `385 total / 117 favorites / 10 ready`
- `hassakuXLIllustrious_v34.safetensors` — `266 total / 86 favorites / 2 ready`
- `ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors` — `181 total / 73 favorites / 6 ready`

### Keep — secondary benchmark pool

- `waiIllustriousSDXL_v140.safetensors` — still materially used; keep until the rebuilt lane is rebenchmarked.
- `akiumLumenILLBase_baseV2.safetensors` — moderate usage and favorite support.
- `autismmixSDXL_autismmixConfetti.safetensors` — high average quality score; keep as a contrast lane.
- `illustrij_v20.safetensors` — good average quality score but weaker publish conversion; keep for comparison only.

### Pruned

- `oneObsession_v19Atypical.safetensors`
  - `11 total / 2 favorites / 0 ready`
  - removed from the active local checkpoint set

## Legacy / No-action rows

The database still contains historical generations referencing old checkpoints that are not in the current local checkpoint directory. These do not require disk cleanup right now.

- `akiumLumenILLBase_base.safetensors`
- `prefectIllustriousXL_v60.safetensors`
- `ponyDiffusionV6XL_v6StartWithThisOne.safetensors`
- `ponyRealism_V22.safetensors`
- `noobaiXlVpredV10.0zE1.safetensors`
- `lunarcherrymix_v24.safetensors`
- `juggernautXL_ragnarokBy.safetensors`
- `ultrarealFineTune_v4.safetensors`
- `flux1-dev.safetensors`
- `realisticVisionV60B1_v51HyperVAE.safetensors`
- `sdxlLightning_1Step.safetensors`
- `svd_xt.safetensors`

## Added Architecture

### Lane 1 — `sdxl_illustrious`

- Dual-encoder SDXL conditioning via `CLIPTextEncodeSDXL`
- defaults:
  - sampler: `euler_ancestral`
  - steps: `30`
  - cfg: `5.5`
  - clip_skip: `2`
  - resolution: `832x1216`
  - default LoRA count: `2`

### Lane 2 — future only

- `Qwen-Image` for text-heavy cover, poster, and controlled edit work
- not required for the current rebuild

## Recommended Additional Models

### Not required now

Phase 1 can run entirely on the currently installed SDXL-family checkpoints and LoRAs.

### Optional next downloads

1. `stabilityai/stable-diffusion-xl-refiner-1.0`
   - use: curated finishing lane only
   - source: Hugging Face
   - login needed: no
   - link: https://huggingface.co/stabilityai/stable-diffusion-xl-refiner-1.0

2. `OnomaAIResearch/Illustrious-XL-v2.0`
   - use: fresh official Illustrious baseline for rebenchmarking
   - source: Hugging Face
   - login needed: no
   - link: https://huggingface.co/OnomaAIResearch/Illustrious-XL-v2.0

3. `Qwen/Qwen-Image`
   - use: future cover / typography / structured scene lane
   - source: Hugging Face
   - login needed: no
   - link: https://huggingface.co/Qwen/Qwen-Image

### Civitai login requirement

- Not required for the current rebuild.
- Only use Civitai later if you intentionally want new community merges or niche LoRAs beyond the current local library.

## Recommended Next Steps

1. Run the rebuilt SDXL lane on the current production-core checkpoints only.
2. Rebenchmark publishable yield on:
   - `prefectIllustriousXL_v70`
   - `animayhemPaleRider_v2TrueGrit`
   - `waiIllustriousSDXL_v160`
   - `hassakuXLIllustrious_v34`
3. Use `POST /api/v1/tools/prompt-factory/generate-and-queue` for the simplest operator flow.
4. Add `SDXL refiner` only after the new baseline is stable.
