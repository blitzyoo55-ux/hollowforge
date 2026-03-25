# Rule34 태그 시장 분석 리포트 v2 (2026-02-17)

- 데이터 기준 시점:
  - `data/full_tag_ranking_20260216_1551.csv` (1000개 태그, 메인)
  - `data/tag_stats_20260216_1509.csv` (32개 타깃 태그, 보강)
- 해석 주의:
  - `post_count`는 태그별 중복 집계(동일 포스트가 여러 태그에 포함)라 전체 합은 실제 총 포스트 수가 아님.
  - `full_tag_ranking`에 없는 일부 니치 태그(`latex_suit`, `novelai` 등)는 `tag_stats` 수치로 보강.

## 1. 전체 시장 개요

- 총 수집 태그 수: **1000개**

### 1-1. 상위 20개 태그 (post_count 기준)

| 순위 | 태그 | post_count | avg_score |
|---:|---|---:|---:|
| 1 | breasts | 7,604,140 | 0.9 |
| 2 | penis | 5,056,181 | 2.0 |
| 3 | nipples | 4,108,088 | 2.7 |
| 4 | solo | 3,789,370 | 2.7 |
| 5 | pussy | 3,749,370 | 1.9 |
| 6 | ass | 3,592,202 | 1.8 |
| 7 | nude | 3,509,508 | 3.1 |
| 8 | big_breasts | 3,265,003 | 2.1 |
| 9 | sex | 2,686,659 | 3.2 |
| 10 | 1boy | 2,660,132 | 2.1 |
| 11 | ai_generated | 2,583,305 | 0.5 |
| 12 | cum | 2,528,252 | 4.0 |
| 13 | long_hair | 2,466,412 | 0.8 |
| 14 | thick_thighs | 2,252,096 | 3.3 |
| 15 | balls | 2,240,756 | 0.9 |
| 16 | huge_breasts | 1,974,485 | 2.6 |
| 17 | big_ass | 1,640,074 | 1.1 |
| 18 | blonde_hair | 1,448,080 | 3.3 |
| 19 | black_hair | 1,393,197 | 2.4 |
| 20 | tongue | 1,351,637 | 4.9 |

### 1-2. 카테고리별 분류 (대표 태그 묶음 합산)

| 카테고리 | 대표 태그 수 | 대표 태그 합산 post_count | 가중 avg_score | 대표 태그 예시 |
|---|---:|---:|---:|---|
| 신체부위 | 9 | 29,858,599 | 2.43 | breasts, penis, nipples, pussy, ass |
| 행위 | 12 | 7,029,837 | 5.06 | sex, cum, bondage, gag, leash, sound |
| 의상/페티시 | 16 | 2,247,740 | 5.84 | latex, latex_suit, mask, lingerie, collar |
| 캐릭터타입 | 8 | 8,993,415 | 3.33 | 1girl, 1boy, solo, futanari, pregnant |
| IP/작품 | 9 | 1,898,608 | 8.90 | pokemon, touhou, fortnite, resident_evil |
| AI관련 | 4 | 2,964,783 | 0.99 | ai_generated, stable_diffusion, novelai |
| 스타일 | 11 | 6,140,705 | 5.59 | animated, anime_style, 3d, sketch, comic |

요약:
- 시장 볼륨은 신체부위/기본 행위 태그가 압도적.
- 반응도는 `IP/작품`, `스타일`, `의상/페티시` 쪽이 상대적으로 높고, `AI관련`은 평균 반응이 낮음.

## 2. 유저 반응도 심층 분석

### 2-1. avg_score TOP 50 (post_count 1,000 이상)

| 순위 | 태그 | post_count | avg_score |
|---:|---|---:|---:|
| 1 | sound | 243,557 | 21.3 |
| 2 | touhou | 128,524 | 18.4 |
| 3 | world_of_warcraft | 103,709 | 17.6 |
| 4 | fortnite | 108,198 | 15.8 |
| 5 | pregnant | 147,974 | 14.2 |
| 6 | age_difference | 146,093 | 13.2 |
| 7 | double_penetration | 121,862 | 13.0 |
| 8 | sideboob | 179,524 | 12.7 |
| 9 | eyebrows | 216,363 | 12.6 |
| 10 | gag | 128,280 | 12.6 |
| 11 | threesome | 232,444 | 11.5 |
| 12 | reverse_cowgirl_position | 119,860 | 11.5 |
| 13 | resident_evil | 88,699 | 11.2 |
| 14 | full_body | 167,408 | 10.9 |
| 15 | leotard | 127,832 | 10.9 |
| 16 | waist | 101,398 | 10.9 |
| 17 | vore | 94,239 | 10.8 |
| 18 | skirt_lift | 100,146 | 10.7 |
| 19 | pubic_hair | 626,649 | 10.2 |
| 20 | no_bra | 210,701 | 10.2 |
| 21 | kissing | 193,329 | 10.2 |
| 22 | leash | 110,587 | 10.0 |
| 23 | animated | 658,375 | 9.2 |
| 24 | no_panties | 240,261 | 9.2 |
| 25 | lingerie | 191,470 | 9.2 |
| 26 | sketch | 157,301 | 9.2 |
| 27 | sucking | 92,437 | 9.2 |
| 28 | green_hair | 337,597 | 8.7 |
| 29 | see-through | 84,172 | 8.7 |
| 30 | licking | 246,710 | 8.6 |
| 31 | cunnilingus | 116,729 | 8.6 |
| 32 | comic | 402,227 | 8.3 |
| 33 | rough_sex | 94,895 | 8.3 |
| 34 | 3girls | 125,091 | 8.2 |
| 35 | from_behind | 396,584 | 8.1 |
| 36 | 2boys | 547,199 | 8.0 |
| 37 | rope | 100,914 | 8.0 |
| 38 | street_fighter | 95,360 | 8.0 |
| 39 | thighs | 1,255,292 | 7.9 |
| 40 | my_hero_academia | 157,883 | 7.9 |
| 41 | dragon_ball | 125,091 | 7.9 |
| 42 | dark_skin | 932,531 | 7.8 |
| 43 | demon_girl | 127,603 | 7.8 |
| 44 | areolae | 889,593 | 7.7 |
| 45 | grey_hair | 183,045 | 7.7 |
| 46 | masturbation | 445,160 | 7.5 |
| 47 | milf | 409,255 | 7.4 |
| 48 | armpits | 279,182 | 7.4 |
| 49 | mosaic_censoring | 290,464 | 7.3 |
| 50 | braid | 175,083 | 7.3 |

### 2-2. 규모 x 반응 매트릭스

- 분석 필터: `post_count >= 1,000` + `sample_size >= 10` (신뢰도 보강)
- 분할 기준:
  - 시장규모 중앙값: **274,554**
  - 반응도 중앙값: **4.8**

| 구분 | 태그 수 | 특징 | 대표 태그 |
|---|---:|---|---|
| 큰 시장 + 고반응 | 33 | 스케일과 반응이 함께 높은 핵심 메인스트림 | thighs(1,255,292/7.9), futanari(1,120,306/6.5), dark_skin(932,531/7.8), animated(658,375/9.2) |
| 큰 시장 + 저반응 | 67 | 공급 과잉, 차별화 없으면 성과 저하 구간 | breasts(7,604,140/0.9), penis(5,056,181/2.0), solo(3,789,370/2.7), big_breasts(3,265,003/2.1) |
| 작은 시장 + 고반응 | 67 | 니치 고효율 구간(실험 우선순위 높음) | sound(243,557/21.3), pregnant(147,974/14.2), touhou(128,524/18.4), leash(110,587/10.0) |
| 작은 시장 + 저반응 | 33 | 우선순위 낮거나 콘셉트 재설계 필요 | swimsuit(272,082/4.3), school_uniform(182,221/4.4), femdom(171,025/4.4) |

## 3. AI 콘텐츠 시장 분석

### 3-1. `ai_generated` vs `stable_diffusion` vs `novelai`

| 태그 | post_count | avg_score | 해석 |
|---|---:|---:|---|
| ai_generated | 2,583,161 | 0.75 | 공급은 압도적이나 반응 저조 |
| stable_diffusion | 347,095 | 0.50 | 범용 SD 태그도 저반응 |
| novelai | 34,273 | 10.35 | 규모는 작지만 반응은 높음 |

### 3-2. AI 태그 vs 비AI 태그 반응도 차이

- (타깃 32개 데이터 기준)
  - AI 코어 3태그(`ai_generated`, `stable_diffusion`, `novelai`) 가중 avg_score: **0.83**
  - 나머지 29태그 가중 avg_score: **2.68**
  - 차이: **-1.85p** (AI 코어가 약 **31% 수준**)

- (1000개 메인 데이터, `novelai` 제외한 AI 코어 3태그 기준)
  - AI(`ai_generated`, `stable_diffusion`, `midjourney`) 가중 avg_score: **0.88**
  - 비AI 997태그 가중 avg_score: **3.65**
  - 차이: **-2.77p**

### 3-3. AI 콘텐츠 강세 카테고리 vs 약세 카테고리

- 강세(상대적):
  - **의상/페티시**: AI 포함 태그군 가중 avg_score **10.04** (`latex_mask`, `latex_suit`, `mask` 등)
  - **행위**: AI 포함 태그군 가중 avg_score **6.99** (`bondage`, `collar`, `blindfold` 등)

- 약세:
  - **AI관련 메타 태그 자체**: 가중 avg_score **0.83** (`ai_generated`, `stable_diffusion`, `novelai`)
  - **범용 캐릭터타입**: AI 포함 태그군 가중 avg_score **1.22** (`1girl`, `solo` 중심)

핵심 해석:
- “AI임”을 전면에 내세우는 태그는 반응이 낮고,
- 의상/페티시/연출 니치와 결합된 AI 결과물이 상대적으로 성과가 좋음.

## 4. 페티시/니치 시장 분석

### 4-1. BDSM/본디지 상세

| 태그 | post_count | avg_score | 비고 |
|---|---:|---:|---|
| bondage | 421,089 | 3.3 | 대형 시장, 반응 중하 |
| bdsm | 66,980 | 4.0 | (타깃32 기준) |
| collar | 417,788 | 3.7 | 규모 큼 |
| leash | 110,587 | 10.0 | 고반응 니치 |
| gag | 128,280 | 12.6 | 고반응 니치 |
| rope | 100,914 | 8.0 | 안정적 고반응 |
| blindfold | 71,036 | 13.1 | (타깃32 기준) 고반응 |

요약:
- `bondage`, `collar`는 볼륨이 크지만 반응이 낮아 연출 디테일이 중요.
- `gag`, `leash`, `blindfold`, `rope`는 반응 우위 태그로 조합 가치가 큼.

### 4-2. 의상 카테고리 상세

| 태그 | post_count | avg_score | 비고 |
|---|---:|---:|---|
| latex | 109,269 | 3.2 | 대중 태그, 반응 보통 이하 |
| latex_suit | 20,921 | 37.5 | (타깃32 기준) 초고반응 |
| rubber | 27,551 | 12.55 | (타깃32 기준) 고반응 |
| leather | 28,191 | 7.9 | (타깃32 기준) 중고반응 |
| stockings | 328,900 | 2.1 | 대형 시장, 반응 낮음 |
| leotard | 127,832 | 10.9 | 고반응 |
| bikini | 442,166 | 4.1 | 대형 시장, 반응 보통 |
| lingerie | 191,470 | 9.2 | 고반응 |
| mask | 130,416 | 17.1 | (타깃32 기준) 고반응 |
| latex_mask | 924 | 26.6 | (타깃32 기준) 니치 고반응 |
| gas_mask | 7,745 | 19.4 | (타깃32 기준) 니치 고반응 |

요약:
- `latex` 단일 태그보다 `latex_suit`/`latex_mask`/`gas_mask` 조합형이 효율이 좋음.

### 4-3. 특수 페티시

| 태그 | post_count | avg_score | 해석 |
|---|---:|---:|---|
| pregnant | 147,974 | 14.2 | 중형 규모 + 매우 높은 반응 |
| vore | 94,239 | 10.8 | 니치 고반응 |
| futanari | 1,120,306 | 6.5 | 대형 규모 + 준수 반응 |
| tentacles | 43,376 | 0.0 | 데이터상 반응 저조/표본 불안정 |

### 4-4. 콤보 태그 분석 (수정판)

- 데이터:
  - `data/combo_primary_20260216_1601.csv` (Primary x Primary)
  - `data/combo_cross_20260216_1625.csv` (Primary x Secondary)
- 역순 중복 제거 규칙:
  - `tag_a + tag_b`와 `tag_b + tag_a`를 동일 조합으로 통합.
  - 동일 조합 중복 발생 시 `post_count`는 최대값 기준으로 사용.
- 정리 결과:
  - Primary x Primary: `182 -> 91` (역순 중복 91쌍 제거)
  - Primary x Secondary: `78 -> 78` (역순 중복 없음)

#### 4-4-1. Top 20 (Primary x Primary, 중복 제거 후)

| 순위 | 콤보 | post_count |
|---:|---|---:|
| 1 | `anime + anime_style` | 46,574 |
| 2 | `latex + latex_gloves` | 22,548 |
| 3 | `bodysuit + latex` | 18,568 |
| 4 | `latex + latex_suit` | 16,834 |
| 5 | `bodysuit + mask` | 9,784 |
| 6 | `latex + rubber` | 8,084 |
| 7 | `bodysuit + latex_suit` | 7,331 |
| 8 | `latex + mask` | 6,466 |
| 9 | `latex_gloves + latex_suit` | 4,983 |
| 10 | `gas_mask + mask` | 4,830 |
| 11 | `bodysuit + rubber` | 3,805 |
| 12 | `bodysuit + latex_gloves` | 3,050 |
| 13 | `latex_suit + rubber` | 2,260 |
| 14 | `mask + rubber` | 2,182 |
| 15 | `bodysuit + catsuit` | 2,175 |
| 16 | `latex_gloves + rubber` | 2,103 |
| 17 | `latex_gloves + mask` | 1,705 |
| 18 | `gas_mask + latex` | 1,637 |
| 19 | `latex_suit + mask` | 1,430 |
| 20 | `catsuit + latex` | 1,372 |

#### 4-4-2. Top 20 (Primary x Secondary, 중복 제거 후)

| 순위 | 콤보 | post_count |
|---:|---|---:|
| 1 | `ai_generated + latex` | 27,454 |
| 2 | `bondage + latex` | 20,250 |
| 3 | `bdsm + latex` | 20,250 |
| 4 | `collar + latex` | 14,959 |
| 5 | `high_heels + latex` | 11,036 |
| 6 | `gag + latex` | 8,976 |
| 7 | `latex + stockings` | 8,419 |
| 8 | `ai_generated + latex_suit` | 5,892 |
| 9 | `ai_generated + latex_gloves` | 5,680 |
| 10 | `latex + thigh_highs` | 5,119 |
| 11 | `latex + stable_diffusion` | 4,658 |
| 12 | `collar + latex_gloves` | 4,545 |
| 13 | `bondage + latex_gloves` | 4,454 |
| 14 | `bdsm + latex_gloves` | 4,454 |
| 15 | `corset + latex` | 3,764 |
| 16 | `latex + leather` | 3,750 |
| 17 | `bondage + latex_suit` | 3,640 |
| 18 | `bdsm + latex_suit` | 3,640 |
| 19 | `high_heels + latex_gloves` | 3,583 |
| 20 | `latex_gloves + stockings` | 3,197 |

#### 4-4-3. 프로젝트 타겟 관련 콤보 점검 (`latex full_face_mask bishoujo`)

| 콤보 | post_count | 해석 |
|---|---:|---|
| `latex + mask` | 6,466 | 마스크 결합 라텍스 수요는 확인됨 |
| `latex + latex_mask` | 773 | 니치하지만 실존 수요 구간 |
| `gas_mask + latex` | 1,637 | 풀페이스 대체 콘셉트 확장 가능 |
| `latex + full_face_mask` | 1 | 현재 데이터상 극저공급 |
| `mask + full_face_mask` | 1 | 사실상 미개척 조합 |
| `latex + bishoujo` | 0 | 직접 결합 데이터 부재 |
| `bishoujo + mask` | 0 | 직접 결합 데이터 부재 |
| `bishoujo + full_face_mask` | 0 | 직접 결합 데이터 부재 |

전략 인사이트(공급 관점):
- 고공급(포화) 구간: `bondage + latex(20,250)`, `bdsm + latex(20,250)`, `collar + latex(14,959)`, `high_heels + latex(11,036)`은 경쟁 밀도가 높아 콘셉트 차별화가 필수.
- 중공급(안정) 구간: `latex + mask(6,466)`, `gag + latex(8,976)`, `latex + stockings(8,419)`은 진입은 가능하나 연출 품질이 성과를 좌우.
- 저공급(기회) 구간: `latex + latex_mask(773)`, `latex + full_face_mask(1)` 및 `bishoujo` 결합 0건은 타깃 정합성이 높고 선점 여지가 큼.

## 5. 프로젝트 타겟("라텍스 풀페이스 마스크 미소녀") 전략

### 5-1. 콤보 데이터 검증 기반 핵심 타겟 5개

1. `latex + mask + bondage`
- 콤보 근거: `latex+bondage(20,250)`, `latex+mask(6,466)`.
- 해석: 수요는 충분히 검증된 메인 구간. 대신 포화도가 높아 구도/배경/소품 차별화 필수.

2. `latex + mask + collar + gag`
- 콤보 근거: `latex+collar(14,959)`, `latex+gag(8,976)`, `latex+mask(6,466)`.
- 해석: BDSM 디테일을 강화하면 포화 구간에서도 클릭 유도 가능.

3. `latex + mask + high_heels + stockings`
- 콤보 근거: `latex+high_heels(11,036)`, `latex+stockings(8,419)`, `latex+mask(6,466)`.
- 해석: 의상/실루엣 중심의 대중형 확장 조합. 볼륨 확보용 트래픽 라인으로 적합.

4. `latex_suit + latex_gloves + mask + bdsm`
- 콤보 근거: `latex+latex_suit(16,834)`, `latex+latex_gloves(22,548)`, `latex_suit+mask(1,430)`, `bdsm+latex_suit(3,640)`.
- 해석: 라텍스 수트 정체성을 유지하면서 BDSM 연결이 가능한 균형형 조합.

5. `latex + full_face_mask + bishoujo` (선점형 실험 라인)
- 콤보 근거: `latex+full_face_mask(1)`, `latex+bishoujo(0)`, `bishoujo+full_face_mask(0)`, 보조근거 `latex+latex_mask(773)`.
- 해석: 현재 공급이 거의 없는 미개척 구간으로, 프로젝트 타겟 정합성은 가장 높음.

### 5-2. 운영 전략 업데이트 (콤보 반영)

- 듀얼 트랙 운영:
  - 안정 트랙(볼륨): 1~3번 조합으로 노출/트래픽 확보.
  - 선점 트랙(브랜딩): 5번 조합으로 타겟 아이덴티티 구축.
- 포화 구간 차별화:
  - `bondage/bdsm/collar`는 이미 대량 공급 상태이므로, 동일 태그라도 조명/재질/마스크 형태(지퍼, 무안구, 산업형)로 변주 필요.
- 저공급 구간 탐색:
  - `full_face_mask`와 `bishoujo` 결합은 데이터 공백이므로, 초기에는 소량 업로드로 반응 신호를 수집하고 점진 확장.

### 5-3. `sound` 시사점 재정리

- `sound`는 단일 태그 반응도(21.3)가 매우 높지만, 이번 콤보 데이터셋에는 직접 교차 수치가 없음.
- 따라서 `sound`는 2차 실험 변수로 유지하고, 1차는 콤보 검증이 끝난 `latex/mask/bondage` 축에 우선 집중하는 것이 안전함.

## 6. 실행 로드맵

### Phase 1: 이미지 생성 (2주)

- 목표: 라텍스 풀페이스 콘셉트의 고반응 조합 탐색.
- 우선 조합:
  - `latex_suit + latex_mask + 1girl`
  - `latex_suit + gas_mask + bishoujo`
  - `latex + mask + lingerie + high_heels`
- 산출물:
  - 조합당 20~30컷 생성, 표정/구도/배경(실내/산업/네온) 3축 분기.

### Phase 2: 업로드 및 반응 테스트 (2~3주)

- 목표: 태그 조합별 CTR/즐겨찾기/score 효율 측정.
- 운영:
  - 업로드 A/B: `BDSM 계열(tag: collar/leash/gag)` vs `스타일 계열(tag: animated/anime_style)`
  - 메타태그 최소화: `ai_generated` 전면 노출보다 장르/연출 태그 중심.
- KPI:
  - 업로드 48시간 기준 평균 score, 댓글률, 저장률.

### Phase 3: 확장 (4주+)

- 영상 확장:
  - `sound` 강세를 반영해 3~8초 루프 애니메이션/짧은 영상 실험.
- IP 확장:
  - 반응 상위 IP(`touhou`, `world_of_warcraft`, `fortnite`)와 라텍스 마스크 콘셉트 결합 테스트.
- 니치 확장:
  - `pregnant`, `vore` 등 고반응 니치를 별도 라인으로 분기해 리스크 분산.

## 최종 결론

- 대형 범용 태그(신체부위/기본 행위/AI메타)는 이미 경쟁 과밀이며 반응 우위가 약함.
- 본 프로젝트의 실전 승부처는 **라텍스/마스크/BDSM/사운드 결합형 니치**.
- 특히 `sound` 1위 데이터는 이미지 단일 포맷보다 **애니메이션/영상 하이브리드 전략**의 우선순위를 높여야 함을 시사한다.
