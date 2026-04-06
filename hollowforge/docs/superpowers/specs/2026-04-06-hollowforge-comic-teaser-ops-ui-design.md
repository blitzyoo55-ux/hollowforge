# HollowForge Comic Teaser Ops UI Design

Date: 2026-04-06

## Goal

`/comic` 안에서 teaser animation 운영 상태를 같이 보고,
stale recovery와 rerun을 스크립트 없이 UI로 수행할 수 있게 만든다.

이번 단계의 목적은 네 가지다.

- operator가 `/comic`에서 최근 teaser animation jobs를 바로 확인
- stale animation recovery를 UI 버튼으로 실행
- current selected panel asset 기준으로 teaser rerun을 한 번에 실행
- 마지막 successful mp4를 `/comic` 안에서 바로 열 수 있게 고정

핵심은 `새 teaser 화면`을 만드는 것이 아니라,
이미 검증된 `/comic` workspace 안에 `teaser 운영 패널`을 추가하는 것이다.

## Current State

지금 runtime/ops 기준으로 이미 닫힌 것:

- comic one-shot remote dry run 성공
- teaser derivative helper 성공
- stale animation recovery helper 성공
- canonical helper:
  - `backend/scripts/launch_comic_teaser_animation_smoke.py`
  - `backend/scripts/reconcile_stale_animation_jobs.py`

지금 UI 측 current state:

- `/comic`는 story import, panel render, selected asset, dialogue, page assembly, export까지 담당
- selected panel의 remote still render jobs는 이미 `/comic`에서 polling/표시됨
- animation API client surface는 이미 존재
  - `getAnimationPresets()`
  - `listAnimationJobs()`
  - `launchAnimationPreset()`

즉 teaser ops UI는 완전히 새 시스템이 아니라,
existing `/comic` state + existing `/api/v1/animation` surface 위에 얹는 것이 맞다.

## Problem Statement

현재 teaser 운영 흐름은 실제로 동작하지만 operator surface가 없다.

문제는 네 가지다.

1. `/comic` 안에서 selected panel 기준 teaser job history를 볼 수 없다.
2. stale job recovery는 shell script를 직접 실행해야 한다.
3. rerun도 helper/script 기반이라 UI operator flow가 끊긴다.
4. 마지막 successful mp4를 `/comic` 맥락에서 바로 확인할 수 없다.

즉 기능은 이미 있지만,
현재는 `운영 절차가 코드 바깥`에 있다.

## Considered Approaches

### 1. `/comic` Inline Teaser Ops Panel

`ComicStudio` 안에 selected panel 기준의 `Teaser Ops` 패널을 추가한다.

표시:

- selected panel teaser jobs
- latest failure reason
- latest success mp4
- `Reconcile stale animation jobs`
- `Rerun teaser from selected panel`

장점:

- current workflow를 안 끊는다
- selected panel truth와 가장 잘 맞는다
- existing `/comic` query/mutation 구조를 그대로 재사용 가능
- operator가 render/select 이후 바로 teaser까지 이어서 본다

단점:

- `ComicStudio`가 조금 더 길어진다

이번 단계에 가장 적합하다.

### 2. `ComicPanelBoard` 내부에 Panel-Scoped Teaser Controls 삽입

panel board 각 panel 또는 selected panel card 안에 teaser actions를 넣는다.

장점:

- selected panel과 action 거리가 가장 가깝다

단점:

- panel render UI와 animation ops UI가 섞인다
- board가 render/status 중심에서 운영 패널로 비대해진다
- last success mp4 / recovery summary 같은 정보가 어색해진다

이번 단계에는 과밀하다.

### 3. Separate `/comic/teaser` Route

teaser ops를 별도 route/page로 분리한다.

장점:

- 기능 경계는 가장 선명하다

단점:

- route, navigation, shared state, re-entry가 늘어난다
- 지금 단계 목표보다 범위가 크다
- `/comic`가 already operator hub인 구조와 어긋난다

지금은 과설계다.

## Recommended Direction

권장 방향은 `1. /comic Inline Teaser Ops Panel`이다.

원칙은 아래와 같다.

- `selected panel asset`가 teaser source truth
- teaser job list는 selected panel context 안에서 `current selected asset`의
  `generation_id` 기준으로 조회
- stale reconcile은 global animation lane action으로 노출
- rerun은 selected panel 기준 새 animation job 생성으로 고정
- 과거 job은 우선 `조회 전용`, `run again from this job`는 미룬다

즉 canonical operator flow는 다음과 같다.

`selected panel asset -> teaser jobs inspect -> stale reconcile(optional) -> rerun teaser -> latest mp4 verify`

## In Scope

- `/comic`에 `Teaser Ops` 패널 추가
- selected panel materialized asset 기준 teaser job list 조회
- latest failure reason 표시
- latest success mp4 링크 표시
- global stale reconcile button
- selected panel rerun button
- minimal backend route for stale reconcile trigger
- frontend/backend test coverage

## Out Of Scope

- job-level rerun from arbitrary historical row
- preset comparison UX
- timeline/shot registry
- new teaser route/page
- publish automation
- broad ComicStudio redesign
- animation quality tuning

## Design Details

## UI Placement

`ComicStudio`의 하단 2-column area를 유지하고,
`ComicPageAssemblyPanel` 아래 또는 같은 오른쪽 column에 `Teaser Ops` 패널을 추가한다.

이유:

- dialogue/page/export와 teaser ops는 모두 selected panel/episode 이후 단계다
- left side는 draft/render 선택에 집중시키고,
  right side는 downstream operations를 모으는 편이 읽기 쉽다

즉 layout principle은:

- left: story + render selection
- right: dialogue + page handoff + teaser ops

## Source Truth Rule

teaser rerun source는 항상 current selected panel의 `selected + materialized asset`이다.

필수 조건:

- selected panel 존재
- selected asset 존재
- selected asset `storage_path` 존재
- `generation_id` 존재

generic animation preset launch surface 자체는 `generation_id`만으로도 호출 가능하지만,
이번 UI action은 `teaser from selected panel` operator flow다. 따라서 readiness는
generic launch보다 보수적으로 잡는다.

즉 UI rerun은 아래를 전제로 한다.

- operator가 현재 보고 있는 selected asset이 실제 materialized file이어야 함
- helper/script와 같은 visible truth를 따라야 함
- 아직 materialize되지 않은 remote placeholder generation으로 teaser를 쏘지 않음

이 조건이 안 되면 rerun 버튼은 disabled 상태여야 한다.

readiness message는 기존 dialogue/page gating과 같은 톤으로 노출한다.

예:

- `Select a winning render for this panel before launching teaser animation.`
- `Wait for the selected render file to finish materializing before launching teaser animation.`

## Job List Query Rule

job list는 selected asset의 `generation_id` 기준으로 조회한다.

사용 surface:

- `GET /api/v1/animation/jobs?generation_id=<selected_generation_id>&limit=<n>`

표시 범위:

- newest first, bounded recent list
- recommended default limit: `8`

각 row 표시:

- status
- created/submitted/completed recency
- executor mode
- external job id or URL if present
- failure message if present
- output mp4 link if present

이 panel은 `selected panel context 안의 selected-asset-scoped view`다.
즉 episode 전체 animation registry를 보여주지 않고,
같은 panel이라도 operator가 다른 selected asset로 바꾸면 visible history도 바뀐다.

이 behavior는 의도된 것이다.

- teaser rerun source truth가 `current selected asset`이기 때문
- operator가 지금 보고 있는 winning render와 연결된 animation history만 보는 것이
  1차 ops surface에 더 적합하기 때문

UI copy도 panel-wide history로 오해되지 않게 맞춘다.

recommended title:

- `Teaser Ops For Selected Render`

## Latest Success Rule

latest success card는 selected panel job list에서 파생한다.

선정 기준:

- `status == completed`
- `output_path` non-empty
- 가장 최근 `completed_at`, fallback `updated_at`

링크 rule:

- `output_path`가 absolute `http(s)`면 그대로 사용
- relative path면 `/data/<output_path>`로 변환

card 내용:

- latest successful `animation_job_id`
- preset/model profile summary if derivable
- mp4 open link

## Failure Display Rule

selected panel job list에서 가장 최근 terminal failure를 요약한다.

선정 기준:

- `status == failed`
- `error_message` non-empty
- 가장 최근 `updated_at`

표시:

- short failure badge
- first-line failure message
- optional expandable raw error text는 이번 단계에서 생략 가능

## Reconcile Action

UI에서 script를 직접 실행하지 않는다.
backend가 existing reconciliation service를 감싼 bounded route를 제공한다.

proposed route:

- `POST /api/v1/animation/reconcile-stale`

response shape:

```json
{
  "checked": 1,
  "updated": 1,
  "failed_restart": 1,
  "completed": 0,
  "cancelled": 0,
  "skipped_unreachable": 0
}
```

semantic:

- route는 existing `animation_reconciliation_service`를 호출
- global remote-worker animation stale rows를 reconciliation
- UI는 response summary를 toast + inline status로 보여줌

button label:

- `Reconcile Stale Animation Jobs`

note:

- 이 액션은 selected panel-scoped가 아니라 global ops action이다
- 하지만 `/comic` operator flow 안에서 가장 자주 필요한 recovery이므로
  같은 패널 안에 두는 것이 맞다

## Rerun Action

rerun은 selected panel 기준 새 animation job launch다.

사용 surface:

- `POST /api/v1/animation/presets/{preset_id}/launch`

launch request:

```json
{
  "generation_id": "<selected asset generation_id>",
  "dispatch_immediately": true,
  "request_overrides": {}
}
```

default preset:

- `sdxl_ipadapter_microanim_v2`

이번 단계에서는 preset selector를 노출하지 않는다.
UI는 current default preset label만 보여주고 one-click rerun으로 고정한다.

button label:

- `Rerun Teaser From Selected Panel`

success behavior:

- returned `animation_job_id`를 toast/inline summary로 표시
- animation jobs query invalidate
- latest success/failure cards refetch

## State Management

`ComicStudio.tsx` 안에서 아래 query/mutation을 추가한다.

- `selectedPanelTeaserJobsQuery`
  - enabled when selected panel has materialized selected asset
- `reconcileAnimationMutation`
- `rerunTeaserMutation`

state additions:

- latest reconcile summary
- latest launched teaser job id

derived selectors:

- `selectedPanelTeaserJobs`
- `latestSuccessfulTeaserJob`
- `latestFailedTeaserJob`
- `teaserReadinessMessage`

UI component split:

- new component:
  - `frontend/src/components/comic/ComicTeaserOpsPanel.tsx`

responsibility:

- purely presentational operator panel
- receives selected panel context, jobs, derived latest cards, actions, busy flags

이렇게 하면 `ComicStudio`는 state orchestration,
`ComicTeaserOpsPanel`은 rendering 역할로 나뉜다.

## Backend Surface

backend changes는 작게 유지한다.

required:

- new route in `backend/app/routes/animation.py` or same router module:
  - `POST /api/v1/animation/reconcile-stale`
- response model:
  - small typed summary model, e.g. `AnimationReconciliationResponse`

service reuse:

- existing `reconcile_stale_animation_jobs()` from
  `backend/app/services/animation_reconciliation_service.py`

non-goals:

- no new persistence
- no filtering/mutation by specific stale job id
- no resume semantics

## Error Handling

UI rules:

- reconcile failure -> toast error + keep current jobs list
- rerun failure -> toast error + do not mutate local latest-success card optimistically
- list query failure -> panel shows bounded inline error state, not full-page failure

backend rules:

- reconcile route bubbles service fatal errors as `500`
- worker unreachable remains reflected in summary via `skipped_unreachable`
- rerun keeps existing animation launch error surface unchanged

## Testing

### Backend

- route test for `POST /api/v1/animation/reconcile-stale`
  - success summary returned
  - service failure maps to error response

### Frontend

- `ComicStudio.test.tsx`
  - teaser ops panel appears when episode/panel context exists
  - rerun button disabled without materialized selected asset
  - reconcile button triggers mutation and renders summary
  - teaser jobs list renders latest failed reason
  - latest successful mp4 link renders from relative output_path
  - rerun invalidates/refetches jobs and shows new job state

## Acceptance Criteria

- `/comic`에서 selected panel 기준 recent teaser animation jobs를 볼 수 있다
- latest failure reason을 UI에서 볼 수 있다
- latest success mp4를 UI에서 열 수 있다
- operator가 shell 없이 stale reconcile을 실행할 수 있다
- operator가 selected panel 기준 teaser rerun을 UI에서 실행할 수 있다
- rerun은 새 animation job id를 만든다
- 기존 stale recovery contract `fail then rerun`은 유지된다

## Implementation Notes

- first release는 selected panel-scoped teaser ops only
- global animation dashboard로 확장하지 않는다
- preset choice는 잠근다
- stale reconcile은 global action이라는 점을 UI copy에 명시한다
- job-level rerun은 후속 단계로 미룬다
