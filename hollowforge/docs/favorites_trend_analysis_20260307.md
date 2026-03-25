# HollowForge Favorites — Generation Detail & Trend Analysis

**Generated:** 2026-03-07
**Total Favorites:** 798 images
**Date Range:** 2026-02-17 ~ 2026-03-06 (18 days)

---

## 1. Checkpoint Distribution

| Checkpoint | Count | Share |
|---|---|---|
| waiIllustriousSDXL_v160 | 180 | 22.6% |
| prefectIllustriousXL_v70 | 115 | 14.4% |
| animayhemPaleRider_v2TrueGrit | 109 | 13.7% |
| hassakuXLIllustrious_v34 | 83 | 10.4% |
| ultimateHentaiAnimeRXTRexAnime_rxV1 | 66 | 8.3% |
| waiIllustriousSDXL_v140 | 62 | 7.8% |
| illustrij_v20 | 54 | 6.8% |
| akiumLumenILLBase_baseV2 | 54 | 6.8% |
| autismmixSDXL_autismmixConfetti | 47 | 5.9% |
| akiumLumenILLBase_base | 13 | 1.6% |
| prefectIllustriousXL_v60 | 9 | 1.1% |
| ponyDiffusionV6XL_v6 | 4 | 0.5% |
| oneObsession_v19Atypical | 2 | 0.3% |

**Key insight:** WAI v160 tops favorites at 22.6% despite earlier analysis ranking it 4th for raw quality (68.5 avg). This is likely a volume effect — WAI v160 was the most-used model overall. prefect v70 and PaleRider both punch above their generation share, indicating genuine quality-per-image superiority.

---

## 2. Top LoRAs (by frequency in favorites)

| LoRA | Appearances | % of favorites |
|---|---|---|
| FullCoverLatexMask.safetensors | 167 | 20.9% |
| incase_new_style_red_ill.safetensors | 159 | 19.9% |
| latex_hood_illustrious.safetensors | 119 | 14.9% |
| GEN(illust) 0.2v.safetensors | 96 | 12.0% |
| plumpill.safetensors | 86 | 10.8% |
| tkt_style.safetensors | 65 | 8.1% |
| Face_Enhancer_Illustrious.safetensors | 63 | 7.9% |
| DetailedEyes_V3.safetensors | 60 | 7.5% |
| 1-A_Dot_AI_Style__NSFW_v2.safetensors | 55 | 6.9% |
| Drool-IL.safetensors | 54 | 6.8% |
| sxdll-000007.safetensors | 48 | 6.0% |
| tomioka_sena-000010.safetensors | 47 | 5.9% |
| Okaze.safetensors | 46 | 5.8% |
| iranon.safetensors | 38 | 4.8% |
| [Artstyle] SomethingWeird_Geekpower.safetensors | 38 | 4.8% |

**LoRA count per image:**
- 0 LoRAs: 6 images (0.8%)
- 1 LoRA: 149 images (18.7%)
- 2 LoRAs: 588 images (73.7%) — dominant pattern
- 3 LoRAs: 13 images (1.6%)
- 4 LoRAs: 42 images (5.3%)

**LoRA strength range:** 0.20–1.00, avg **0.58**

**Key insight:** 2-LoRA combination is overwhelmingly preferred (73.7%). The latex-focused LoRAs (FullCoverLatexMask, latex_hood_illustrious) appear in ~35% of all favorites, confirming latex mask as the core identity motif. incase_new_style_red_ill is the second most common style LoRA, suggesting its distinctive line art style resonates strongly with the brand aesthetic.

---

## 3. Sampling Parameters

### CFG Scale
| CFG | Count |
|---|---|
| 4.5 | 106 |
| 5.0 | 271 (34.0%) — dominant |
| 5.5 | 93 |
| 6.0 | 234 (29.3%) |
| 6.5 | 27 |
| 7.0 | 38 |
| 7.5+ | 12 |

**Avg CFG: 5.47**
Sweet spot: **5.0–6.0** (66.7% of all favorites). CFG≥7 is rare (6.3%), indicating low classifier guidance favors softer, more natural results for this style.

### Steps
| Steps | Count |
|---|---|
| 28 | 80 |
| 30 | 347 (43.5%) — dominant |
| 32 | 45 |
| 35 | 246 (30.8%) |
| 38 | 10 |
| 40 | 47 |
| 45 | 6 |

**Dominant:** 30 steps (43.5%) and 35 steps (30.8%). Together these cover 74.3% of all favorites. 40+ steps add marginal benefit at higher compute cost.

### Sampler
| Sampler | Count | % |
|---|---|---|
| euler_a | 498 | 62.4% |
| dpmpp_2m | 170 | 21.3% |
| dpmpp_2m_sde | 78 | 9.8% |
| euler_ancestral | 41 | 5.1% |
| euler | 11 | 1.4% |

**euler_a dominates** at 62.4%. Its stochastic behavior introduces creative variation, which pairs well with the expressive illustrious style checkpoints.

### Scheduler
- `normal`: 788 (98.7%)
- `karras`: 8 (1.0%)
- `simple`: 2 (0.3%)

**normal scheduler is standard** across all favorites.

### Clip Skip
- `clip_skip=2`: 494 (61.9%)
- Not set (None): 304 (38.1%)

Clip skip 2 is the explicit preference for Illustrious-based models, which is consistent with best-practice recommendations.

---

## 4. Resolution

| Resolution | Count | % |
|---|---|---|
| 832×1216 (portrait) | 761 | 95.4% |
| 896×1152 (tall portrait) | 18 | 2.3% |
| 1216×832 (landscape) | 12 | 1.5% |
| 1024×1024 (square) | 7 | 0.9% |

**832×1216 portrait is the canonical format** (95.4%). This is consistent with the target platform (Pixiv/SubscribeStar vertical scroll optimized).

---

## 5. Quality Scores

Both quality_score (manual) and quality_ai_score are populated for 746 of 798 favorites (93.5%).

| Metric | Min | Max | Avg |
|---|---|---|---|
| Manual quality_score | 38 | 100 | **85.7** |
| AI quality_ai_score | 38 | 100 | **86.9** |

**Score distribution peaks at 90–96** — indicating the favorites collection is consistently high quality, not a random sample. The long tail below 75 (≈70 images) likely reflects early-iteration or experimental pieces kept for reference.

**Score bracket breakdown (manual):**
- ≥95: 104 images (13.9%)
- 90–94: 212 images (28.4%)
- 85–89: 147 images (19.7%)
- 80–84: 88 images (11.8%)
- 75–79: 51 images (6.8%)
- <75: 144 images (19.3%)

---

## 6. Prompt Theme Analysis

| Theme / Keyword | Count | % |
|---|---|---|
| `solo` | 796 | 99.7% |
| `score_9` (quality tag) | 786 | 98.5% |
| `latex` (any) | 381 | 47.7% |
| `lab-451` brand tag | 286 | 35.8% |
| `latex mask` | 187 | 23.4% |
| `drone` (faceless drone) | 186 | 23.3% |
| `full cover latex mask` | 185 | 23.2% |
| `faceless` | 185 | 23.2% |
| `unit-xx` | 164 | 20.6% |
| `harness` | 152 | 19.0% |
| `explicit nudity` | 124 | 15.5% |
| `neon` | 103 | 12.9% |
| `bondage` | 91 | 11.4% |

**Key insight:** Brand consistency is strong — `lab-451` appears in 35.8% and `unit-xx` in 20.6% of favorites. The core faceless latex drone identity is coherent. `explicit nudity` appears in only 15.5%, suggesting the non-explicit aesthetic (masked/covered) may be equally or more preferred.

---

## 7. Temporal Trend

| Month | Favorites |
|---|---|
| 2026-02 | 376 (47.1%) |
| 2026-03 | 422 (52.9%) |

The project accelerated into March. Given the date range ends on 2026-03-06 (only 6 days into March vs 11 days of Feb from the 17th), March is generating favorites at a **significantly higher daily rate** (~70/day vs ~34/day in Feb).

---

## 8. Upscale Status

| Status | Count |
|---|---|
| Upscaled | **2** (0.25%) |
| Not upscaled | 796 (99.75%) |

Virtually no favorites have been upscaled. With auto-upscale on favorite now implemented, this pipeline will activate going forward.

---

## 9. Optimal Generation Recipe (from favorites data)

Based on the above analysis, the configuration that maximizes favorite selection probability:

```
Checkpoint:   prefectIllustriousXL_v70 or animayhemPaleRider_v2TrueGrit
LoRAs:        2 LoRAs — FullCoverLatexMask (0.5–0.7) + style LoRA (incase/tkt/GEN)
CFG:          5.0–6.0
Steps:        30 or 35
Sampler:      euler_a
Scheduler:    normal
Resolution:   832×1216
Clip Skip:    2
Core prompt:  score_9, score_8_up, solo, lab-451, full cover latex mask, faceless drone
```

**Models to deprioritize:** waiIllustriousSDXL_v140 and ponyDiffusionV6XL (low favorite/generation ratio relative to their usage volume).

**Models to increase usage:** prefectIllustriousXL_v70 and animayhemPaleRider_v2TrueGrit both show strong quality-to-volume ratios.

---

## 10. Recommended Next Actions

1. **Auto-upscale pipeline now active** — all future favorites will be upscaled via remacri 4x automatically
2. **Batch upscale backlog** — 796 existing favorites are unupscaled; consider queuing in batches of 50 to avoid ComfyUI queue saturation
3. **Retire WAI v140** — superseded by v160; remove from rotation
4. **Increase PaleRider proportion** — currently 13.7% of favorites from likely lower generation share; increase allocation
5. **Non-explicit set** — 84.5% of favorites do NOT contain `explicit nudity` keyword, yet contain strong brand identity. This subset (~674 images) may have higher Pixiv approval rate
6. **Score filter for publishing** — recommend ≥85 threshold (≈507 images, 63.5% of favorites) as the publish-ready pool
