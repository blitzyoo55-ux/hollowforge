# HollowForge Animation Stale Job Reconciliation Design

Date: 2026-04-05

## Goal

animation worker 또는 backend가 재시작된 뒤 `queued`, `submitted`,
`processing` 상태로 남아 버린 stale animation job을 자동으로 정리하고,
operator가 기존 teaser/comic helper로 안전하게 `rerun`할 수 있게 만든다.

이번 단계의 목표는 세 가지다.

- worker restart 뒤 `animation_jobs`와 `worker_jobs`에 남는 stale 상태 제거
- late callback이나 오래된 worker state가 terminal backend state를 덮어쓰지 못하게 보호
- operator가 새로운 retry 시스템 없이 기존 helper로 다시 실행할 수 있게 고정

핵심은 `resume`이 아니라 `fail then rerun`이다.

## Current State

stable teaser derivative 경로 자체는 검증됐다.

- canonical teaser helper:
  - `backend/scripts/launch_comic_teaser_animation_smoke.py`
- latest successful teaser job:
  - `animation_job_id = c2c84a11-7c13-4b71-bd5b-f0025d3ef5a7`
  - `output_path = outputs/e0bc969d-d6c1-4bd9-941c-1bf7eeae5a21.mp4`
- latest successful worker job:
  - `worker_job_id = e0bc969d-d6c1-4bd9-941c-1bf7eeae5a21`

하지만 같은 session 중 earlier teaser launch 하나는 stale로 남아 있다.

- backend animation job:
  - `267a0a8d-8ed2-42e6-a359-d61f8542bd0c`
  - status: `processing`
- worker job:
  - `05c8901a-775a-4836-9b2e-77b4d8194080`
  - status: `processing`
  - `updated_at = 2026-04-05T13:56:09.352022+00:00`

실제 evidence상 이 job은 더 이상 진행되지 않고, restart 이전 상태가 남아 있는 orphan에
가깝다. 반면 worker에는 startup stale cleanup이 없고, backend animation callback도
comic remote render 쪽처럼 late regression을 적극적으로 막지 않는다.

generation 쪽에는 이미 startup stale cleanup 패턴이 있다.

- `backend/app/services/generation_service.py`
  - `cleanup_stale()`
  - non-terminal generation을 `failed / Server restarted`로 정리

animation 쪽에는 동일한 운영 규칙이 아직 없다.

## Problem Statement

지금 stale animation job 문제가 생기는 이유는 두 가지다.

1. worker process가 내려가면 in-flight `worker_jobs`가 terminal state로 정리되지 않는다.
2. backend `animation_jobs`는 worker callback에 크게 의존하므로, worker가 죽거나 callback이
   누락되면 `processing`으로 남는다.

이 상태를 방치하면 operator는 실제로 끝난 작업인지, 죽은 작업인지, 다시 실행해도 되는지
판단하기 어렵다. 특히 teaser helper는 성공 사례가 이미 있는 상태라서, 다음 필요한 것은
새 animation system이 아니라 `운영 복구 규칙`이다.

## Considered Approaches

### 1. Manual Reconcile Helper Only

backend script 또는 route 하나를 두고 stale job을 수동 정리한다.

장점:

- 구현이 작다
- restart path를 크게 안 건드린다

단점:

- worker restart 직후 stale가 자동으로 정리되지 않는다
- operator가 매번 “먼저 reconcile”을 기억해야 한다
- stale state가 오래 남으면 UI/ops 해석이 흔들린다

이 방향은 운영 규칙을 사람에게 떠넘긴다.

### 2. Startup Fail Then Rerun

worker startup 시 non-terminal `worker_jobs`를 전부 `failed`로 정리하고,
callback으로 backend `animation_jobs`를 best-effort로 맞춘다. 동시에 backend 쪽에도
별도 stale reconciliation pass를 두어 callback 누락이나 backend restart 뒤에도 terminal
state를 따라잡게 한다. 이후 operator는 기존 teaser helper나 preset launch로 새 job을
다시 실행한다.

장점:

- 결정적이다
- generation stale cleanup 패턴과 철학이 맞다
- worker가 중간 상태를 “재개 가능”하다고 착각하지 않는다
- callback 누락까지 backend 쪽에서 보정할 수 있다
- 구현 범위가 여전히 작고 테스트하기 쉽다

단점:

- restart 직전 frame이 몇 장 생성됐더라도 이어받지 않는다
- operator가 rerun 한 번은 해줘야 한다

이번 단계에 가장 적합하다.

### 3. Resume On Startup

worker가 restart 뒤 stale `worker_jobs`를 다시 읽고 ComfyUI prompt 상태를 추적해서
이어서 처리한다.

장점:

- 이론상 재계산을 줄일 수 있다
- 긴 animation run에는 더 효율적일 수 있다

단점:

- prompt/history/frame/output 복구 조건이 복잡하다
- orphaned ComfyUI prompt, duplicate callback, partial mp4 assembly 같은 edge case가 많다
- 이번 문제보다 범위가 훨씬 크다

지금 단계에서는 과설계다.

## Recommended Direction

권장 방향은 `2. Startup Fail Then Rerun`이다.

원칙은 아래와 같다.

- restart는 in-flight animation job의 terminal event로 취급
- stale 상태는 자동으로 `failed` 정리
- backend terminal state는 late callback으로 되돌아가지 않음
- rerun은 새 animation job id로 수행
- operator-facing retry surface는 기존 helper 재사용

즉 canonical recovery flow는 다음과 같다.

`worker restart -> stale worker_jobs failed(Worker restarted) -> callback -> backend animation_jobs failed(Worker restarted) -> operator rerun helper -> new animation job`

## In Scope

- worker startup stale cleanup
- stale worker job의 failed callback propagation
- backend-side stale animation reconciliation pass
- backend animation callback의 terminal-state precedence hardening
- teaser helper/operator rerun contract 유지
- unit/integration test coverage

## Out Of Scope

- ComfyUI prompt resume
- partial frame reuse
- new retry queue system
- animation shot registry
- publish automation
- general-purpose animation orchestration refactor
- broad README/STATE polishing

## Design Details

## Worker Startup Cleanup Rule

worker lifespan 초기화 직후 아래 상태의 `worker_jobs`를 stale로 간주한다.

- `queued`
- `submitted`
- `processing`

startup cleanup는 이 row들을 아래처럼 바꾼다.

- `status = failed`
- `error_message = Worker restarted`
- `completed_at = now`
- `updated_at = now`

그 후 callback 정보가 있는 row에 대해서는 HollowForge backend로 best-effort failed callback을
보낸다.

callback payload:

```json
{
  "status": "failed",
  "external_job_id": "<existing external_job_id if any>",
  "external_job_url": "<existing external_job_url if any>",
  "error_message": "Worker restarted"
}
```

여기서 `output_path`는 보내지 않는다.

## Backend Stale Reconciliation Pass

worker callback만으로 backend stale를 전부 정리하는 것은 충분하지 않다. 따라서 backend도
자기 쪽 non-terminal `animation_jobs`를 worker state와 대조하는 reconciliation pass를
가져야 한다.

대상 row:

- `executor_mode = remote_worker`
- `status IN ('queued', 'submitted', 'processing')`
- `external_job_id`가 비어 있지 않음

reconciliation source:

- worker `GET /api/v1/jobs/{worker_job_id}`
- 여기서 `worker_job_id`는 backend `animation_jobs.external_job_id`를 그대로 사용한다
- 즉 backend dispatch contract 기준으로 `external_job_id`는 worker job UUID 자체다

reconciliation rules:

- worker status가 `completed`이면 backend row도 `completed`로 맞춘다
  - `worker.output_url`을 backend callback과 같은 정규화 규칙으로
    data-relative `output_path`로 변환한다
  - `error_message`는 비운다
- worker status가 `failed`이면 backend row도 `failed`로 맞춤
- worker status가 `cancelled`이면 backend row도 `cancelled`로 맞춤
- worker job이 `404`이거나 startup cleanup 뒤 terminal row가 없으면 backend row를
  `failed / Worker restarted`로 정리
- worker가 일시적으로 unreachable이면 row를 그대로 두고 이번 pass에서는 건너뜀

이 reconciliation pass는 두 경로에서 재사용한다.

1. backend startup
2. operator-facing bounded helper/script

즉 worker startup callback이 실패해도, backend restart 또는 manual reconcile 한 번으로
backend stale row를 terminal state에 맞출 수 있어야 한다.

## Backend Animation Terminal-State Guard

`/api/v1/animation/jobs/{job_id}/callback`는 stale restart 이후 late callback이 와도
terminal state를 덮어쓰지 못해야 한다.

required guard rules:

- current status가 `completed`이면 late `failed`, `submitted`, `processing`, `cancelled`
  를 무시
- current status가 `failed`이면 late `queued`, `submitted`, `processing`, `completed`
  를 무시
- current status가 `cancelled`이면 late `queued`, `submitted`, `processing`, `completed`
  를 무시

즉 terminal state precedence는 다음과 같다.

- `completed`, `failed`, `cancelled` are sticky

단, 동일 terminal 상태에서 metadata가 비어 있을 경우에만 제한적으로 merge하는 방향은
이번 단계에서 필요 없다. 이번 단계는 보수적으로 terminal status를 유지하는 쪽이 맞다.

## Operator Recovery Rule

operator는 stale animation job을 `resume`하지 않는다.

recovery SOP:

1. stale job이 `failed / Worker restarted` 또는 equivalent terminal state로 정리됐는지 확인
2. 동일 source panel에 대해 기존 helper를 다시 실행
3. 새 animation job id와 새 worker job id를 사용

canonical rerun command:

```bash
cd backend
./.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id 2d696b08-4899-4a3b-b499-adc37dbaa9f5 \
  --panel-index 0 \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --poll-sec 5 \
  --timeout-sec 1800
```

즉 “복구”는 stale row를 새로 살리는 것이 아니라, stale row를 실패로 닫고 새 row를
만드는 방식이다.

## Testing Strategy

필수 테스트는 다섯 묶음이다.

1. worker startup cleanup
- stale `worker_jobs`가 startup에서 `failed / Worker restarted`로 바뀜
- callback payload가 failed로 전송됨

2. backend stale reconciliation pass
- worker terminal state를 backend terminal state로 mirror함
- worker 404 또는 missing row를 `failed / Worker restarted`로 정리함
- worker unreachable은 mutation 없이 skip함

3. backend callback regression guard
- `failed` animation job이 late `processing` 또는 late `completed`로 되돌아가지 않음
- `completed` animation job이 late `failed`로 되돌아가지 않음

4. teaser helper/operator contract
- stale failure 이후 기존 teaser helper rerun path는 그대로 동작
- 새 job id를 반환

5. live bounded verification
- stale row fixture 또는 실제 restart 상황에서 `processing` row가 `failed / Worker restarted`
  로 정리됨
- 그 다음 rerun helper가 새 completed mp4를 만듦

## Success Criteria

이번 단계가 끝났다고 말하려면 아래가 모두 맞아야 한다.

- worker restart 뒤 stale `worker_jobs`가 자동으로 terminal state가 된다
- matching backend `animation_jobs`도 callback 또는 reconciliation pass를 통해 terminal
  state로 정리된다
- late callback이 terminal backend state를 되돌리지 못한다
- operator는 새 retry surface 없이 기존 teaser helper로 rerun할 수 있다
- stale failure 1건 + rerun success 1건이 실제로 검증된다

## Expected Operator Outcome

완료 후 operator가 보게 되는 상태는 단순하다.

- 죽은 animation run은 `processing`에 영원히 남지 않는다
- stale job은 `failed / Worker restarted`로 명확히 보인다
- 다시 실행하면 새 job id로 clean하게 rerun된다
- teaser derivative 운영 규칙이 `resume`이 아니라 `fail then rerun`으로 고정된다
