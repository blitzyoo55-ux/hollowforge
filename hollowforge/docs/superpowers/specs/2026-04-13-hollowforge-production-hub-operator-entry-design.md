# HollowForge Production Hub Operator Entry Design

Date: 2026-04-13

## Goal

`/production`를 단순 조회 화면이 아니라 실제 운영 진입점으로 바꾼다.

이번 설계의 목표는 아래 네 가지다.

1. shared production core에서 `work`, `series`, `production episode`를 직접 생성할 수 있게 한다.
2. `/production`에서 선택한 episode를 기준으로 `/comic`, `/sequences` 작업을 바로 시작하거나 재개하게 만든다.
3. `comic handoff`, `animation track`이 각각 같은 production episode를 기준으로 동작하도록 URL 계약을 고정한다.
4. 새 거대 엔진을 만들지 않고, 기존 comic/sequence 화면의 책임 경계를 유지한 채 연결성만 강화한다.

이 슬라이스의 핵심은 “새 authoring 기능 추가”가 아니라 “운영 진입점 정렬”이다.

## Approved Decisions

- operator entry surface: `/production`
- production hub role: `shared core creation + episode-level resume hub`
- downstream entry pattern: `URL query based context handoff`
- preferred entry behavior: `auto-open current if exactly one linked track exists`
- fallback behavior: `prefill create form if no linked track exists`
- ambiguity handling: `filter only when multiple linked tracks exist`
- current-track policy direction: `production episode당 comic current 1개, animation current 1개`

## Current System Fit

현재 HollowForge는 이미 다음을 갖고 있다.

- `works`, `series`, `production_episodes` shared core
- `comic_episodes.production_episode_id`
- `sequence_blueprints.production_episode_id`
- `/production` list/detail API
- `/comic` comic handoff surface
- `/sequences` animation track surface

즉 데이터 경계는 이미 생겼다.

부족한 부분은 두 가지다.

- production core를 UI에서 실제로 만들 수 없다
- `/production`에서 `/comic`, `/sequences`로 내려갈 때 “현재 맥락”이 이어지지 않는다

이 때문에 사용자는 여전히 `/comic`, `/sequences`에 직접 들어가서 다시 대상을 찾고 생성해야 한다.

## Problem Statement

핵심 문제는 기능 부족이 아니라 `entry contract` 부재다.

### 1. Production core가 읽기 전용에 가깝다

shared core를 도입했지만, 운영자가 여기서 새 episode를 시작하지 못하면 `/production`은 실제 허브가 되지 못한다.

### 2. Episode context가 화면 간에 유지되지 않는다

현재 `/comic`, `/sequences`는 production episode와 연결될 수 있지만, 허브에서 특정 episode를 선택해도 그 맥락으로 자동 진입하지 않는다.

### 3. 사람이 한 번 더 선택해야 한다

허브에서 episode를 보고도 downstream 화면에서 다시 대상을 골라야 하면 운영 허브의 가치가 약해진다.

### 4. 자동화 링크를 만들기 어렵다

향후 알림, 큐, 운영 문서, 외부 오케스트레이션에서 “이 episode를 바로 열어라” 같은 링크를 만들려면 URL 계약이 먼저 고정돼야 한다.

## Non-Goals

이번 슬라이스에서 하지 않는 것:

- current track를 DB constraint로 강제하는 것
- production episode edit/delete UI
- comic/animation 이력 관리 전용 UI
- CLIP STUDIO EX용 최종 authoring 기능 추가
- 외부 animation editor용 최종 export timeline 추가
- `/production` 안에서 comic/sequence 생성 전 과정을 wizard로 통합하는 것

## Considered Approaches

### 1. Creation UI Only

`/production`에서 work/series/episode만 만들고, downstream 진입은 기존처럼 각 화면에서 다시 고른다.

장점:

- 구현이 단순하다
- 경계가 비교적 명확하다

단점:

- 운영 허브로서 체감 가치가 낮다
- 사람이 다시 고르는 과정이 남는다
- 자동화 링크 가치가 약하다

부족하다.

### 2. Filter-Only Handoff

`/production`에서 `/comic`, `/sequences`로 갈 때 `production_episode_id`만 넘기고, downstream에서는 필터만 적용한다.

장점:

- 기존 화면 구조를 크게 안 건드린다
- 다중 linked 상황을 다루기 쉽다

단점:

- 사람이 마지막 선택을 다시 해야 한다
- 허브가 “준비만 해주는 화면”에 머문다
- 자동화 효율이 떨어진다

중간 단계로는 가능하지만, 최종 운영 UX로는 약하다.

### 3. Auto-Open Current With Guard Rails

`/production`에서 episode를 선택해 downstream으로 갈 때:

- linked track이 정확히 1개면 자동으로 그 상세를 연다
- linked track이 없으면 create form을 prefill한다
- linked track이 여러 개면 필터된 선택 화면으로 보낸다

장점:

- 사람 기준 조작 수가 가장 적다
- 자동화 링크가 강해진다
- production episode를 중심으로 작업 맥락이 유지된다

단점:

- URL과 진입 상태 규칙을 명확히 관리해야 한다
- downstream 화면이 컨텍스트 해석 로직을 가져야 한다

현재 목표에 가장 적합하다.

## Recommended Direction

권장 방향은 `Auto-Open Current With Guard Rails`다.

운영자는 `/production`에서 아래 두 가지를 한다.

1. 새 work/series/episode를 만든다
2. 기존 episode를 기준으로 comic/animation 작업을 시작하거나 재개한다

이 구조면 `/production`는 shared core creation surface이면서도, 실제 작업 재개 허브가 된다.

## Operator Flow

### New Episode Start

1. 운영자는 `/production`에서 work를 선택하거나 새로 만든다
2. 필요하면 series를 선택하거나 새로 만든다
3. episode를 생성한다
4. episode row에서 `Open Comic Handoff` 또는 `Open Animation Track`을 누른다
5. linked track이 없으면 downstream create form이 prefill된 상태로 열린다

### Resume Existing Comic Work

1. 운영자는 `/production`에서 episode row를 본다
2. `Open Comic Handoff`를 누른다
3. linked comic current가 정확히 1개면 그 detail을 바로 연다

### Resume Existing Animation Work

1. 운영자는 `/production`에서 episode row를 본다
2. `Open Animation Track`을 누른다
3. linked animation current가 정확히 1개면 그 blueprint/detail을 바로 연다

### Ambiguous History

linked track이 여러 개면 자동 진입하지 않는다.

이 경우 downstream 화면은:

- 해당 `production_episode_id`로 필터된 후보만 보여준다
- 사용자가 현재 작업 대상을 고르게 한다

이 슬라이스에서는 ambiguity를 숨기지 않고 드러내는 편이 맞다.

## Route And State Contract

전역 상태 저장소를 새로 만들지 않는다.

컨텍스트 전달은 URL query를 표준 계약으로 사용한다.

### `/production -> /comic`

- `production_episode_id=<id>`
- `mode=open_current | create_from_production`

### `/production -> /sequences`

- `production_episode_id=<id>`
- `mode=open_current | create_from_production`

이 계약의 장점은 다음과 같다.

- 사람이 새로고침하거나 링크를 공유해도 컨텍스트가 유지된다
- 운영 문서와 알림에서 바로 deep link를 만들 수 있다
- downstream 화면 상태가 숨겨지지 않는다

## Downstream Screen Rules

### `/comic`

`open_current`

- linked comic track이 정확히 1개면 그 episode detail을 자동 로드한다
- 여러 개면 해당 production episode 기준 후보 목록만 보여준다

`create_from_production`

- production episode 정보를 기준으로 create/import form 기본값을 채운다
- 최소한 `production_episode_id`, `work_id`, `series_id`, `content_mode`, `title`, `synopsis`를 반영한다

### `/sequences`

`open_current`

- linked animation track이 정확히 1개면 그 blueprint/detail을 자동 선택한다
- 여러 개면 해당 production episode 기준 blueprint 목록만 보여준다

`create_from_production`

- blueprint form 기본값을 production episode 기준으로 채운다
- 최소한 `production_episode_id`, `work_id`, `series_id`, `content_mode`를 반영한다

## UI Structure

### `/production`

이번 슬라이스의 UI 구조는 아래처럼 둔다.

#### 1. Work Creation Panel

- 새 work 생성
- 생성 후 episode form에서 바로 선택 가능해야 함

#### 2. Series Creation Panel

- 기존 work에 series 생성
- 생성 후 episode form에서 바로 선택 가능해야 함

#### 3. Episode Creation Panel

핵심 입력:

- work
- series (optional)
- title
- synopsis
- content_mode
- target_outputs

episode 생성이 이번 화면의 중심이다.

#### 4. Episode Registry

이미 구현된 registry를 유지하되, 아래를 강화한다.

- linked current 상태 표시
- `Open Comic Handoff`
- `Open Animation Track`
- 버튼이 내부적으로 `open_current` 또는 `create_from_production` 링크를 생성

## Data And Responsibility Boundary

이 슬라이스는 새 core 테이블을 추가하지 않는다.

필요한 것은 기존 shared core와 linked track 정보를 이용한 `entry orchestration`이다.

책임은 이렇게 나눈다.

### Production Hub

- shared core 생성
- downstream 링크 계산
- current linkage 가시화

### Comic Handoff

- comic episode 생성/불러오기
- production context 해석
- handoff 작업 재개

### Animation Track

- sequence blueprint 생성/불러오기
- production context 해석
- rough-cut 작업 재개

## Minimal File Impact

이번 설계가 의미하는 파일 범위는 아래와 같다.

### Backend

- `backend/app/models.py`
  - production create request/response를 frontend에서 쓸 수 있게 유지
- `backend/app/routes/production.py`
  - 이미 있는 create endpoints를 그대로 사용

추가 백엔드 기능은 최소화한다.

### Frontend

- `frontend/src/api/client.ts`
  - production create clients 추가
- `frontend/src/pages/ProductionHub.tsx`
  - 생성 패널 + downstream link 계산
- `frontend/src/pages/ProductionHub.test.tsx`
  - 생성 UI와 link mode 테스트
- `frontend/src/pages/ComicStudio.tsx`
  - URL query 해석
- `frontend/src/pages/ComicStudio.test.tsx`
  - open_current / create_from_production 테스트
- `frontend/src/pages/SequenceStudio.tsx`
  - URL query 해석
- `frontend/src/pages/SequenceStudio.test.tsx`
  - open_current / create_from_production 테스트

## Risks

### 1. Linked history ambiguity

같은 production episode에 linked comic/animation 이력이 여러 개 있을 수 있다.

대응:

- 이번 슬라이스에서는 자동 진입을 멈추고 후보 선택으로 fallback
- 후속 슬라이스에서 `current track` 개념을 명시적으로 강화

### 2. Prefill shape mismatch

production episode 정보와 downstream create form이 완전히 1:1로 대응하지 않을 수 있다.

대응:

- 이번 슬라이스는 “존재하는 필드만 prefill” 원칙으로 간다
- 억지 매핑은 하지 않는다

### 3. 화면 책임 과확장

`/production`가 너무 많은 것을 한 번에 하려 하면 다시 비대해진다.

대응:

- 이번 슬라이스는 생성 + 진입 orchestration까지만
- edit/history/current-admin은 후속 과제로 분리

## Success Criteria

아래가 만족되면 이번 슬라이스는 성공이다.

1. 운영자가 `/production`에서 work, series, episode를 생성할 수 있다.
2. 새 episode 생성 직후 `/comic` 또는 `/sequences`로 맥락을 잃지 않고 이동할 수 있다.
3. linked current가 정확히 1개면 downstream 화면이 자동으로 해당 작업을 연다.
4. linked current가 없으면 downstream 생성 화면이 production context로 prefill된다.
5. linked current가 여러 개면 잘못된 자동 진입 없이 필터된 선택 상태로 떨어진다.
6. 구현 후에도 `/production`는 shared core 허브이고, `/comic`와 `/sequences`는 각자 handoff/review surface라는 경계가 유지된다.

## Recommendation

이번 슬라이스는 `/production`를 실제 운영 진입점으로 만드는 데 필요한 최소한이면서, 이후 자동화와 외부 툴 링크까지 자연스럽게 확장 가능한 기준점이다.

다음 단계는 이 spec을 기준으로 implementation plan을 작성하고, 프론트 중심으로 TDD 순서의 태스크로 쪼개 실행하는 것이다.
