# HollowForge Camila V2 Identity-First Candidate Gating Design

기준일: 2026-04-09

## Goal

`Camila Duarte` V2 still lane에서 `읽히는 컷`과 `같은 사람 유지`가 충돌할 때, 무조건 `같은 사람 유지`를 먼저 통과시키는 selection gate를 추가한다.

이번 단계의 목적은 prompt를 더 화려하게 만드는 것이 아니다. 이미 통과한 `room readability`와 `role diversity`를 유지하면서, `same-person hold`를 깨는 후보가 자동 선택되는 구조를 막는 bounded fix다.

## Trigger

실제 live acceptance에서 아래 네 컷이 선택되었고, 결과는 실패였다.

- `a581dac9-927c-44b6-85b6-f1a2d3a5206b.png`
- `8aa4e0e2-ce2a-46e2-8e0f-d4bd0225e170.png`
- `0a3b62e7-7490-43d4-aa34-fa490b44514c.png`
- `683a6b7b-ebf6-49ea-98c7-1b431e09dce4.png`

실패 양상은 명확했다.

1. `establish readability`는 좋아졌다.
2. `role diversity`도 생겼다.
3. 하지만 패널 1과 패널 2~4가 같은 Camila로 읽히지 않았다.

즉 현재 병목은 `quality 부족`이 아니라 `selection이 identity drift를 막지 못하는 것`이다.

## Problem Statement

현재 bounded pilot helper와 comic still lane은 아래 문제를 가진다.

### 1. Helper auto-selection이 너무 얕다

`launch_camila_v2_comic_pilot.py`는 현재 패널별로 사실상 `첫 materialized asset`을 선택한다.

이 구조에서는:

- render가 빨리 끝난 후보가 우선되고
- identity drift가 있어도 자동 selection에 들어갈 수 있다
- candidate_count를 늘려도 실제로는 후보 품질 비교가 거의 없다

### 2. Existing quality scoring is readability-first only

현재 backend의 candidate quality scoring은:

- `quality_selector_hints`
- `positive_signals`
- `negative_signals`

를 사용해 `quality_score`를 계산한다.

하지만 이 score는 아직 아래를 강하게 다루지 않는다.

- same-person hold
- face / hair / wardrobe drift
- `읽히는 establish`를 만들기 위해 다른 사람으로 바뀌는 현상

### 3. Worker callback contract has no explicit identity gate yet

현재 worker callback의 structured quality assessment는 `quality` 중심이다.

즉 backend는 지금도 structured assessment를 읽을 수 있지만, `identity hold`를 별도 first-class signal로 다루지 않는다.

## Scope

이번 bounded fix는 아래만 다룬다.

- `Camila Duarte` V2 still lane only
- comic still candidate selection only
- bounded pilot helper auto-selection only

이번 단계에서 하지 않는 것:

- 다른 캐릭터로 확장
- frontend UI 변경
- full visual similarity model 도입
- 새 style canon 설계
- teaser 스타일 재튜닝
- stable path 승격

## Design Principles

### 1. Identity outranks readability

앞으로 candidate selection 우선순위는 아래 순서로 고정한다.

1. same-person hold
2. role readability
3. scene readability
4. artifact suppression
5. beauty / glamour score

즉 `establish가 잘 읽히지만 Camila가 아니면 탈락`이다.

### 2. Fail closed, not open

identity gate를 못 넘는 후보들만 있으면 helper는 조용히 골라선 안 된다.

대신:

- 해당 panel selection을 실패로 돌리고
- operator가 drift failure를 바로 보게 해야 한다

### 3. Reuse existing structured assessment first

이번 단계는 새 무거운 모델이나 새 UI를 붙이지 않는다.

먼저 재사용할 것은:

- worker callback의 `request_json`
- backend의 structured quality extraction
- existing render-job polling path

즉 기존 계약을 최대한 재사용하면서 `identity gate`만 추가한다.

## Proposed Changes

### A. Add identity-first assessment lanes to the callback contract

worker callback request_json 안의 structured assessment를 아래처럼 확장 가능하게 만든다.

- `identity_positive_signals`
- `identity_negative_signals`

허용 예시:

- positive
  - `camila face hold`
  - `hair silhouette hold`
  - `wardrobe family hold`
  - `same-person continuity`
- negative
  - `different face`
  - `hair redesign`
  - `wardrobe drift`
  - `different age read`
  - `different ethnicity read`

이번 단계에서는 worker가 이 값을 항상 채우지 않아도 된다.

중요한 건 backend가 이 구조를 받아들일 수 있어야 한다는 점이다.

### B. Compute identity gate separately from quality score

backend는 candidate마다 두 값을 다룬다.

- `identity_score`
- `quality_score`

이번 단계에서는 schema를 크게 넓히지 않고, 최소한 아래를 구현한다.

- structured request_json에서 identity 신호를 읽는다
- `identity_score`를 계산한다
- helper selection에서 `identity_score`가 threshold 미만이면 탈락시킨다

핵심은 `quality_score`가 높아도 `identity_score`가 낮으면 선택되지 않는다는 것이다.

### C. Add panel-role aware identity thresholds

panel role마다 허용 drift 폭이 같을 필요는 없다.

초기 기준:

- `closeup`
  - 가장 엄격
- `beat`
  - 엄격
- `insert`
  - 중간
- `establish`
  - 가장 느슨하지만, 여전히 same-person hold는 필요

즉 establish도 무조건 environment-first를 허용하는 것이 아니라, `작아져도 같은 사람으로 읽혀야 한다`.

### D. Change helper auto-selection from first-materialized to best-passing candidate

`launch_camila_v2_comic_pilot.py`는 아래처럼 바뀐다.

현재:

- panel마다 첫 materialized asset 선택

변경 후:

1. candidate_count만큼 기다림
2. panel render jobs / assets를 모두 읽음
3. `identity threshold`를 넘긴 후보만 남김
4. 남은 후보 중 가장 높은 composite candidate를 선택
5. 남는 후보가 없으면 helper 전체를 fail

즉 helper는 더 이상 `먼저 나온 그림`을 고르지 않는다.

### E. Composite candidate ranking

identity gate를 통과한 후보에 대해서만 composite ranking을 적용한다.

초기 ranking 원칙:

- `identity_score`가 floor를 넘는지 먼저 확인
- 그 다음 `quality_score`
- tie-breaker로:
  - role-specific readability notes
  - lower artifact penalties

이 단계에서는 `beauty-first tie-breaker`를 금지한다.

## Acceptance Criteria

이 fix가 통과하려면 아래가 만족되어야 한다.

1. helper가 더 이상 첫 materialized asset을 자동 선택하지 않는다.
2. identity threshold를 못 넘는 후보는 selection에서 제외된다.
3. same-person hold가 깨진 panel set이면 helper가 `fail closed`한다.
4. still acceptance를 다시 돌렸을 때, 선택된 4컷이 같은 Camila로 읽힌다.
5. still acceptance를 통과한 경우에만 teaser verification으로 넘어간다.

## Non-Goals

이번 단계는 아래를 해결하려 하지 않는다.

- full face-embedding similarity system
- 전 캐릭터 공통 identity scorer
- frontend identity-debug UI
- stable baseline 승격

이번 단계는 strictly `Camila V2 bounded still acceptance recovery`다.
