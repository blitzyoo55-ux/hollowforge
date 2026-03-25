# HollowForge Market Validation Matrix

작성일: 2026-03-13  
대상 프로젝트: HollowForge  
목적: `AI_NSFW_MARKET_LANDSCAPE_20260313.md`의 시장 해석을 실제 배치 실험 계획으로 전환한다.

관련 문서:
- [AI NSFW Market Landscape Report](./AI_NSFW_MARKET_LANDSCAPE_20260313.md)
- [favorites_trend_analysis_20260307.md](./favorites_trend_analysis_20260307.md)
- [Market Validation Preset Runbook](./HOLLOWFORGE_MARKET_VALIDATION_PRESET_RUNBOOK_20260313.md)
- `HOLLOWFORGE_MARKET_VALIDATION_PHASE1_DIRECT_IMPORT_20260313.csv`
- `HOLLOWFORGE_MARKET_VALIDATION_PHASE1_QUEUE_PAYLOAD_20260313.json`
- `HOLLOWFORGE_MARKET_VALIDATION_REQUEST_PRESETS_20260313.json`

---

## 0. 결론

- HollowForge의 다음 시장 검증은 `latex/bdsm 단일축 심화`가 아니라 `4개 라인 병렬 검증`으로 가는 것이 맞다.
- 1차 라운드는 `콘텐츠 축`만 비교한다.
- 2차 라운드는 `체크포인트 편향`을 제거한다.
- 3차 라운드는 `이긴 라인`을 `캐릭터 자산`으로 굳히는 단계다.

**권장 실험 총량**

- Phase 1: `12 batches`
- Phase 2: `8 batches`
- Phase 3: `6 batches`
- 총계: `26 batches`

**권장 배치 단위**

- `1 batch = 25 images`
- 구성: `5 prompt variants x 5 seeds`
- 총 이미지 수: `650 images`

이 정도면 HollowForge가 현재 방식으로 충분히 처리 가능하면서도, 라인 간 차이를 읽을 만큼의 표본이 나온다.

---

## 1. 실험 원칙

### 1-1. 이번 검증에서 확인할 것

1. `어떤 콘텐츠 라인이 가장 높은 반응을 받는가`
2. `어떤 라인이 캐릭터 자산화에 유리한가`
3. `latex/bdsm`가 코어여야 하는지, premium lane이면 충분한지
4. `오리지널 캐릭터 + 뷰티/스타성`이 실제로 stronger lane인지

### 1-2. 이번 검증에서 고정할 것

- 해상도: `832x1216`
- steps: `30` 또는 `35`
- CFG: `5.0 ~ 6.0`
- sampler: `euler_a`
- clip skip: `2`
- negative prompt: 현재 HollowForge 기본 negative prompt 고정
- no-IP 원칙: 유명 캐릭터명, 프랜차이즈명, 로고, 고유 상징 금지

### 1-3. 체크포인트 운영 원칙

- Phase 1 baseline checkpoint: `prefectIllustriousXL_v70`
- Phase 2 verification checkpoint A: `waiIllustriousSDXL_v160`
- Phase 2 verification checkpoint B: `animayhemPaleRider_v2TrueGrit`

이렇게 해야 `콘텐츠 라인 자체의 반응`과 `모델 스타일 편향`을 분리해서 볼 수 있다.

---

## 2. 평가 지표

## Primary Metrics

- `favorite_rate`
  - 공식값: `favorites / generated`
- `strong_pick_rate`
  - 수동으로 “다시 만들고 싶은 컷”으로 고른 이미지 비율
- `character_seed_rate`
  - 시리즈화 가능한 캐릭터 후보로 분류된 이미지 비율

## Secondary Metrics

- `quality_pass_rate`
  - `quality_ai_score >= 86` 또는 수동 평가 통과 비율
- `repeatable_face_rate`
  - 같은 배치 안에서 얼굴/헤어/무드가 반복 가능해 보이는 컷 비율
- `distinctiveness_rate`
  - 다른 라인과 구분되는 브랜딩 감도를 보여주는 컷 비율

## Penalty Metrics

- `drift_rate`
  - 의도와 다른 장르/스타일로 무너지는 비율
- `anatomy_fail_rate`
  - 손/비율/얼굴 붕괴 비율
- `ip_risk_rate`
  - 특정 유명 IP로 연상될 여지가 있는 비율

## 통과 기준

### Phase 1 통과

- `favorite_rate >= 14%`
- `strong_pick_rate >= 6%`
- `character_seed_rate >= 4%`
- `ip_risk_rate = 0`

### Phase 2 통과

- Phase 1 기준 통과
- 다른 checkpoint에서도 반응 하락폭이 크지 않을 것
- `repeatable_face_rate >= 25%`

### Phase 3 최종 승격

- 최소 1명의 명확한 캐릭터가 반복 가능
- `favorite_rate >= 18%`
- `character_seed_rate >= 8%`
- `strong_pick_rate >= 8%`

---

## 3. 실험 라인 구조

이번 검증은 4개 라인으로 나눈다.

### Line A — Original Beauty / Editorial

목적:
- 가장 넓은 유입 가능성을 검증한다.
- HollowForge가 fetish 없이도 strong reaction을 얻는지 본다.

핵심 가설:
- `미형 + 스타성 + 고급 에디토리얼`이 현재 HollowForge보다 더 넓은 반응을 만든다.

### Line B — Alt / Goth / Non-IP Cosplay-coded

목적:
- 캐릭터성, 세계관성, 코스튬 판타지를 검증한다.

핵심 가설:
- `오리지널 캐릭터 + alt/goth + 비IP 코스튬 감성`이 HollowForge의 가장 강한 성장축이 될 수 있다.

### Line C — Fetish-adjacent Broad Appeal

목적:
- `latex`보다 넓은 fetish-adjacent 축을 검증한다.

핵심 가설:
- 발, 부츠, 초커, 하네스, posture 같은 요소가 `latex-only`보다 넓은 반응을 만든다.

### Line D — Latex / BDSM Premium

목적:
- 현재 시그니처 라인의 실제 강도를 측정한다.

핵심 가설:
- `latex/bdsm`는 여전히 반응이 강하지만, 코어보다는 프리미엄 확장 라인으로 더 적합하다.

---

## 4. Phase 1 Matrix

Phase 1 목표:
- `콘텐츠 축`만 비교
- 전부 `prefectIllustriousXL_v70`로 생성
- 각 pack당 `1 batch = 25 images`

### Phase 1 총량

- `12 packs`
- `12 batches`
- `300 images`

### Matrix

| Pack ID | Line | 목적 | 태그 조합 방향 | Batch 수 |
|---|---|---|---|---:|
| A1 | Original Beauty / Editorial | broad beauty baseline | `original character`, `solo`, `editorial glamour`, `luxury lingerie`, `confident gaze`, `soft key light`, `hotel suite`, `clean skin`, `cinematic portrait` | 1 |
| A2 | Original Beauty / Editorial | star quality 검증 | `original character`, `solo`, `high-fashion`, `sheer couture`, `red carpet mood`, `flash glam`, `celebrity aura`, `beauty close-up` | 1 |
| A3 | Original Beauty / Editorial | dark romance 검증 | `original character`, `solo`, `romantic darkness`, `corset couture`, `candlelit chamber`, `elegant pose`, `long hair motion`, `dramatic light` | 1 |
| B1 | Alt / Goth / Non-IP Cosplay-coded | alt-goth 코어 검증 | `original character`, `solo`, `goth makeup`, `black lace`, `choker`, `smoky eyes`, `moody club light`, `cool confidence` | 1 |
| B2 | Alt / Goth / Non-IP Cosplay-coded | sci-fi 코스튬 감성 검증 | `original character`, `solo`, `sleek tactical bodysuit`, `visor`, `neon lab`, `futuristic styling`, `clean silhouette`, `cold lighting` | 1 |
| B3 | Alt / Goth / Non-IP Cosplay-coded | occult fashion 검증 | `original character`, `solo`, `occult couture`, `ritual sigils`, `dark academy`, `structured outfit`, `library set`, `mystic elegance` | 1 |
| C1 | Fetish-adjacent Broad Appeal | legwear/heels 검증 | `original character`, `solo`, `long legs`, `stockings`, `stilettos`, `choker`, `glam pose`, `soft flash lighting` | 1 |
| C2 | Fetish-adjacent Broad Appeal | boots/authority 검증 | `original character`, `solo`, `thigh-high boots`, `gloves`, `commanding stance`, `doorway framing`, `editorial power pose` | 1 |
| C3 | Fetish-adjacent Broad Appeal | accessory restraint-coded 검증 | `original character`, `solo`, `body harness`, `cuffs as fashion`, `tension pose`, `studio backdrop`, `controlled elegance` | 1 |
| D1 | Latex / BDSM Premium | latex editorial baseline | `original character`, `solo`, `glossy latex`, `fashion editorial`, `spotlight`, `high contrast`, `luxury set`, `clean composition` | 1 |
| D2 | Latex / BDSM Premium | current signature 검증 | `original character`, `solo`, `full-cover latex mask`, `latex hood`, `sterile chamber`, `faceless elegance`, `lab-coded atmosphere` | 1 |
| D3 | Latex / BDSM Premium | power dynamic premium 검증 | `original character`, `solo`, `latex harness`, `restraint aesthetic`, `industrial set`, `dramatic side light`, `submission-coded posture` | 1 |

---

## 5. Phase 2 Matrix

Phase 2 목표:
- Phase 1 상위 pack만 추린다.
- `checkpoint bias`를 걷어낸다.
- winning pack이 다른 모델에서도 살아남는지 확인한다.

### 선발 규칙

- Phase 1 상위 `4 packs` 선발
- 기준: `favorite_rate`, `strong_pick_rate`, `character_seed_rate`

### Phase 2 총량

- 상위 `4 packs`
- pack당 `2 batches`
- 총 `8 batches`
- 총 `200 images`

### 운영 방식

각 winning pack에 대해:

- `1 batch`는 `waiIllustriousSDXL_v160`
- `1 batch`는 `animayhemPaleRider_v2TrueGrit`

### 목적

- 같은 태그 조합이 다른 기반 모델에서도 먹히는지 확인
- 특정 checkpoint에서만 우연히 잘 나온 라인을 제거
- 시리즈화에 적합한 라인의 안정성 검증

---

## 6. Phase 3 Matrix

Phase 3 목표:
- 이긴 라인을 `캐릭터 자산`으로 전환
- 태그 실험이 아니라 `캐릭터 반복 생산성`을 본다

### 선발 규칙

- Phase 2 상위 `2 packs` 선발

### Phase 3 총량

- 상위 `2 packs`
- pack당 `3 batches`
- 총 `6 batches`
- 총 `150 images`

### 배치 구성

각 winning pack에 대해 아래 3개 배치를 만든다.

#### Batch 1 — Character Lock

- 목적: 같은 캐릭터가 반복 생성 가능한지 확인
- 방식: 이름, 얼굴 구조, 헤어, 시그니처 outfit를 고정

#### Batch 2 — Environment Drift Test

- 목적: 배경이 바뀌어도 캐릭터성이 유지되는지 확인
- 방식: 같은 캐릭터를 `3개 환경`으로 변주

#### Batch 3 — Intensity Ladder

- 목적: 강도 조절이 가능한지 확인
- 방식: 같은 캐릭터를 `soft editorial -> suggestive -> premium` 3단 구조로 변주

---

## 7. 구체 태그 팩 설계

아래는 실제 Prompt Factory에서 바로 쓰기 좋은 수준의 `tag pack skeleton`이다.

## A1 — Luxury Editorial Baseline

**Core**

- `original character`
- `solo`
- `editorial glamour`
- `luxury lingerie`
- `confident gaze`
- `clean skin`
- `cinematic portrait`

**Environment**

- `hotel suite`
- `soft key light`
- `warm gold accent`

**Intent**

- `high-end`
- `celebrity aura`
- `expensive mood`

## B1 — Alt Goth Core

**Core**

- `original character`
- `solo`
- `goth makeup`
- `black lace`
- `choker`
- `smoky eyes`
- `cool confidence`

**Environment**

- `moody club light`
- `dark dressing room`
- `blue-red contrast`

**Intent**

- `alt icon`
- `nightlife muse`
- `dark beauty`

## B2 — Sci-fi Cosplay-coded

**Core**

- `original character`
- `solo`
- `sleek tactical bodysuit`
- `visor`
- `futuristic styling`
- `clean silhouette`

**Environment**

- `neon lab`
- `sterile hallway`
- `cold rim light`

**Intent**

- `non-ip sci-fi heroine`
- `premium costume fantasy`

## C1 — Legs / Heels / Choker

**Core**

- `original character`
- `solo`
- `long legs`
- `stockings`
- `stilettos`
- `choker`
- `glam pose`

**Environment**

- `boudoir couch`
- `soft flash`
- `editorial room set`

**Intent**

- `broad fetish-adjacent appeal`
- `fashion-first`

## C2 — Boots / Authority

**Core**

- `original character`
- `solo`
- `thigh-high boots`
- `gloves`
- `commanding stance`
- `strong posture`

**Environment**

- `doorway framing`
- `hallway set`
- `hard key light`

**Intent**

- `authority-coded`
- `dominant elegance`

## C3 — Harness / Accessory Tension

**Core**

- `original character`
- `solo`
- `body harness`
- `cuffs as fashion`
- `tension pose`
- `structured styling`

**Environment**

- `minimal studio`
- `clean backdrop`
- `high contrast`

**Intent**

- `restraint-coded but editorial`
- `fashionized fetish`

## D1 — Latex Editorial

**Core**

- `original character`
- `solo`
- `glossy latex`
- `fashion editorial`
- `clean composition`

**Environment**

- `spotlight`
- `luxury set`
- `mirror reflections`

**Intent**

- `premium fetish fashion`

## D2 — Signature Masked Latex

**Core**

- `original character`
- `solo`
- `full-cover latex mask`
- `latex hood`
- `faceless elegance`
- `lab-coded styling`

**Environment**

- `sterile chamber`
- `cold overhead light`
- `minimal clinical set`

**Intent**

- `brand signature`
- `lab-451 identity`

## D3 — Power Dynamic Premium

**Core**

- `original character`
- `solo`
- `latex harness`
- `restraint aesthetic`
- `submission-coded posture`

**Environment**

- `industrial set`
- `dramatic side light`
- `metal structure`

**Intent**

- `premium power dynamic`
- `niche concentration`

---

## 8. 권장 배치 배분

실험 효율을 위해 아래 순서를 권장한다.

### Week 1

- Phase 1의 `A1, B1, C1, D1`
- 각 `1 batch`
- 목적: 각 라인의 가장 대표적인 baseline 반응 확인

### Week 2

- Phase 1의 `A2, B2, C2, D2`
- 각 `1 batch`
- 목적: 2차 스타일 축 비교

### Week 3

- Phase 1의 `A3, B3, C3, D3`
- 각 `1 batch`
- 목적: 라인 내부 고강도 변형 비교

### Week 4

- Phase 2 상위 `4 packs`
- 각 `2 batches`

### Week 5

- Phase 3 상위 `2 packs`
- 각 `3 batches`

---

## 9. 데이터 입력 방식

이번 검증은 이미지 하나하나의 감상평보다 `라인 단위 scorecard`로 적재해야 한다.

### 각 batch에 기록할 값

- `batch_id`
- `lane_id`
- `pack_id`
- `checkpoint`
- `favorite_count`
- `favorite_rate`
- `strong_pick_count`
- `character_seed_count`
- `quality_avg`
- `quality_ai_avg`
- `repeatable_face_count`
- `ip_risk_count`
- `notes`

### 각 winning character에 기록할 값

- `character_temp_id`
- `pack_id`
- `hair / face / styling notes`
- `used prompt recipe`
- `reusable environments`
- `premium escalation suitability`

---

## 10. Kill / Keep Rules

## 바로 중단할 것

- `favorite_rate < 10%`
- `character_seed_rate = 0`
- IP 유사성 이슈 발생
- 반복적으로 anatomy fail이 나오는 pack

## 유지할 것

- `favorite_rate >= 14%`
- `strong_pick_rate >= 6%`
- 반복 가능한 얼굴/헤어 아이덴티티 발견

## 확대할 것

- `favorite_rate >= 18%`
- `character_seed_rate >= 8%`
- 다른 checkpoint에서도 강함 유지

---

## 11. HollowForge용 최종 권장

현재 기준으로는 아래 순서가 가장 합리적이다.

1. `A1`, `B1`, `C1`, `D1`부터 시작한다.
2. 첫 주 결과에서 `B1`과 `C1`이 강하면, HollowForge의 코어 방향은 `alt/goth + fetish-adjacent`로 본다.
3. `D2`가 강하더라도, 그것만으로 메인 전략 승격은 하지 않는다.
4. `A1/A2`가 강하면 `스타성/뷰티 코어`를 더 전면으로 올린다.
5. 최종적으로는 `코어 1개 + 확장 1개 + 프리미엄 1개`의 3라인 구조로 굳힌다.

---

## 12. 최종 판단

이번 검증은 단순히 “무슨 fetish가 더 센가”를 보는 실험이 아니다.

이번 검증의 진짜 질문은 아래 두 개다.

1. `HollowForge가 어떤 라인에서 가장 큰 반응을 얻는가`
2. `그 반응이 캐릭터 자산과 구독형 상품성으로 이어질 수 있는가`

따라서 이번 매트릭스는 `태그 인기 실험`이 아니라 `콘텐츠 비즈니스 포지셔닝 실험`으로 봐야 한다.
