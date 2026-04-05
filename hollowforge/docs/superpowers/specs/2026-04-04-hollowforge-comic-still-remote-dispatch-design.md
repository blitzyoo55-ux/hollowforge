# HollowForge Comic Still Remote Dispatch Design

Date: 2026-04-04

## Goal

`adult_nsfw one-shot manga`의 `panel still render`를 로컬 검증 lane과 원격 생산 lane으로 분리한다.

이번 단계의 목적은 세 가지다.

- `one-panel verification`과 `selection`은 계속 로컬에서 빠르게 유지
- `full 4-panel+ production still render`는 원격 worker로 넘길 수 있는 계약 고정
- 기존 `character -> episode -> scene -> panel -> render asset -> page export` lineage를 깨지 않고 유지

핵심은 `애니 worker를 또 하나 만드는 것`이 아니라, 이미 존재하는 HollowForge `remote worker envelope`를 comic still render까지 확장하는 것이다.

## Measured Trigger

이번 설계는 추상이 아니라 실측값 위에 올라간다.

수정된 local benchmark helper:

- `backend/scripts/launch_comic_four_panel_benchmark.py`

실제 live run 결과:

- backend: `http://127.0.0.1:8010`
- episode id: `c0b65996-0246-4470-98b9-b2bf6bfe0555`
- first panel id: `e7239af2-01d5-4e3b-979d-99dfbeb2c5cf`
- first panel render duration: `239.352s`
- fail-fast threshold: `180.0s`
- result: `remote_worker_recommended`

report artifact:

- `data/comics/reports/c0b65996-0246-4470-98b9-b2bf6bfe0555_jp_2x2_v1_jp_manga_rightbound_v1_local_benchmark.json`

이 값은 `4-panel repeated local production`이 운영 기준에서 이미 약하다는 뜻이다.

## Current State

현재 comic render path는 전부 local generation worker 전제다. `execution_mode=remote_worker`는 계약상 노출되지만, Task 1 시점에는 아직 명시적으로 `501 Not Implemented`로 거절한다.

- route:
  - `POST /api/v1/comic/panels/{panel_id}/queue-renders`
- service:
  - `backend/app/services/comic_render_service.py`
- runtime:
  - `GenerationService.queue_generation_batch()`
  - local ComfyUI polling

현재 장점:

- `character_version` 기준 prompt build가 이미 정리되어 있다
- `comic_panel_render_assets`와 selected asset 흐름이 page assembly/export와 연결되어 있다
- smoke, one-panel verification, production dry-run 경로가 이미 존재한다

현재 한계:

- repeated still render heavy path가 local generation worker와 완전히 결합돼 있다
- benchmark는 remote 전환이 필요함을 보여주지만, comic still render용 remote dispatch/callback contract는 아직 없다
- animation remote worker는 존재하지만 `source_image_url` 중심 `image-to-video` payload를 전제로 한다

## Problem Statement

지금 필요한 것은 `generation quality tweak`가 아니라 `execution boundary`다.

로컬에서 계속 할 일:

- panel prompt packet 생성
- one-panel 실자산 검증
- selected asset human review
- dialogue drafting
- page assembly/export

원격으로 옮겨야 할 일:

- repeated full panel still generation
- candidate fan-out
- 장시간 ComfyUI polling
- production-grade throughput

문제는 이 경계를 어디에 두느냐다.

잘못된 경계:

- `GenerationService`에 remote still logic를 직접 섞기
- `animation_jobs`를 그대로 재사용해 comic still을 우겨 넣기
- comic asset lineage를 worker 내부 상태에 넘겨버리기

올바른 경계:

- HollowForge는 계속 `creative source of truth`
- remote worker는 `heavy execution adapter`
- comic still remote path도 panel/render asset lineage 위에 매달려야 한다

## Considered Approaches

### 1. Keep Local And Just Raise Budgets

benchmark threshold만 올리고 local Mac mini를 계속 production path로 쓴다.

장점:

- 구현 비용이 가장 낮다
- 기존 queue path를 그대로 유지한다

단점:

- 실측상 첫 패널 하나가 이미 `239.352s`
- 4패널 이상 반복 생산은 계속 operator waiting bottleneck이 된다
- benchmark가 주는 의미가 사라진다

이 방향은 맞지 않다.

### 2. Put Remote Still Logic Directly Inside GenerationService

`GenerationService`가 local ComfyUI와 remote worker를 모두 고르게 한다.

장점:

- generation lineage를 강하게 유지하기 쉽다
- route surface 변경이 작아 보인다

단점:

- local background worker와 remote orchestration이 한 서비스에 섞인다
- cancel/poll/status semantics가 더 복잡해진다
- `still preview lane`과 `remote production lane`의 경계가 흐려진다

이 방향은 장기적으로 불리하다.

### 3. Add A Comic Remote Render Job Layer While Reusing Generation Rows

comic still 전용 `job layer`를 추가하되, `generations` 행은 lineage shell로 계속 유지한다.

장점:

- `comic_panel_render_assets -> generations` join을 유지할 수 있다
- local generation worker loop는 그대로 둔다
- animation worker의 envelope를 재사용하면서 comic 전용 callback/job lifecycle을 분리할 수 있다
- `/comic`에서 local verification과 remote production을 의도적으로 나눌 수 있다

단점:

- migration, dispatch service, callback route, worker 확장이 함께 필요하다

이 방향이 가장 맞다.

## Recommended Direction

권장 방향은 `3. Comic Remote Render Job Layer + Generation Shell Reuse`다.

원칙은 아래와 같다.

- local preview lane은 유지
- remote production lane은 별도 job layer로 추가
- `comic_panel_render_assets`는 계속 comic truth
- `generations`는 render lineage shell로 계속 유지
- worker contract는 `animation-only`에서 `generic heavy execution`으로 조금 넓힌다

즉:

`panel -> generation shell -> comic_panel_render_asset -> comic_render_job -> remote worker -> callback -> generation/image_path materialized`

이 구조가 현재 코드와 가장 잘 맞는다.

## In Scope

- comic still remote dispatch contract
- comic remote render job persistence
- generation shell creation for remote still jobs
- worker payload extension for `comic_panel_still`
- callback path that materializes generation/image paths and render asset storage
- `/comic` operator surface for `local verification` vs `remote production`
- remote preflight/smoke path for comic still render

## Out Of Scope

- automatic benchmark-driven lane switching
- replacing the current local one-panel verification helper
- native `.clip` generation
- teaser animation implementation
- fully generic job platform for every future execution type
- storefront/publisher automation

## Design Details

## Source Of Truth

truth는 계속 HollowForge 쪽이다.

- `comic_scene_panels`
- `comic_panel_render_assets`
- `generations`
- new `comic_render_jobs`

worker는 truth를 갖지 않는다. worker는 `job executor`일 뿐이다.

## Execution Split

### Local verification lane

목적:

- 1패널 실자산 확인
- prompt/context sanity check
- selected asset human approval

canonical tools:

- `launch_comic_one_panel_verification.py`
- existing `POST /api/v1/comic/panels/{panel_id}/queue-renders`
- `execution_mode=remote_worker`는 아직 여기서 실행되지 않으며, Task 2에서 remote dispatch/callback가 붙을 때 활성화된다.

### Remote production lane

목적:

- 4패널 이상 repeated still production
- candidate fan-out
- production throughput

canonical surface:

- same panel lineage
- new remote dispatch-backed render job path

## Persistence Model

새 테이블을 추가한다.

### `comic_render_jobs`

필드 예시:

- `id`
- `scene_panel_id`
- `render_asset_id`
- `generation_id`
- `request_index`
- `source_id`
- `target_tool`
- `executor_mode`
- `executor_key`
- `status` (`queued`, `submitted`, `processing`, `completed`, `failed`, `cancelled`)
- `request_json`
- `external_job_id`
- `external_job_url`
- `output_path`
- `error_message`
- `submitted_at`
- `completed_at`
- `created_at`
- `updated_at`

핵심은 `job = one candidate asset`라는 점이다.

`comic_panel_render_assets`는 여전히 operator-facing asset truth이고,
`comic_render_jobs`는 execution truth다.

## Generation Lineage Rule

remote still render도 `generations` 행을 가진다.

이 규칙을 두는 이유:

- 현재 `comic_panel_render_assets` 로딩이 generation join을 전제로 한다
- `source_id` 기준 batch identity를 계속 재사용할 수 있다
- selected asset 이후 quality/export logic를 덜 건드리고 유지할 수 있다

즉 remote still path는 `generation worker queue`를 재사용하지 않더라도, `generation row`는 재사용한다.

recommended rule:

- queue 시점에 `generations` placeholder row 생성
- status는 `queued`
- `source_id`는 Task 1에서 확정된 `_render_request_source_id(panel_id, candidate_count, execution_mode)` 규칙을 그대로 유지
- 즉 `comic-panel-render:{panel_id}:{candidate_count}:{execution_mode}` 형태로 local/remote batch identity collision을 막는다
- remote callback에서 generation row를 `submitted/processing/completed/failed/cancelled`로 업데이트
- completed 시 `image_path`를 반드시 materialize

## Route Surface

기존 route는 유지하되 remote 분기를 추가한다.

### Canonical queue route

`POST /api/v1/comic/panels/{panel_id}/queue-renders`

new query param:

- `execution_mode`
  - `local_preview` default
  - `remote_worker`

local path:

- 현재 동작 그대로 유지

remote path:

- generation shell rows 생성
- render asset rows 생성
- comic render jobs 생성
- remote worker dispatch
- placeholder asset list 반환

### Supporting route

`GET /api/v1/comic/panels/{panel_id}/render-jobs`

목적:

- `/comic`에서 selected panel의 remote job progress 확인
- asset materialization 전에도 pending/completed/failed 상태를 보여주기

### Callback route

`POST /api/v1/comic/render-jobs/{job_id}/callback`

목적:

- remote worker 상태 업데이트 수용
- generation row update
- render asset materialization

## Response Surface

기존 `ComicPanelRenderQueueResponse`는 유지하되 아래를 확장한다.

- `execution_mode`
- `materialized_asset_count`
- `pending_render_job_count`
  - `queued/submitted/processing` remote jobs만 센다
- `remote_job_count`

new response:

- `ComicRenderJobResponse`

최소 필드:

- `id`
- `scene_panel_id`
- `render_asset_id`
- `generation_id`
- `status`
- `external_job_id`
- `external_job_url`
- `output_path`
- `error_message`
- `created_at`
- `updated_at`

## Dispatch Service Boundary

새 backend service를 추가한다.

- `backend/app/services/comic_render_dispatch_service.py`

책임:

- `comic_render_jobs` row -> worker payload build
- auth header attach
- worker submit
- remote response normalize

이 서비스는 animation dispatch와 유사하지만 comic still payload를 안다.

## Worker Contract

기존 worker endpoint는 유지한다.

- `POST /api/v1/jobs`

하지만 payload envelope를 조금 넓힌다.

### Worker create payload

- `target_tool="comic_panel_still"`
- `generation_id` required
- `source_image_url` optional for still jobs
- `request_json` required for still jobs

recommended `request_json` shape:

```json
{
  "backend_family": "sdxl_still",
  "model_profile": "comic_panel_sdxl_v1",
  "still_generation": {
    "prompt": "...",
    "negative_prompt": "...",
    "checkpoint": "...",
    "loras": [],
    "steps": 28,
    "cfg": 7.0,
    "width": 832,
    "height": 1216,
    "sampler": "euler",
    "scheduler": "normal",
    "clip_skip": 1,
    "source_id": "comic-panel-render:..."
  },
  "comic": {
    "scene_panel_id": "...",
    "render_asset_id": "...",
    "character_version_id": "..."
  }
}
```

### Worker backend behavior

`lab451-animation-worker`는 이름은 유지하지만 실행 역할을 확장한다.

- `target_tool="comic_panel_still"`이면 text-to-image workflow 실행
- `target_tool`이 기존 animation 계열이면 현재 동작 유지

즉 repo 이름은 animation worker지만, 실질적으로는 `heavy execution worker`가 된다.

## Callback Update Rules

callback payload를 받으면 HollowForge는 아래를 수행한다.

### `submitted` / `processing`

- `comic_render_jobs.status` update
- `external_job_id/url` update
- `generations.status` update

### `completed`

- `comic_render_jobs.status=completed`
- `comic_render_jobs.output_path` set
- `generations.status=completed`
- `generations.image_path` set
- `comic_panel_render_assets.storage_path` set

### `failed` / `cancelled`

- `comic_render_jobs.status` update
- `comic_render_jobs.error_message` set
- `generations.status` update
- asset는 placeholder로 남지만 `storage_path`는 비어 있음

## Operator UX

`/comic`에서는 의도적으로 두 버튼 또는 두 mode를 보여준다.

- `Queue Local Verification Render`
- `Queue Remote Production Renders`

selected panel 기준으로 보여줄 정보:

- current execution mode
- materialized asset count
- pending remote job count
- first failed job message
- external job link when available

핵심은 operator가 `지금 이 panel이 local preview인지 remote production인지`를 명확히 아는 것이다.

## Rollout Strategy

### Phase A

- benchmark result documented
- spec/plan fixed

### Phase B

- backend persistence + callback contract
- no frontend mode switch yet
- remote smoke via script

### Phase C

- `/comic` production lane UI
- operator-visible remote status

### Phase D

- handoff workflow와 teaser derivative가 remote still-selected assets를 그대로 소비

## Risks And Mitigations

### Risk: generation and render job state drift

mitigation:

- callback handler updates both in one transaction

### Risk: worker contract breaks existing animation flow

mitigation:

- keep `target_tool`-based branching
- do not rename existing animation endpoints

### Risk: remote job creates assets without generation lineage

mitigation:

- require generation shell creation before dispatch

### Risk: operator confusion between local and remote lanes

mitigation:

- explicit execution-mode UI labels
- remote job status surface in panel board

## Success Criteria

- a panel can queue remote still candidates without using the local generation worker loop
- completed remote stills materialize as normal `comic_panel_render_assets`
- selected remote assets can pass the existing dialogue, assembly, export, and dry-run flow
- `/comic` clearly separates local verification from remote production
- existing local one-panel verification path remains intact
