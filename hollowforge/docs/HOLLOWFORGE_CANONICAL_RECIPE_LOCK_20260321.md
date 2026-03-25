# HollowForge Canonical Recipe Lock

기준일: 2026-03-21

## 1. 이번 판정의 의미

- 검토 대상 배치: `hf_character_signature_combo_matrix_20260321_v1`
- 실제 생성 수: `36`
- 구조: `12 characters x 3 shared combos`
- 현재 상태: `36 completed / 0 favorited`

즉 이번 배치만으로는 아직 `사용자 favorite 기반 승률`을 계산할 수 없다.
이번 문서의 결정은 아래 두 축을 합쳐 내린 `canonical_still_v1` 잠금이다.

1. 최근 7일 favorite priors
2. animation-safe 운영 원칙

## 2. shared combo 정의

- `combo_a`
  - `prefectIllustriousXL_v70`
  - `DetailedEyes_V3@0.45`
  - `Face_Enhancer_Illustrious@0.36`
- `combo_b`
  - `waiIllustriousSDXL_v140`
  - `Seet_il5-000009@0.40`
  - `DetailedEyes_V3@0.42`
- `combo_c`
  - `ultimateHentaiAnimeRXTRexAnime_rxV1`
  - `Face_Enhancer_Illustrious@0.34`
  - `DetailedEyes_V3@0.41`

## 3. 승률 정의

추후 실제 승률은 아래 공식을 사용한다.

- `favorite_win_rate = favorites / completed`
- `shortlist_win_rate = shortlist / completed`
- `reuse_win_rate = reused_as_anchor / completed`

최종 canonical 재판정 점수는 단일 지표가 아니라 가중치 합으로 본다.

- `40%` favorite 전환
- `25%` 얼굴/헤어/체형 drift 안정성
- `20%` animation anchor 적합성
- `15%` 기술 결함률

이번 배치는 아직 favorite가 `0`이라, canonical은 `prior lock` 상태로 본다.

## 4. canonical_still_v1 잠금 결과

### Core
- `Kaede Ren`
  - canonical still: `combo_c`
  - 이유: 최근 7일 favorites에서 `ultimate` 축이 가장 강했고 hero still 적합성이 높음
- `Imani Adebayo`
  - canonical still: `combo_c`
  - 이유: 최근 7일 favorites에서 `ultimate` 축 우세, still 반응 최상
- `Nia Laurent`
  - canonical still: `combo_a`
  - 이유: `prefect` 축이 가장 안정적이고 animation 확장성도 좋음
- `Camila Duarte`
  - canonical still: `combo_a`
  - 이유: `prefect` 중심 결과가 가장 균형적
- `Mina Sato`
  - canonical still: `combo_a`
  - 이유: commercial readability와 character stability가 가장 좋음

### Reserve
- `Celeste Moretti`
  - canonical still: `combo_c`
  - 이유: 최근 favorite 장면에서 `ultimate + quiet luxury` 반응이 강함
- `Mireya Solis`
  - canonical still: `combo_c`
  - 이유: lifestyle high-response 장면에서 `ultimate` 전환 우세
- `Freya Lindholm`
  - canonical still: `combo_a`
  - 이유: luxury editorial에서 `prefect` 쪽이 가장 안전하게 고급 톤 유지
- `Lucia Moreau`
  - canonical still: `combo_a`
  - 이유: film-star glamour를 과하지 않게 고정하기 좋음
- `Hana Seo`
  - canonical still: `waiIllustriousSDXL_v160 + DetailedEyes_V3 + Face_Enhancer_Illustrious`
  - 이유: 최근 favorite priors가 `wai160/wai140` 축에 몰려 있고, 이번 shared matrix만으로 뒤집을 증거가 없음
- `Elena Petrov`
  - canonical still: `waiIllustriousSDXL_v160 + DetailedEyes_V3 + Face_Enhancer_Illustrious`
  - 이유: couture/winter luxury 장면에서 `wai160` 계열이 가장 자연스럽고 안정적
- `Keira Okafor`
  - canonical still: `waiIllustriousSDXL_v160 + DetailedEyes_V3 + Face_Enhancer_Illustrious`
  - 이유: nightlife glamour는 still 반응이 분산됐지만, identity 유지 기준으로 `wai160`이 더 안전

## 5. 운영 규칙

- 이제부터 캐릭터 대량 생산은 `still_default`가 아니라 `canonical_still`을 우선 참조한다.
- animation source still은 계속 `animation_anchor` 버전을 쓴다.
- `combo_c`가 canonical still인 캐릭터도 animation anchor는 `prefect / wai140 / wai160` 쪽을 유지한다.
- 이번 36장 배치에서 실제 favorite가 누적되면 `canonical_still_v2` 재평가를 진행한다.

## 6. 다음 작업 권장

1. 12명 각각에 대해 `canonical_still` 기준으로 identity pack `12~20장` 생성
2. 각 캐릭터에서 animation-safe anchor `6장` 추출
3. 상위 3~5명만 character LoRA 후보로 승격 검토
