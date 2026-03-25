# HollowForge 즐겨찾기 분석 리포트
**기준일:** 2026-02-24 | **샘플:** 59건 (DB 직접 조회)

---

## 1. 체크포인트 선호도

| 순위 | 체크포인트 | 즐찾 | 비율 |
|------|-----------|------|------|
| 1 | `waiIllustriousSDXL_v160` | 21 | 36% |
| 2 | `animayhemPaleRider_v2TrueGrit` | 11 | 19% |
| 3 | `autismmixSDXL_autismmixConfetti` | 7 | 12% |
| 4 | `akiumLumenILLBase_base` | 6 | 10% |
| 5 | `waiIllustriousSDXL_v140` | 4 | 7% |
| 5 | `prefectIllustriousXL_v60` | 4 | 7% |
| 7 | `ultimateHentaiAnimeRXTRexAnime_rxV1` | 3 | 5% |
| 8 | `ponyDiffusionV6XL_v6StartWithThisOne` | 2 | 3% |

**주요 인사이트:**
- WAI v160이 36%로 압도적 1위. 핵심 주력 모델.
- animayhemPaleRider가 2위(19%)로 예상 외 강세. Pony 계열보다 우수.
- ponyRealism은 즐겨찾기 0건 → 생산 파이프라인에서 제외 권장.

---

## 2. LoRA 선호도

### 전체 LoRA 등장 빈도

| LoRA | 등장 | 권장 Strength |
|------|------|--------------|
| `incase_new_style_red_ill` | **26회** | 0.65~0.75 |
| `plumpill` | **20회** | 0.70~0.85 |
| `DetailedEyes_V3` | 14회 | 0.50~0.60 |
| `IckpotIXL_v1` | 10회 | **0.20~0.45** (낮게) |
| `Harness_Panel_Gag_IL` | 10회 | 0.60~0.70 |
| `iranon` | 7회 | 0.35~0.65 |
| `PonyXL - Natural Large Areolae` | 7회 | 0.50 |
| `Drool-IL` | 7회 | 0.50 |
| `Shiny_Clothes_and_Skin_Latex_Illustrious` | 5회 | 0.55~0.60 |
| `Eyes_for_Illustrious_Lora_Perfect_anime_eyes` | 5회 | 0.60~0.70 |

### 황금 조합 (체크포인트별)

**WAI v160 최다 즐찾 조합 (4회):**
```
DetailedEyes_V3(0.5) + Shiny_Clothes_Latex(0.6) + incase_new_style_red_ill(0.7) + plumpill(0.6~0.8)
```

**WAI v160 서브 조합 (3회):**
```
DetailedEyes_V3(0.5) + incase_new_style_red_ill(0.7) + plumpill(0.7)
```

**WAI v140 최다 조합 (3회):**
```
IckpotIXL_v1(0.25~0.4) + incase_new_style_red_ill(0.65~0.85) + iranon(0.4~0.65)
```

**autismmixSDXL 최다 조합 (3회):**
```
incase_new_style_red_ill(0.5~0.6) + plumpill(0.6~0.8)
```

**akiumLumenILLBase 최다 조합 (4회):**
```
plumpill(0.7~1.0) 단독
```

---

## 3. 기술 설정 스위트 스팟

| 파라미터 | 권장값 | 세부 분포 |
|---------|--------|----------|
| **Steps** | 28~30 | 28(47%), 30(42%) — 거의 동등 |
| **CFG** | 5.5~7.0 | avg **5.85** / 5.0(27%), 6.0(22%), 7.0(17%) |
| **Sampler** | `euler_ancestral` | 71% 압도적 1위 |
| **해상도** | `832×1216` | 78%(46/59) — 세로 portrait 기본 |
| **LoRA avg Strength** | 0.60 | incase: 0.7 / plumpill: 0.7~0.8 / IckpotIXL: 0.2~0.4 |

**CFG 참고:** 이전 예상(5.0~5.5)보다 높은 5.5~7.0이 실제 즐찾에 많음.
특히 akiumLumenILLBase + plumpill 조합은 cfg=6.0~7.5 구간에서 좋은 결과.

---

## 4. 캐릭터 & 신체 방향성

### 신체 타입 선호 (즐찾 내 등장 빈도)

| 키워드 | 건수 | 비율 |
|--------|------|------|
| `plump` | **16** | 27% |
| `thick thighs` | **14** | 24% |
| `nipple` (노출) | 12 | 20% |
| `pussy` (노출) | 11 | 19% |
| `armpit hair` | 11 | 19% |
| `wide hips` / `bottom heavy` | 10각 | 17% |
| `bushy pubic hair` | 9 | 15% |
| `big breasts` | 9 | 15% |
| `skindentation` | 8 | 14% |
| `hairy anus` / `anal hair` | 7 | 12% |

→ **통통/하체 비대 체형(plump + thick thighs + wide hips)이 핵심 선호.**
→ plumpill LoRA 20회 사용과 완전히 일치 — 이 LoRA는 사실상 필수.

---

## 5. 포즈 & 복장 & 배경

### 포즈 / 앵글

| 키워드 | 건수 |
|--------|------|
| `squat` / `squatting` | **12** |
| `sitting` | 9 |
| `presenting` | 8 |
| `wide spread` (legs) | 6 |
| `from behind` / `bent over` / `pov` / `kneeling` | 5각 |
| `from behind` / `looking back` | 5 / 4 |

→ **스쿼트 포즈가 압도적 1위.** 로우앵글 + 스프레드 조합이 핵심.

### 복장 / 소재

| 키워드 | 건수 |
|--------|------|
| `latex` | **16** |
| `naked` / `stockings` | 11각 |
| `bikini` / `harness` / `fishnet` | 8각 |
| `swimsuit` / `bdsm` / `bodysuit` | 5~6 |

→ **라텍스(16) + 스타킹(11) + 피쉬넷(8) 조합이 복장의 핵심 트리오.**
→ 하네스/BDSM 테마(8건)도 유의미한 선호.

### 배경 / 분위기

| 키워드 | 건수 |
|--------|------|
| `shower` / `neon` / `dramatic` | 9각 |
| `cinematic` | 7 |
| `cyberpunk` / `dungeon` | 6각 |
| `fantasy` / `poolside` | 4각 |

→ **샤워씬, 네온/사이버펑크, 던전** 3가지가 배경 선호의 핵심.

---

## 6. 프롬프트 황금 템플릿

### WAI v160 기본 (범용)

```
score_9, score_8_up, source_anime, rating_explicit,
1girl, solo,

[포즈: squat / presenting / wide spread legs],

(plump:1.2), thick thighs, wide hips, bottom heavy, big breasts,
skindentation, nipple, cameltoe,
(bushy pubic hair:1.2), (armpit hair:1.2),

latex / fishnet stockings / naked,
[배경: neon + dramatic / shower + cinematic / dark dungeon],

masterpiece, highres
```

**LoRA:** `incase_new_style_red_ill(0.7)` + `plumpill(0.75)` + `DetailedEyes_V3(0.5)`
**Steps:** 28~30 | **CFG:** 6.0 | **Sampler:** euler_ancestral | **해상도:** 832×1216

---

### animayhemPaleRider (서브)

```
score_9, score_8_up, source_anime, rating_explicit,
1girl, solo,

[포즈: from behind / bent over / presenting],

big breasts, wide hips, bottom heavy,
naked / harness / bikini,
(bushy pubic hair:1.2), (armpit hair:1.2),

[배경: dramatic / cinematic / poolside],

masterpiece
```

**LoRA:** `incase_new_style_red_ill(0.65)` 또는 `PonyXL - Natural Large Areolae(0.5)`
**Steps:** 30~34 | **CFG:** 5.5~6.5 | **Sampler:** euler_ancestral | **해상도:** 832×1216

---

### BDSM/하네스 특화 (prefectIllustriousXL or ultimateHentai)

```
score_9, score_8_up, source_anime, rating_explicit,
1girl, solo,

leather harness, bdsm, suspended / spread eagle / kneeling,
completely naked, (bushy pubic hair:1.2), (armpit hair:1.2),
tears, blush,

dark dungeon, dramatic lighting, masterpiece
```

**LoRA:** `Harness_Panel_Gag_IL(0.65)` + `incase_new_style_red_ill(0.5)`
**Steps:** 28~30 | **CFG:** 5.5~6.0 | **Sampler:** euler_ancestral | **해상도:** 832×1216

---

## 7. 제외 권장 (즐찾 0건)

- `ponyRealism_V22` — 생성량 대비 즐찾 0. 파이프라인 제외.
- `noobaiXlVpredV10.0zE1` — 즐찾 0 (방금 배치에 포함되어 추가 검증 필요).

---

*생성: 2026-02-24 | HollowForge 즐겨찾기 59건 DB 직접 분석*
