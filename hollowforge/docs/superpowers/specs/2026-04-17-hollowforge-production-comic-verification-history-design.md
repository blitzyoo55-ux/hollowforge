# HollowForge Production Comic Verification History Design

Date: 2026-04-17

## Goal

`/production`을 단순 명령 복사 진입점에서, 최근 comic verification 운영 상태를 읽을 수 있는 실제 운영 허브로 확장한다.

이번 단계의 목표는 검증 실행 자체를 UI에 붙이는 것이 아니다.

- canonical verification 명령 표면은 유지한다.
- 최근 preflight / suite 결과를 backend에 영속화한다.
- `/production`에서 최근 성공/실패와 실패 lane을 안정적으로 읽어 보여준다.

성공 기준은 아래 세 가지다.

1. comic verification 실행 결과가 파일이나 터미널 기억이 아니라 backend 기록으로 남는다.
2. `/production`에서 최근 검증 상태를 읽기 전용으로 확인할 수 있다.
3. 이후 자동 재실행, 추이 분석, operator note 같은 후속 기능이 같은 run 모델 위에 자연스럽게 확장된다.

## Current State

현재 HollowForge는 아래 상태까지 도달해 있다.

- `/production`
  - global `Verification Ops` 카드에서 canonical command를 복사할 수 있음
- `backend/scripts/check_comic_remote_render_preflight.py`
  - remote still lane preflight를 실행하고 stdout에 결과를 출력함
- `backend/scripts/run_comic_verification_suite.py`
  - `smoke -> full -> remote` suite를 실행하고 summary marker를 stdout에 출력함
- README / STATE / SOP
  - operator command contract는 문서상으로 정리돼 있음

즉, verification 실행 계약은 이미 존재한다.

부족한 점은 실행 결과가 운영 허브에 남지 않는다는 것이다.

## Problem Statement

문제는 실행 도구가 없어서가 아니라, 운영 결과가 시스템 상태로 남지 않는다는 점이다.

### 1. `/production`은 아직 실행 결과를 모른다

현재 `/production`은 어떤 명령을 실행해야 하는지는 알려주지만, 최근에 무엇이 성공했고 어디서 실패했는지는 전혀 모른다.

### 2. verification 상태가 터미널과 파일에 갇혀 있다

preflight와 suite는 stdout marker를 출력하지만, 이 정보는 터미널 세션이 끝나면 운영 표면에서 사라진다.

### 3. 파일 기반 읽기는 운영 계약으로 약하다

로그 파일이나 JSON artifact를 읽는 방식은 빠를 수 있지만, 실행 환경과 파일 경로에 강하게 의존한다. `/production`을 운영 허브로 만들려면 backend API와 DB를 통한 안정적 read model이 필요하다.

### 4. 현재 verification은 per-episode 작업이 아니다

comic verification suite는 특정 production episode 하나를 직접 대상으로 실행하는 계약이 아니다. 따라서 저장 구조도 per-episode history가 아니라 `global comic ops run history`가 되어야 한다.

## Non-Goals

이번 단계에서 하지 않는 것:

- `/production`에서 shell command를 직접 실행하는 API
- live polling / streaming logs / tail view
- 실행 중(`in_progress`) 상태 추적
- per-episode verification history
- animation verification history
- 상세 드릴다운 페이지
- rerun 버튼

## Considered Approaches

### 1. 파일 기반 읽기 전용 adapter

스크립트가 남긴 artifact를 `/production`이 직접 읽는다.

장점:

- 빠르게 붙일 수 있다
- migration이 없다

단점:

- 파일 경로와 실행 환경에 종속된다
- 최근 성공/실패 선택 규칙이 프론트나 adapter에 새어 나온다
- 향후 자동화 확장성이 낮다

운영 허브로는 약하다.

### 2. production 상태 전용 단일 summary 테이블

최근 상태만 저장하고 과거 이력은 버린다.

장점:

- 구현이 비교적 가볍다
- `/production`에 필요한 최소 정보만 유지한다

단점:

- 최근 실패 추이나 재현 경로를 복원하기 어렵다
- 결국 history 요구가 생기면 별도 run 테이블로 다시 이동할 가능성이 높다

중간 단계로는 가능하지만, 구조적으로 덜 안정적이다.

### 3. 별도 `comic_verification_runs` 테이블 추가

각 실행을 1행으로 저장하고, `/production`은 이 이력을 읽는 summary API만 사용한다.

장점:

- run history가 명확하다
- 최근 1건 요약과 최근 5건 목록을 안정적으로 만들 수 있다
- 이후 자동화, 추이 분석, operator note 확장이 자연스럽다

단점:

- migration, repository, route, client, frontend surface를 모두 추가해야 한다

현재 목표에 가장 적합하다.

## Recommended Direction

권장 방향은 별도 `comic_verification_runs` 테이블 기반의 global run history 모델이다.

핵심 설계는 아래와 같다.

- 저장 단위는 `1 row = 1 verification execution`
- 실행 종류는 `run_mode`로 구분한다
  - `preflight`
  - `suite`
  - `full_only`
  - `remote_only`
- `/production`은 여러 endpoint를 조합하지 않고, 하나의 summary endpoint만 읽는다
- 스크립트는 stdout을 유지하면서 종료 시점에 backend로 최종 결과를 1회 POST 한다

이 방향의 장점은 operator contract를 `command surface + durable history`로 한 단계 올릴 수 있다는 점이다.

## Data Model

새 테이블 이름은 `comic_verification_runs`로 둔다.

### Columns

- `id`
- `run_mode`
- `status`
- `overall_success`
- `failure_stage`
- `error_summary`
- `base_url`
- `total_duration_sec`
- `started_at`
- `finished_at`
- `stage_status_json`
- `created_at`
- `updated_at`

### Status Semantics

- `status`
  - `completed`
  - `failed`
- 이번 단계에서는 `in_progress`를 저장하지 않는다.
- run row는 실행 종료 후 최종 상태로만 기록한다.

### Stage Status Payload

단계별 세부 정보는 컬럼을 늘리지 않고 `stage_status_json`에 보관한다.

예시:

```json
{
  "preflight": {
    "status": "passed",
    "duration_sec": 1.14,
    "error_summary": null
  },
  "smoke": {
    "status": "passed",
    "duration_sec": 42.8,
    "error_summary": null
  },
  "full": {
    "status": "failed",
    "duration_sec": 512.4,
    "error_summary": "remote poll timeout"
  },
  "remote": {
    "status": "skipped",
    "duration_sec": null,
    "error_summary": null
  }
}
```

이 구조면 `/production`이 필요한 요약을 만들 수 있고, 향후 상세 표시도 가능하다.

## Write Path

쓰기 경계는 backend HTTP endpoint로 둔다.

### Endpoint

- `POST /api/v1/production/comic-verification/runs`

### Request Shape

최소 payload는 아래 필드를 가진다.

- `run_mode`
- `status`
- `overall_success`
- `failure_stage`
- `error_summary`
- `base_url`
- `total_duration_sec`
- `started_at`
- `finished_at`
- `stage_status`

### Why HTTP Instead of Direct DB Writes

스크립트가 SQLite를 직접 열어 쓰는 방식은 피한다.

이유:

- DB write logic이 CLI마다 복제된다
- backend schema 변경 시 스크립트 결합도가 높아진다
- 나중에 실행 주체가 로컬 CLI에서 다른 operator/worker로 바뀌어도 기록 계약을 재사용하기 어렵다

따라서 기록은 backend endpoint가 담당하고, CLI는 결과 payload만 전송한다.

## Read Path

프론트는 run row들을 직접 조합하지 않게 한다.

### Endpoint

- `GET /api/v1/production/comic-verification/summary`

### Response Shape

summary 응답은 `/production` 전용 read model로 둔다.

- `latest_preflight`
- `latest_suite`
- `recent_runs`

`recent_runs`는 최근 5건만 반환한다.

이 설계의 장점은 프론트가 간단해지고, “무엇을 latest로 볼지” 같은 규칙이 backend에 고정된다는 점이다.

## UI Surface

`/production`에서 기존 `Verification Ops` 카드는 그대로 유지한다.

그 아래에 읽기 전용 `Verification History` 블록을 추가한다.

### Summary Cards

상단에는 요약 2개만 둔다.

- `Latest Preflight`
- `Latest Suite`

각 카드에는 아래 정보만 표시한다.

- `status`
- `started_at`
- `finished_at`
- `duration`
- `failure_stage`

### Recent Runs Table

그 아래에 최근 5건 테이블을 둔다.

컬럼:

- `started_at`
- `mode`
- `status`
- `failure_stage`
- `duration`
- `error_summary`

이번 단계에서는 이력 상세 드릴다운이나 로그 전문 조회는 넣지 않는다.

## Failure Handling

이번 단계의 기록 단위는 `completed run history`로 제한한다.

- 실시간 상태는 저장하지 않는다
- preflight나 suite가 종료되면 최종 결과를 기록한다
- 실패한 경우에도 `status=failed`와 함께 기록을 남겨야 한다

### Persistence Failure Rule

기록 저장이 실패하면 CLI는 그 사실을 명시적으로 출력하고, 실행도 실패로 간주하는 것을 권장한다.

이유:

- 검증은 성공했더라도 운영 기록이 남지 않으면 `/production`에 거짓 양성처럼 보일 수 있다
- 이번 기능의 목적은 “verification correctness”뿐 아니라 “history persistence correctness”까지 운영 계약에 포함시키는 것이다

즉, 성공 조건은 아래 둘을 함께 만족해야 한다.

1. verification 실행이 올바르게 끝남
2. 결과가 backend history에 저장됨

## Script Integration

### Preflight Script

`check_comic_remote_render_preflight.py`는 현재 체크 결과를 stdout에만 출력한다.

이 스크립트는 종료 직전에 다음을 수행하도록 확장한다.

- 체크 결과들을 구조화된 payload로 정규화
- PASS/FAIL/SKIP 결과를 `stage_status.preflight` 중심 모델로 변환
- backend write endpoint에 최종 1회 POST

### Suite Runner

`run_comic_verification_suite.py`는 현재 summary marker dict를 stdout으로 출력한다.

이 summary dict를 그대로 재사용해서 아래를 만든다.

- `run_mode`
- `overall_success`
- `failure_stage`
- `total_duration_sec`
- `stage_status`

그 다음 backend write endpoint에 최종 1회 POST 한다.

핵심은 사람용 stdout을 버리지 않고, operator-facing persistence만 추가하는 것이다.

## Testing Strategy

### Backend

- `test_production_routes.py`
  - write endpoint 저장 테스트
  - summary endpoint read model 테스트
- schema test
  - `comic_verification_runs` 테이블 존재 검증
- repository/service tests
  - 최근 5건 정렬
  - `latest_preflight` 선택 규칙
  - `latest_suite` 선택 규칙

### Scripts

- preflight script
  - check 결과를 write payload로 변환하는 순수 함수 테스트
- suite runner
  - summary marker dict를 write payload로 변환하는 순수 함수 테스트
- POST 실패 시 CLI exit가 non-zero가 되는지 검증

### Frontend

- `ProductionHub.test.tsx`
  - `Verification History` 블록 렌더링
  - 성공/실패 상태 badge
  - 최근 5건 표시
  - empty history 상태
- 필요 시 history 컴포넌트 단위 테스트 추가

## Rollout Order

1. backend migration + models + repository
2. production routes에 write/read API 추가
3. preflight / suite CLI에 history POST 연동
4. frontend client + `/production` history UI 추가
5. backend tests, frontend tests, build, local live smoke

## Out of Scope

이번 단계에서 계속 제외되는 항목:

- live polling
- logs 전문 조회
- rerun button
- per-episode linkage
- animation verification history
- operator notes
- alerting

## Expected Outcome

이 설계가 구현되면 `/production`은 아래 두 역할을 동시에 갖는다.

1. canonical verification command surface
2. recent comic verification operating history surface

즉, operator는 `/production`에서 “무엇을 실행해야 하는가”와 “최근에 무엇이 성공/실패했는가”를 함께 볼 수 있게 된다.
