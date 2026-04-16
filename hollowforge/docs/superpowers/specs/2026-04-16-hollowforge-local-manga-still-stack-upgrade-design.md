# HollowForge Local Manga Still Stack Upgrade Design

기준일: 2026-04-16

## Goal

맥미니 로컬 ComfyUI 환경에서 `트렌디한 일본풍 만화 / 애니메이션 still` 품질을 끌어올리되,
현재 HollowForge가 이미 보유한 SDXL / Illustrious 자산을 최대한 재사용하는 방향으로
comic still lane을 업그레이드한다.

이번 단계의 목표는 세 가지다.

1. `Camila V2`를 포함한 시리즈 캐릭터의 얼굴 정체성 유지력을 개선한다.
2. `establish / beat / closeup` 각 역할에서 현재보다 더 usable한 후보를 안정적으로 받는다.
3. 로컬 `Mac mini M4 / 24GB` 제약 안에서 유지 가능한 스택만 채택한다.

이번 단계는 “최신 모델을 무작정 더 많이 받는 것”이 아니라,
`현재 로컬 스택`과 `필수 보강 자산`을 구분해
실효성이 높은 업그레이드만 넣는 설계다.

## Current State

현재 로컬 ComfyUI checkpoint inventory는 이미 생산 가능한 수준이다.

- `prefectIllustriousXL_v70.safetensors`
- `waiIllustriousSDXL_v160.safetensors`
- `hassakuXLIllustrious_v34.safetensors`
- `animayhemPaleRider_v2TrueGrit.safetensors`
- `akiumLumenILLBase_baseV2.safetensors`
- `autismmixSDXL_autismmixConfetti.safetensors`
- `illustrij_v20.safetensors`
- `ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors`

LoRA inventory도 최소한의 품질 보강에 충분하다.

- `DetailedEyes_V3.safetensors`
- `Face_Enhancer_Illustrious.safetensors`
- `Seet_il5-000009.safetensors`
- `incase_new_style_red_ill.safetensors`
- `Okaze.safetensors`
- `tkt_style.safetensors`

즉 현재 문제는 “모델이 없어서”가 아니다.

현재 still 품질 저하의 핵심 원인은 아래 두 가지다.

1. 얼굴 정체성 보강 자산이 일반 `SDXL IPAdapter` 한 종뿐이다.
2. still lane이 사실상 `single-pass generation` 구조라서,
   wide shot이나 room-first composition에서 identity drift를 흡수하지 못한다.

실제 현재 `sdxl_ipadapter_still` worker workflow는
`Checkpoint -> LoRA -> CLIPTextEncodeSDXL -> IPAdapterAdvanced -> EmptyLatentImage -> KSampler -> SaveImage`
구조이며, 최종 still polishing 단계가 없다.

## Hardware Constraint

실행 하드웨어는 아래와 같다.

- `Mac mini`
- `Apple M4`
- `24 GB unified memory`

이 제약에서 `대형 신형 아키텍처`를 여러 개 동시에 들여
장기 운영하는 것은 비효율적이다.

현실적인 방향은:

- `SDXL / Illustrious` 중심 유지
- `face-specific identity asset` 추가
- `2-stage still lane` 설계
- checkpoint 추가는 1개 단위로 제한

이다.

## Root Cause

현재 품질 문제를 “체크포인트 노후화”로만 보면 오진이다.

기존 결과와 최근 실패 사례를 종합하면 문제는 아래 순서로 정리된다.

### 1. General SDXL IPAdapter is not enough for identity lock

현재 로컬에는 `ipAdapterPlusSd15_ipAdapterPlusSdxlVit.safetensors`만 있다.
이건 일반 이미지 conditioning에는 유용하지만,
컷이 바뀌는 comic still production에서 얼굴 동일성을 강하게 고정하기엔 약하다.

특히 아래 상황에서 한계가 두드러진다.

- `establish`처럼 인물이 작고 공간이 큰 컷
- 캐릭터 스타일과 room-first composition이 동시에 요구되는 컷
- 긴 positive / negative grammar와 reference conditioning이 겹치는 컷

### 2. Current establish lane is over-constrained but under-repaired

현재 establish lane은 아래를 한 번에 모두 요구한다.

- scene-first composition
- reduced subject occupancy
- identity canon
- style canon
- binding notes
- long negative prompt
- reference image conditioning

하지만 생성 이후 `face/identity repair pass`가 없어서,
한 번 어긋난 hair / skin / face drift가 그대로 남는다.

### 3. Existing favorite-informed room recipe optimizes room readability, not face appeal

`room_safe` recipe는 현재 `akiumLumenILLBase_baseV2`와
`LoRA 없음`으로 establish를 돌리게 한다.

이 결정은 방 읽힘에는 도움 되지만,
사용자가 현재 중요하게 보는 포인트인 아래 항목에는 불리하다.

- 캐릭터 매력도
- 같은 사람으로 보이는 얼굴 유지
- 최신 일본풍 만화/애니 일러스트 감도

즉 room recipe는 유지하더라도,
identity repair 계층이 반드시 필요하다.

## Model Update Assessment

현재 설치 모델을 전면 교체할 이유는 없다.

### Keep as active production baselines

- `prefectIllustriousXL_v70`
- `waiIllustriousSDXL_v160`
- `hassakuXLIllustrious_v34`
- `animayhemPaleRider_v2TrueGrit`

이 모델들은 내부 문서 기준으로도 이미 main pool 혹은 secondary pool에 들어가 있고,
외부 공개 상태로도 완전히 낡은 라인이 아니다.

### Worth updating or adding

- `NoobAI-XL`
  - 2025~2026 기준으로도 메인스트림 anime checkpoint로 유지된다.
  - 권장 설정이 현재 HollowForge SDXL lane과 잘 맞는다.
  - 목적: 최신 anime baseline 1개 확보

- `AniMayhem Pale Rider v3.0`
  - 현재 로컬은 `v2 True Grit`
  - 공개상 `v3.0 Plains Drifter`가 존재한다.
  - 목적: 기존 선호 merge의 최신 계열 비교

### Not recommended as immediate priority

- 공식 `Illustrious XL 2.0+`
  - 기술적으로 가치가 있지만,
    현재 목적은 “바로 production-looking still을 뽑는 것”이다.
  - 즉시 실효성 기준에서는 `NoobAI-XL`보다 우선순위가 낮다.

## Recommended Direction

권장 방향은 아래다.

### 1. Keep the current SDXL / Illustrious core

먼저 `prefect / wai / hassaku`를 버리지 않는다.
현재 프로젝트 프롬프트와 LoRA, 그리고 ComfyUI lane은 이미 이 계열에 맞춰져 있다.

### 2. Add face-specific IPAdapter assets first

checkpoint 추가보다 먼저 넣어야 하는 자산은 `face-specific IPAdapter`다.

필수 추가:

- `ip-adapter-plus-face_sdxl_vit-h.safetensors`

선택 추가:

- `ip-adapter-faceid-plusv2_sdxl.bin`
- `ip-adapter-faceid-plusv2_sdxl_lora.safetensors`

의도는 아래와 같다.

- `plus-face SDXL` = 기본 얼굴 유사성 보강
- `FaceID plus v2 SDXL` = closeup / repair 전용 stronger identity lock

### 3. Add only one new checkpoint at first

신규 체크포인트는 1개만 추가한다.

1순위:

- `NoobAI-XL`

2순위:

- `AniMayhem Pale Rider v3.0`

이유는 간단하다.

- 변수 수를 적게 유지해야 무엇이 실제로 효과를 냈는지 분리할 수 있다.
- 맥미니 로컬에서 대형 실험군을 늘리면 디스크와 운영 복잡도만 커진다.

### 4. Replace single-pass establish with two-stage still lane

가장 중요한 설계 변경은 이 부분이다.

최종 still은 앞으로 아래 두 단계로 간다.

#### Stage A: base still generation

목적:

- 구도
- 환경 읽힘
- 몸 전체 실루엣
- 컷 서사

candidate source:

- `prefect v70`
- `hassaku v34`
- `NoobAI-XL` after install

conditioning:

- current structured prompt
- current role negative
- optional hero-only reference guidance

#### Stage B: identity repair / face repair

목적:

- 얼굴 동일성
- 머리색 / 피부톤 drift 보정
- 눈 / 입 / 얼굴 윤곽 안정화
- 과도한 AI 티 완화

candidate source:

- `plus-face SDXL` 기본
- `FaceID plus v2 SDXL`는 closeup / salvage lane 전용

이 구조로 가면 `establish`에서는 room-first 구도를 살리고,
`beat / closeup`에서는 얼굴 정체성을 훨씬 더 강하게 고정할 수 있다.

## Install Targets

이번 단계의 설치 대상은 아래 순서로 제한한다.

### Phase 1: required

1. `ip-adapter-plus-face_sdxl_vit-h.safetensors`

### Phase 2: optional but recommended

2. `ip-adapter-faceid-plusv2_sdxl.bin`
3. `ip-adapter-faceid-plusv2_sdxl_lora.safetensors`

### Phase 3: checkpoint

4. `NoobAI-XL` checkpoint 1개

### Deferred

5. `AniMayhem Pale Rider v3.0`
6. official `Illustrious XL 2.x`

## Validation Plan

설치 후 검증은 광범위 benchmark가 아니라
작은 production-like matrix로 시작한다.

### Shot set

- `establish`
- `beat`
- `closeup`

각 1샷씩, 총 3샷.

### Checkpoint comparison set

- `prefectIllustriousXL_v70`
- `hassakuXLIllustrious_v34`
- `NoobAI-XL`

### Evaluation axes

- 얼굴이 같은 사람처럼 보이는가
- 머리색 / 피부톤 drift가 줄었는가
- room readability가 유지되는가
- 손 / 얼굴 안정성이 올라갔는가
- camera frame / gibberish text artifact가 줄었는가
- 캐릭터 매력도가 올라갔는가
- “AI 티”가 덜 거슬리는가

### Pass condition

최소 아래 두 조건을 동시에 만족해야 한다.

1. 현재 hero-only establish baseline보다 identity drift가 유의미하게 줄어든다.
2. 사용자가 눈으로 봤을 때 더 매력적이고 덜 어색하다고 느낄 정도의 개선이 나온다.

## Risks

### 1. Face repair may over-pull portraits

face-specific adapter를 강하게 쓰면
room-first establish가 다시 portrait pull로 무너질 수 있다.

대응:

- establish는 `base pass 우선`
- face repair는 제한된 강도로만 적용
- closeup / beat와 establish를 같은 weight로 다루지 않는다

### 2. FaceID adds operational complexity

FaceID 계열은 전용 LoRA와 추가 runtime dependency가 필요할 수 있다.

대응:

- `plus-face SDXL`부터 도입
- FaceID는 2차 실험군으로만 도입

### 3. New checkpoint may not outperform tuned legacy stack

`NoobAI-XL`이 화제성은 높아도,
현재 프로젝트 프롬프트와 LoRA 문법에선 `prefect / hassaku`보다 안 맞을 수 있다.

대응:

- baseline을 유지
- 신규 checkpoint는 replace가 아니라 compare로만 시작

## Out of Scope

이번 설계는 아래를 포함하지 않는다.

- animation generation tool 최종 선정
- CSP 편집 단계
- speech bubble / PSD typography production
- full comic page assembly redesign
- 모든 체크포인트 전수 재벤치

## Decision

이번 단계의 최종 의사결정은 아래다.

1. 현재 SDXL / Illustrious core는 유지한다.
2. 가장 먼저 `plus-face SDXL`을 추가한다.
3. `FaceID plus v2 SDXL`는 2차 도입 후보로 둔다.
4. 신규 체크포인트는 `NoobAI-XL` 1개만 먼저 추가한다.
5. still lane은 `single-pass`가 아니라 `base pass -> identity repair pass` 구조로 전환한다.
