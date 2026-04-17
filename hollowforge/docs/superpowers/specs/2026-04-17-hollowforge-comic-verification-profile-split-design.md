# HollowForge Comic Verification Profile Split Design

기준일: 2026-04-17

## Goal

`HollowForge`의 comic verification 경로를 두 가지 운영 목적에 맞게 분리한다.

- 빠른 운영 점검용 `smoke`
- 실제 이미지 materialization과 layered handoff까지 확인하는 `full`

이번 단계의 목표는 “스크립트를 하나 더 만든다”가 아니다.

- 운영자가 평소 상태 점검을 빠르게 돌릴 수 있어야 한다
- 실제 품질 검증은 로컬 `ComfyUI` 렌더 시간을 전제로 별도 budget을 가져야 한다
- 두 경로가 서로 다른 성공 기준을 가져야 한다
- CLI와 테스트가 어떤 검증을 수행하는지 이름만 보고 구분 가능해야 한다

## Current State

현재 worktree에는 두 개의 관련 엔트리포인트가 있다.

- `backend/scripts/launch_comic_remote_render_smoke.py`
- `backend/scripts/launch_comic_one_panel_verification.py`

실제 동작은 아래와 같다.

1. `launch_comic_remote_render_smoke.py`
   `remote_worker` 경로를 직접 검증한다.
2. `launch_comic_one_panel_verification.py`
   one-panel episode 생성부터 dialogue, page assembly, layered export까지 모두 확인한다.

이번 세션에서 확인된 핵심 사실은 아래와 같다.

1. 현재 로컬 실경로는 `8012 -> 8611 -> 8188` 이다.
2. `ComfyUI`는 정상 완료 후 실제 PNG를 생성한다.
3. 기존 타임아웃 실패의 원인은 callback wiring이 아니라 기본 poll budget 부족이었다.
4. 실제 1패널 렌더는 약 4분이 걸릴 수 있다.

즉 현재 스크립트 문제는 “작업 실패”가 아니라 “검증 책임이 뒤섞여 있다”는 점이다.

## Problem Statement

현재 구조는 운영 스모크와 실검증을 충분히 분리하지 못한다.

### 1. one-panel verification이 너무 많은 책임을 동시에 가진다

현재 `launch_comic_one_panel_verification.py`는 아래를 한 번에 검증한다.

- episode 생성
- panel render queue
- remote render completion
- dialogue generation
- page assembly
- layered export
- dry-run handoff validation

이 자체는 필요하다. 문제는 이 경로가 “평소 점검용”으로도 사용되기 쉽다는 점이다.

### 2. 빠른 상태 점검과 실제 품질 검증의 시간 예산이 다르다

운영자는 자주 아래 질문에 답하고 싶다.

- API가 살아 있는가
- panel queue가 깨지지 않았는가
- assembly/export contract가 유지되는가

이 질문은 짧은 시간 안에 답할 수 있어야 한다.

반면 실제 `remote_worker + ComfyUI` 렌더 확인은 몇 분이 걸릴 수 있으며, 여기에는 더 긴 poll budget이 필요하다.

### 3. CLI 이름만으로 검증 강도가 드러나지 않는다

현재는 `remote_render_smoke`와 `one_panel_verification`이 일부는 겹치고 일부는 다르다.

문제는 아래다.

- 어떤 스크립트가 “빠른 운영 체크”인지 명확하지 않다
- 어떤 스크립트가 “실제 image materialization”을 요구하는지 바로 드러나지 않는다
- 향후 자동화에서 잘못된 스크립트를 고르기 쉽다

## Non-Goals

이번 단계에서 하지 않는 것:

- comic render recipe 자체 변경
- model / LoRA 교체
- character canon 구조 변경
- layered handoff 포맷 변경
- CLIP Studio 편집 단계 자동화
- animation pipeline 통합

## Considered Approaches

### 1. 기존 스크립트 하나에 `--verification-profile`만 추가

장점:

- 구현량이 가장 작다
- 내부 로직을 재사용하기 쉽다

단점:

- 운영자가 옵션을 틀리게 줄 가능성이 높다
- 자동화가 스크립트 이름만 보고 목적을 판단하기 어렵다
- “빠른 점검”과 “실검증”의 분리가 문서에만 남고 CLI 표면에는 약하게 드러난다

단독 해법으로는 부족하다.

### 2. 스크립트 두 개를 완전히 분리하고 로직도 각각 유지

장점:

- 역할이 명확하다
- 운영자 입장에서 이해하기 쉽다

단점:

- 코드 중복이 늘어난다
- 기본값과 검증 계약이 다시 어긋날 수 있다

장기 유지보수에 불리하다.

### 3. 공용 프로필 레이어 + 명시적인 엔트리포인트 분리

장점:

- CLI 표면은 명확하다
- 내부 default contract는 한 곳에서 관리할 수 있다
- 테스트가 profile별 책임을 직접 검증할 수 있다
- 향후 `benchmark`, `ci_smoke`, `full_runtime` 같은 프로필 확장이 쉽다

단점:

- 기존 스크립트를 약간 재구성해야 한다

현재 단계에 가장 적합하다.

## Recommended Direction

권장 방향은 `공용 verification profile layer + 명시적 엔트리포인트 분리`다.

핵심 원칙은 아래와 같다.

1. `smoke`는 빠른 운영 점검이다.
2. `full`은 실제 remote image materialization까지 포함한 실검증이다.
3. profile의 default contract는 공용 상수 또는 resolver에서 관리한다.
4. 엔트리포인트 이름은 목적을 직접 드러내야 한다.

즉 앞으로의 표면 구조는 아래가 된다.

- `launch_comic_one_panel_smoke.py`
- `launch_comic_one_panel_verification.py`

내부에서는 공용 profile resolver가 아래를 제공한다.

- `execution_mode`
- `candidate_count`
- `render_poll_attempts`
- `render_poll_sec`
- 필요 시 향후 `story lane`, `allow_synthetic_fallback`, `materialization_required`

## Design

### 1. Verification profile model

공용 프로필 구조를 도입한다.

예상 필드는 아래와 같다.

- `name`
- `execution_mode`
- `candidate_count`
- `render_poll_attempts`
- `render_poll_sec`
- `requires_materialized_asset`

이번 단계에서는 복잡한 class보다, 기존 스크립트와 잘 맞는 `named tuple`, `dataclass`, 또는 상수 dict면 충분하다.

핵심은 “default contract를 한 곳에서 읽는다”는 점이다.

### 2. Smoke profile

`smoke`의 목적은 운영 경로가 살아 있는지 빠르게 확인하는 것이다.

계약은 아래와 같다.

- 기본 `execution_mode = local_preview`
- 짧은 poll budget
- 최소 candidate
- `render queue -> dialogue -> assembly -> export` 흐름 유지
- 실제 remote worker materialization은 요구하지 않음

즉 `smoke`는 “오케스트레이션과 handoff contract가 유지되는가”를 묻는다.

### 3. Full profile

`full`의 목적은 실제 이미지가 생성되고, 그 산출물이 layered handoff까지 이어지는지 확인하는 것이다.

계약은 아래와 같다.

- 기본 `execution_mode = remote_worker`
- 긴 poll budget
- materialized asset 필수
- dry-run export / layered handoff 필수

즉 `full`은 “실제 production lane이 end-to-end로 살아 있는가”를 묻는다.

### 4. Entry-point ownership

`launch_comic_one_panel_verification.py`는 `full` 기본값을 유지한다.

이 스크립트는 아래 상황에서 쓴다.

- ComfyUI 상태를 포함한 실제 runtime 검증
- handoff 패키지 생성 확인
- 렌더 품질 경로까지 포함한 파일 생성 검증

새 `launch_comic_one_panel_smoke.py`는 `smoke` 프로필을 강제한다.

이 스크립트는 아래 상황에서 쓴다.

- 배포 후 기본 상태 점검
- 로컬 메모리 상황이 나쁠 때 빠른 오케스트레이션 확인
- 작업 전에 API/assembly/export contract만 먼저 확인할 때

### 5. Relationship with remote render smoke

기존 `launch_comic_remote_render_smoke.py`는 계속 유지한다.

이 스크립트는 “remote render lane 자체”를 bounded하게 보는 도구다.

정리하면 역할은 아래처럼 된다.

- `launch_comic_remote_render_smoke.py`
  remote worker still lane 전용 점검
- `launch_comic_one_panel_smoke.py`
  one-panel orchestration + handoff 빠른 점검
- `launch_comic_one_panel_verification.py`
  one-panel end-to-end full 검증

### 6. Test strategy

테스트는 profile contract를 직접 고정해야 한다.

최소 회귀 범위는 아래다.

1. `one_panel_smoke`
   `local_preview`, 짧은 poll, 빠른 기본값 사용
2. `one_panel_verification`
   `remote_worker`, 긴 poll, materialized asset 요구
3. 기존 `remote_render_smoke`
   긴 poll 기본값 유지

이번 단계에서 중요한 것은 “기본값이 의미를 갖는다”는 점이다.

운영자가 CLI 인자를 하나도 주지 않았을 때도 의도한 검증 강도가 보장되어야 한다.

## Success Criteria

이번 단계의 성공 기준은 아래와 같다.

1. 운영자는 빠른 one-panel smoke를 별도 엔트리포인트로 실행할 수 있다.
2. full verification은 현재처럼 실제 materialized asset과 layered handoff를 계속 검증한다.
3. profile default contract가 테스트로 고정된다.
4. 스크립트 이름만 보고 검증 목적을 구분할 수 있다.

## Implementation Notes

구현 순서는 아래를 권장한다.

1. profile contract를 테스트로 먼저 고정한다.
2. `one_panel_smoke` 엔트리포인트를 추가한다.
3. `one_panel_verification`을 full profile 기반으로 정리한다.
4. 관련 pytest를 돌린다.
5. 가능하면 로컬에서 `smoke`와 `full`을 각각 1회씩 실검증한다.
