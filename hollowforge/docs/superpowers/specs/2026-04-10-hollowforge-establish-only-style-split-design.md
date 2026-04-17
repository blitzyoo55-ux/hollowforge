# HollowForge Establish-Only Style Split Design

기준일: 2026-04-10

## Goal

`Camila V2` still lane에서 `establish` 패널만 별도 execution style로 분리한다.

목표는 단순한 미세 품질 개선이 아니다.

- `잘못된 establish 후보를 더 잘 거르는 것`에서 멈추지 않고
- `처음부터 더 성숙하고 room-first인 establish 후보를 생성하는 것`

이번 단계의 성공 기준은 아래 두 가지다.

1. `establish`에서 schoolgirl / classroom / glamour portrait bias가 유의미하게 줄어든다.
2. `beat / insert / closeup`은 현재 favorite-quality lane을 그대로 유지한다.

즉 이번 설계는 `series style canon 전체 교체`가 아니라, `establish만 분리된 generator lane`을 추가하는 bounded fix다.

## Current State

현재 상태는 이전 단계보다 낫지만, 여전히 생성기가 병목이다.

확인된 사실:

- latest live backend는 `bad candidate`를 이제 실제로 탈락시킨다.
- 최신 live one-panel run은 `Identity gate rejected all materialized candidates`로 종료됐다.
- 즉 `selection`은 개선됐고, `generator`가 남은 병목이다.

대표 evidence:

- 이전 wrongly-passed establish:
  - `data/outputs/9d328d66-5ae8-4f23-853b-510b7cde2a93.png`
- 최신 live rejected establish:
  - `data/outputs/8635ab4b-5d63-4ef7-a475-fe7e4a42da83.png`
  - `data/outputs/924c5be5-3ddd-485a-802f-8e67b962f11e.png`

직접 확인한 결과:

- `REC/frame` artifact는 줄었지만
- 여전히 `orange hair`, `school-uniform silhouette`, `classroom/desk bias`, `portrait pull`, `gibberish bottom text`가 강하다

즉 prompt와 gate만으로는 부족하고, `establish generation lane` 자체를 분리해야 한다.

## Installed Checkpoint Inventory

현재 ComfyUI runtime에서 확인된 image checkpoint는 아래다.

- `akiumLumenILLBase_baseV2.safetensors`
- `animayhemPaleRider_v2TrueGrit.safetensors`
- `autismmixSDXL_autismmixConfetti.safetensors`
- `hassakuXLIllustrious_v34.safetensors`
- `illustrij_v20.safetensors`
- `prefectIllustriousXL_v70.safetensors`
- `ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors`
- `waiIllustriousSDXL_v140.safetensors`
- `waiIllustriousSDXL_v160.safetensors`

이 단계에서는 새 모델을 도입하지 않는다.
설치는 끝난 체크포인트 안에서만 establish split을 시도한다.

## Problem Statement

현재 `Camila V2` style execution은 role별로 checkpoint를 바꾸지 않는다.

지금 구조:

- style execution:
  - `prefectIllustriousXL_v70`
- establish:
  - beauty enhancer LoRA는 제거됨
- beat / insert / closeup:
  - favorite stack 유지

이 구조는 다음 한계를 가진다.

1. checkpoint base 자체가 still attractiveness 쪽으로 너무 잘 끌린다.
2. establish에서 even without LoRA, 얼굴/의상/톤이 youth-coded anime로 수렴할 때가 많다.
3. 결과적으로 gate가 좋아질수록 `all candidates rejected` 빈도만 높아진다.

즉 지금 필요한 것은 `더 강한 gate`가 아니라 `더 적합한 establish generator`다.

## Considered Approaches

### 1. Same checkpoint, stronger prompt/negative

장점:

- 구현 범위가 가장 작다

단점:

- 이미 한계가 확인됐다
- current state가 바로 이 접근의 귀결이다
- gate는 개선되지만 usable establish를 만들지 못한다

부족하다.

### 2. Establish-only style split

장점:

- 병목을 직접 겨냥한다
- `beat / insert / closeup` favorite lane을 건드리지 않는다
- `Camila V2 still quality pass`를 작은 범위로 계속 검증할 수 있다
- 실패해도 rollback 범위가 작다

단점:

- role별 style execution contract가 조금 늘어난다
- 첫 checkpoint 선택을 잘못하면 한 번 더 튜닝이 필요하다

이번 단계에 가장 적합하다.

### 3. Full series style canon replacement

장점:

- 장기 구조는 가장 깔끔할 수 있다

단점:

- 지금 범위에서는 과하다
- establish 병목과 전체 스타일 문제를 분리해서 볼 수 없게 된다
- beat/closeup까지 같이 흔들 위험이 크다

이번 단계에는 과설계다.

## Recommended Direction

권장 방향은 `establish-only style split`이다.

구체적으로:

- `establish`만 별도 execution override를 사용
- `beat / insert / closeup`은 현행 `prefectIllustriousXL_v70` favorite lane 유지
- 1차 establish checkpoint는 `akiumLumenILLBase_baseV2.safetensors`

이 선택의 이유:

- 현재 live evidence에서 필요한 건 `more adult / less schoolgirl / more room-first`
- `prefectIllustriousXL_v70`는 establish에서 youth-coded portrait bias가 강하다
- `akiumLumenILLBase_baseV2`는 이름과 inventory positioning상, 첫 bounded establish 후보로 가장 무난하다

이번 단계는 “최종 winner 고정”이 아니라 “establish split이 실제로 quality에 도움이 되는지”를 검증하는 1차 시도다.

## Design

### 1. Series Style Canon ownership stays intact

checkpoint/LoRA family ownership은 계속 `series style canon`에 둔다.

하지만 이제 `series style canon`은 optional role execution override를 가질 수 있다.

예시 구조:

- base execution
  - checkpoint
  - loras
  - steps/cfg/sampler
- role overrides
  - `establish`
    - checkpoint
    - loras
    - optional steps/cfg/sampler override

즉 `panel profile`은 여전히 shot grammar만 소유하고,
`which checkpoint to use for establish`는 style canon이 소유한다.

### 2. V2 resolver adds role-aware execution lookup

`resolve_comic_render_v2_contract(...)`는 현재 `series_style_id -> execution params`만 본다.

이번 단계부터는:

- default execution params를 읽고
- `panel_type == establish`이면 role override를 merge한다

merge precedence:

1. style base execution
2. style role override
3. binding lock strengths
4. panel profile dimensions/framing metadata

### 3. Establish override policy

1차 establish override policy:

- checkpoint:
  - `akiumLumenILLBase_baseV2.safetensors`
- LoRA:
  - none
- sampler family:
  - current establish-safe settings 유지 unless live result forces retune

의도:

- beauty enhancer 완전 제거
- more adult baseline
- room/background readability를 checkpoint level에서 끌어올리기

### 4. No change to beat/insert/closeup in this phase

이번 단계에서 손대지 않는 것:

- beat generator
- insert generator
- closeup generator
- teaser motion policy

이유:

- 현재 병목은 establish다
- role 전체를 같이 흔들면 원인 분리가 다시 어려워진다

## In Scope

- `series style canon`에 role execution override 추가
- `camila_pilot_v1`에 establish-only override 추가
- V2 resolver에서 role-aware execution merge 구현
- tests update
- live one-panel Camila V2 establish rerun
- direct image review

## Out Of Scope

- full series style canon replacement
- beat/closeup generator retune
- new checkpoint downloads
- other characters
- stable path promotion
- Clip Studio integration

## Acceptance

이번 단계 acceptance는 아래로 고정한다.

1. focused tests pass
2. live one-panel Camila V2 establish rerun completes
3. direct review 기준:
   - less school-uniform / less youth-coded drift
   - less classroom/desk bias
   - more believable artist-loft / room-first read
4. gate가 `all rejected`에서 벗어나거나,
   적어도 이전 `prefect` establish보다 materially better한 candidate를 1개 이상 생성

## Failure Handling

아래 중 하나면 이번 checkpoint 후보는 실패다.

- still looks like schoolgirl anime portrait
- room does not read as artist loft
- candidate still needs the gate to reject everything
- beat/closeup lane regression appears

그 경우 다음 후보는 아래 순서로 본다.

1. `illustrij_v20.safetensors`
2. `hassakuXLIllustrious_v34.safetensors`

하지만 이번 단계에서는 implementation을 `candidate sweep framework`로 키우지 않는다.
1차 시도는 `akiumLumenILLBase_baseV2` 하나로 bounded하게 검증한다.
