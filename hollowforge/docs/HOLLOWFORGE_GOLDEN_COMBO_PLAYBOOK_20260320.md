# HollowForge Golden Combo Playbook

기준일: 2026-03-20

## 1. 범위
- 분석 대상: 최근 7일(`favorited_at >= now - 7d`) 동안 favorite 처리된 HollowForge still 이미지
- favorite 수: 283
- 목적:
  - 최근 실제 선호 데이터 기준으로 still 생성 황금 조합을 정리
  - 캐릭터 IP 후보를 추려 지속 생산 기준을 세움
  - 애니메이션까지 이어질 수 있는 조합과 still 전용 조합을 분리

## 2. 핵심 결론
- 지난 7일 기준으로 가장 강한 still 체크포인트는 `prefectIllustriousXL_v70`, `waiIllustriousSDXL_v140`, `ultimateHentaiAnimeRXTRexAnime_rxV1` 축이다.
- 가장 일관된 LoRA 베이스는 `DetailedEyes_V3 + Face_Enhancer_Illustrious`다.
- `incase_new_style_red_ill`, `Seet_il5-000009`, `96YOTTEA-WAI`, `GEN(illust) 0.2v`는 장면별 스타일 변주용으로 유효하다.
- 장면 측면에서는 `럭셔리 라이프스타일`, `스포티 글래머`, `로맨틱 여행/리조트`, `저녁 도시 무드`, `일상 속 친밀한 생활 장면`이 강했다.
- 캐릭터 IP는 `Kaede Ren`, `Imani Adebayo`, `Nia Laurent`, `Camila Duarte`, `Mina Sato`를 코어 5로 두는 것이 가장 합리적이다.
- 애니메이션 기준의 기본 still anchor는 `prefect / wai140 / wai160 + face/detail 중심 LoRA`가 가장 안전하다.
- `ultimateHentaiAnimeRXTRexAnime_rxV1`는 still favorite 전환은 매우 강하지만, 기본 애니메이션 anchor로는 한 단계 보수적으로 써야 한다.

## 3. 지난 7일 황금 조합

### 3-1. 체크포인트 랭킹
샘플 수와 favorite rate를 함께 본 기준이다.

| 티어 | 체크포인트 | 생성 수 | favorite 수 | favorite rate | 판단 |
| --- | --- | ---: | ---: | ---: | --- |
| A | `ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors` | 95 | 40 | 42.1% | still 반응 최강, 애니메이션은 보수적으로 |
| A | `prefectIllustriousXL_v70.safetensors` | 162 | 51 | 31.5% | still/animation 균형 최고 |
| A | `waiIllustriousSDXL_v140.safetensors` | 105 | 33 | 31.4% | 안정적인 캐릭터 미감 |
| B | `akiumLumenILLBase_baseV2.safetensors` | 55 | 12 | 21.8% | 부드러운 고급 톤, 보조축으로 유효 |
| B | `waiIllustriousSDXL_v160.safetensors` | 168 | 34 | 20.2% | 범용 anchor 용도 |
| B | `animayhemPaleRider_v2TrueGrit.safetensors` | 158 | 25 | 15.8% | 장면 따라 기복 있음 |
| C | `hassakuXLIllustrious_v34.safetensors` | 145 | 17 | 11.7% | 최근 favorites 기준 효율 약화 |
| 실험 | `illustrij_v20.safetensors` | 20 | 5 | 25.0% | `motorsport_chic` 한정 강세, 표본 작음 |

### 3-2. 신뢰도 높은 LoRA pair
최소 10장 이상 생성된 조합 위주.

| 티어 | 체크포인트 | LoRA 조합 | favorite 수 / 생성 수 | 판단 |
| --- | --- | --- | ---: | --- |
| A | `ultimateHentaiAnimeRXTRexAnime_rxV1` | `Face_Enhancer_Illustrious@0.34 + DetailedEyes_V3@0.41` | 6 / 10 | still 베이스 최상 |
| A | `prefectIllustriousXL_v70` | `DetailedEyes_V3@0.45 + Face_Enhancer_Illustrious@0.36` | 5 / 10 | 가장 안전한 범용 조합 |
| A | `waiIllustriousSDXL_v140` | `Seet_il5-000009@0.4 + DetailedEyes_V3@0.42` | 5 / 10 | 우아한 캐릭터 고정력 양호 |
| B | `ultimateHentaiAnimeRXTRexAnime_rxV1` | `incase_new_style_red_ill@0.48 + Face_Enhancer_Illustrious@0.34` | 4 / 10 | still용 스타일 강화 |
| B | `ultimateHentaiAnimeRXTRexAnime_rxV1` | `incase_new_style_red_ill@0.5 + DetailedEyes_V3@0.43` | 4 / 10 | 강한 시각 반응, animation은 주의 |
| B | `waiIllustriousSDXL_v140` | `96YOTTEA-WAI@0.5 + incase_new_style_red_ill@0.46` | 4 / 10 | 일상형/글래머형 모두 무난 |

소표본이지만 강하게 뜬 조합:

| 체크포인트 | LoRA 조합 | favorite 수 / 생성 수 | 메모 |
| --- | --- | ---: | --- |
| `illustrij_v20` | `Face_Enhancer_Illustrious@0.52 + DetailedEyes_V3@0.32` | 5 / 5 | `motorsport_chic` 한정으로 매우 강함 |
| `prefectIllustriousXL_v70` | `GEN(illust) 0.2v@0.42 + Face_Enhancer_Illustrious@0.45` | 5 / 5 | favorite scene pack 계열에서 강함 |

### 3-3. 장면 축
최근 favorite 전환이 강했던 장면 이름.

강한 럭셔리/에스케이프 축:
- `favorite_private_jet`
- `favorite_luxury_spa`
- `favorite_infinity_pool`
- `favorite_seaside_lounge`
- `yacht_golden_hour`
- `favorite_piano_bar`

강한 트렌드/도시 축:
- `motorsport_chic`
- `rooftop_afterwork_cocktail`
- `winter_avenue_editorial`
- `hidden_jazz_booth`

강한 일상/친밀 축:
- `post_shower_robe`
- `vinyl_floor_pose`
- `flower_market_sundress`
- `bus_stop_rain`

## 4. 운영 규칙

### 4-1. still 기본값
- 해상도: `832x1216`
- lane: `sdxl_illustrious`
- sampler: `euler_ancestral` 또는 `euler_a`
- steps: `30~35`
- cfg: `5.2~5.6`
- clip skip: `2`

### 4-2. prompt 구조
- 캐릭터 앵커는 반드시 고정한다.
- 장면 anchor는 `럭셔리 1`, `도시 1`, `일상 1`의 3축으로 분산한다.
- high-performing cue:
  - `strong eye contact`
  - `luminous skin`
  - `fully clothed`
  - `tasteful adult allure`
  - `cinematic fashion photography`
  - `platform-friendly desirability`

### 4-3. LoRA 운용 규칙
- 기본 pair는 `DetailedEyes_V3 + Face_Enhancer_Illustrious`
- 스타일 LoRA는 한 번에 1개만 추가하는 것을 기본으로 한다.
- style LoRA 우선순위:
  1. `incase_new_style_red_ill`
  2. `Seet_il5-000009`
  3. `96YOTTEA-WAI`
  4. `GEN(illust) 0.2v`
- `Okaze`, `tkt_style`는 특정 씬 보정용으로만 쓴다.

## 5. 캐릭터 선발 결과

### Core 5
1. `Kaede Ren`
2. `Imani Adebayo`
3. `Nia Laurent`
4. `Camila Duarte`
5. `Mina Sato`

선발 기준:
- 최근 7일 favorite rate
- 장면 다양성
- 서로 다른 체크포인트에서 반복적으로 살아남는지
- 향후 시리즈 운영 시 인종/무드/시장성 분산이 되는지

### Reserve
- `Celeste Moretti`
- `Freya Lindholm`
- `Lucia Moreau`
- `Mireya Solis`

### Hold
- `Amal El-Sayed`
  - 최근 7일 favorite rate가 5.0%로 낮아, 지금은 핵심 IP보다 재설계 대상이다.

## 6. 애니메이션 적합성 판단

### 6-1. 전제
- HollowForge 문서 기준으로 여전히 권장 기본 lane은 `sdxl_ipadapter_microanim_v2`다.
- 이유는 LTX 계열보다 얼굴, 머리, 의상, 프레이밍 보존이 낫기 때문이다.
- 즉 애니메이션용 still은 `극단적으로 세게 스타일링된 still`보다 `정체성이 잘 읽히는 clean anchor still`이 유리하다.

### 6-2. A-tier: still + animation 겸용
- `prefectIllustriousXL_v70 + DetailedEyes_V3 + Face_Enhancer_Illustrious`
  - 가장 안전한 기본 조합
  - 캐릭터 얼굴 유지와 미세 모션 preview에 적합
- `waiIllustriousSDXL_v140 + Seet_il5-000009 + DetailedEyes_V3`
  - 캐릭터 고정과 우아한 톤의 균형이 좋음
- `waiIllustriousSDXL_v160 + DetailedEyes_V3 + Face_Enhancer_Illustrious`
  - 범용 anchor still로 사용 가능

### 6-3. B-tier: animation 후보, 사전 검증 필요
- `animayhemPaleRider_v2TrueGrit + GEN(illust) 0.2v + Face_Enhancer_Illustrious`
  - still은 충분히 좋지만 장면별 편차가 있음
- `akiumLumenILLBase_baseV2 + Seet_il5-000009 + Face_Enhancer_Illustrious`
  - 차분한 톤에서 강점, 강한 모션보다 portrait 중심에 적합

### 6-4. C-tier: still 우선, animation은 보수적으로
- `ultimateHentaiAnimeRXTRexAnime_rxV1 + face/detail 조합`
  - still favorite 전환은 가장 강하지만 스타일 lock이 세질 수 있음
  - 본편 anchor보다는 hero still / key art 용도로 우선 사용
- `illustrij_v20 + Face_Enhancer_Illustrious + DetailedEyes_V3`
  - 최근 `motorsport_chic`에서 매우 강했지만 표본이 작고 animation 검증이 없음

### 6-5. 실무 규칙
- animation source still은 `fully clothed`, `front or 3/4 face`, `clean silhouette`, `simple background separation` 컷을 우선한다.
- still favorite가 높더라도 다음 조건이면 animation anchor에서 제외한다.
  - 스타일 LoRA가 2개 이상 과하게 겹친 컷
  - 반사/광택/하드 콘트라스트가 지나치게 강한 컷
  - 구도보다 mood에 치우쳐 얼굴 정보가 줄어든 컷
- 아직 최근 7일 favorites에는 `dreamactor_path`/`hiresfix`/`adetail` 이력이 사실상 없어서, animation 적합성 평가는 문서 원칙 + still 특성 기반 판단이다.

## 7. 바로 적용할 황금 조합

### Golden Still Base
- `prefectIllustriousXL_v70`
- `DetailedEyes_V3@0.45`
- `Face_Enhancer_Illustrious@0.36`
- 용도: 코어 캐릭터 표준 still, 캐릭터 시트, 일상형/도시형 anchor

### Golden Style Variant
- `waiIllustriousSDXL_v140`
- `Seet_il5-000009@0.4`
- `DetailedEyes_V3@0.42`
- 용도: 우아한 드레스업, 여행/리조트, 로맨틱 lifestyle

### Golden High-Reaction Still
- `ultimateHentaiAnimeRXTRexAnime_rxV1`
- `Face_Enhancer_Illustrious@0.34`
- `DetailedEyes_V3@0.41`
- 용도: 썸네일/hero still
- 주의: animation anchor 기본값으로는 쓰지 않는다

## 8. 다음 작업
1. 코어 5를 `characters` / `character_versions` 레지스트리로 승격
2. still용 기본 레시피와 animation용 anchor 레시피를 분리
3. `motorsport`, `rooftop night`, `resort luxury`, `daily intimacy` 4개 scene pack을 코어 운영 테마로 고정
4. 각 코어 캐릭터에 대해 `anchor still 6~8장`만 별도 제작 후 animation preview를 시작
