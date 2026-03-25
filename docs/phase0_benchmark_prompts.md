# Phase 0 — Model Benchmark Prompts
**Date:** 2026-02-17

## 목적
동일 프롬프트로 3개 모델의 라텍스 질감·구도·전체 퀄리티를 비교한다.

---

## 테스트 대상 모델

| # | Model | Type | 비고 |
|---|-------|------|------|
| 1 | `waiIllustriousSDXL_v160` | Illustrious SDXL | 애니 스타일, NSFW 지원 |
| 2 | `ponyDiffusionV6XL_v6` | Pony SDXL | NSFW 특화, 태그 체계 다름 |
| 3 | `flux1-schnell-fp8` | Flux.1 Schnell | 범용 고품질, NSFW 제한적 |

**공통 LoRA:** `latex_huger_c7` (weight 0.7~0.8)
**공통 VAE:** `sdxl_vae` (모델 1,2) / `ae` (모델 3)
**해상도:** 832x1216 (세로 구도)
**Steps:** 모델 1,2 = 25 steps / 모델 3 = 4 steps (schnell 특성)

---

## 프롬프트 세트 (5개)

### Prompt A: Basic Latex Suit (기본 라텍스)

**Illustrious/WAI 형식:**
```
masterpiece, best quality, 1girl, solo, mature_female, voluptuous,
black latex_suit, full_body, skin_tight, shiny, glossy,
standing, looking_at_viewer,
laboratory, white_tiles, fluorescent_light,
no_face, gas_mask, black_gloves
```

**Pony 형식:**
```
score_9, score_8_up, score_7_up, source_anime, rating_explicit,
1girl, solo, mature_female, voluptuous,
black latex_suit, full_body, skin_tight, shiny, glossy,
standing, looking_at_viewer,
laboratory, white_tiles, fluorescent_light,
no_face, gas_mask, black_gloves
```

**Flux 형식 (자연어):**
```
A voluptuous mature woman in a skin-tight glossy black latex full-body suit,
wearing a black gas mask covering her entire face. She stands in a sterile
white-tiled laboratory under fluorescent lights. The latex suit has an
extremely shiny, reflective surface. Black latex gloves.
Anime art style, high detail, dramatic lighting.
```

**Negative (공통):**
```
lowres, bad anatomy, bad hands, text, error, worst quality, low quality,
child, loli, flat_chest, school_uniform, nude, nipples, genitals
```

---

### Prompt B: BDSM Collar + Leash (구속 상황)

**Illustrious/WAI:**
```
masterpiece, best quality, 1girl, solo, mature_female, voluptuous,
black latex_suit, catsuit, skin_tight, shiny, glossy,
collar, leash, kneeling, arms_behind_back,
dungeon, concrete_wall, dim_lighting, chains,
latex_mask, full_face_mask, faceless
```

**Pony:**
```
score_9, score_8_up, score_7_up, source_anime, rating_explicit,
1girl, solo, mature_female, voluptuous,
black latex_suit, catsuit, skin_tight, shiny, glossy,
collar, leash, kneeling, arms_behind_back,
dungeon, concrete_wall, dim_lighting, chains,
latex_mask, full_face_mask, faceless
```

**Flux:**
```
A voluptuous mature woman wearing a glossy black latex catsuit that covers
her entire body, with a full-face latex mask making her faceless.
She kneels with arms behind her back in a dark concrete dungeon.
A leather collar with a leash around her neck. Chains hang from the walls.
Dim dramatic lighting. Anime art style.
```

---

### Prompt C: Cyberpunk Neon (네온 거리)

**Illustrious/WAI:**
```
masterpiece, best quality, 1girl, solo, mature_female, voluptuous,
black_and_orange latex_suit, skin_tight, shiny, glossy,
cyberpunk, neon_lights, rain, wet, night_city,
gas_mask, standing, hand_on_hip, confident_pose,
reflection, puddle, neon_sign
```

**Pony:**
```
score_9, score_8_up, score_7_up, source_anime, rating_explicit,
1girl, solo, mature_female, voluptuous,
black_and_orange latex_suit, skin_tight, shiny, glossy,
cyberpunk, neon_lights, rain, wet, night_city,
gas_mask, standing, hand_on_hip,
reflection, puddle, neon_sign
```

**Flux:**
```
A voluptuous mature woman in a skin-tight black and orange latex suit
with extremely glossy reflective surface. She wears a gas mask covering
her face. Standing confidently in a rainy cyberpunk night city street,
neon signs reflecting in wet puddles. Rain droplets on the shiny latex.
Anime art style, vibrant neon colors.
```

---

### Prompt D: Gag + Blindfold (BDSM 고EE)

**Illustrious/WAI:**
```
masterpiece, best quality, 1girl, solo, mature_female, voluptuous,
black latex_suit, skin_tight, shiny, glossy,
ball_gag, blindfold, collar, bound_wrists,
latex_gloves, thigh_highs, high_heels,
dungeon, spotlight, dark_background
```

**Pony:**
```
score_9, score_8_up, score_7_up, source_anime, rating_explicit,
1girl, solo, mature_female, voluptuous,
black latex_suit, skin_tight, shiny, glossy,
ball_gag, blindfold, collar, bound_wrists,
latex_gloves, thigh_highs, high_heels,
dungeon, spotlight, dark_background
```

**Flux:**
```
A voluptuous mature woman in a skin-tight glossy black latex bodysuit
with long black latex gloves and black thigh-high latex stockings with
high heels. She wears a ball gag in her mouth and a blindfold over her
eyes, with a leather collar around her neck and wrists bound.
In a dark dungeon illuminated by a single spotlight. Anime art style.
```

---

### Prompt E: Soft Entry - Leotard (Phase 3 Preview)

**Illustrious/WAI:**
```
masterpiece, best quality, 1girl, solo, mature_female, voluptuous,
black leotard, thigh_highs, high_heels,
shiny, glossy, skin_tight,
mask, half_mask, mysterious,
bedroom, mood_lighting, curtains,
sitting, crossed_legs, elegant_pose
```

**Pony:**
```
score_9, score_8_up, score_7_up, source_anime, rating_explicit,
1girl, solo, mature_female, voluptuous,
black leotard, thigh_highs, high_heels,
shiny, glossy, skin_tight,
mask, half_mask, mysterious,
bedroom, mood_lighting, curtains,
sitting, crossed_legs
```

**Flux:**
```
A voluptuous mature woman wearing a glossy black leotard with black
thigh-high stockings and high heels. She wears a mysterious half-mask
covering the upper half of her face. Sitting elegantly with crossed legs
in a dimly lit bedroom with flowing curtains. The leotard has a shiny,
latex-like material. Anime art style, elegant mood.
```

---

## 평가 기준

| 기준 | 가중치 | 설명 |
|------|--------|------|
| 라텍스 질감 | 30% | 광택, 반사, 타이트핏 표현 |
| 마스크/Faceless | 20% | 얼굴 가림 정확도 |
| 체형 일관성 | 15% | mature, voluptuous 반영도 |
| 배경 퀄리티 | 15% | 프롬프트 대비 배경 정확도 |
| 구도/포즈 | 10% | 자연스러움, 매력도 |
| 생성 속도 | 10% | Mac mini 24GB 기준 소요시간 |

---

## 실행 방법

1. Pinokio에서 ComfyUI 실행
2. 각 모델별로 Prompt A~E × 2장씩 = **30장 생성** (3모델 × 5프롬프트 × 2장)
3. 파일명 규칙: `benchmark_{model}_{prompt}_{n}.png`
   - 예: `benchmark_wai160_A_1.png`
4. 생성 후 평가표 작성 → 최적 모델+LoRA 조합 확정

*소요 예상: 약 1~2시간 (배치 생성 시)*
