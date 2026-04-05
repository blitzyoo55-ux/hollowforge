# HollowForge Comic Teaser Derivative Design

Date: 2026-04-05

## Goal

stable one-shot comic 결과에서 `selected panel asset 1개`를 골라
`teaser animation job 1건`으로 승격하고, 기존 animation worker callback
계약을 통해 `mp4 output 1개`를 확보한다.

이번 단계의 목적은 세 가지다.

- comic one-shot 결과를 animation preview/production 파이프라인으로 실제 연결
- 기존 `/api/v1/animation` surface와 remote worker contract를 최대한 재사용
- comic-side lineage를 잃지 않고 `teaser derivative 1건`을 재현 가능한 helper로 고정

핵심은 `새 애니메이션 시스템`을 만드는 것이 아니라,
이미 검증된 `selected panel asset -> worker callback` 경로를
`animation job`으로 한 단계 더 이어주는 것이다.

## Current State

지금까지 stable runtime에서 이미 닫힌 것:

- `comic remote still render`는 stable backend + stable launchd worker에서 동작
- `one-shot production dry run` 1건이 성공
- canonical helper:
  - `backend/scripts/launch_comic_remote_one_shot_dry_run.py`
- latest validated episode:
  - `episode_id = 2d696b08-4899-4a3b-b499-adc37dbaa9f5`
- latest handoff artifacts:
  - `data/comics/exports/2d696b08-4899-4a3b-b499-adc37dbaa9f5_jp_2x2_v1_handoff.zip`
  - `data/comics/reports/2d696b08-4899-4a3b-b499-adc37dbaa9f5_jp_2x2_v1_jp_manga_rightbound_v1_dry_run.json`

현재 animation 쪽 reusable surface도 이미 있다.

- animation route:
  - `POST /api/v1/animation/jobs`
  - `POST /api/v1/animation/presets/{preset_id}/launch`
  - `POST /api/v1/animation/jobs/{job_id}/callback`
- remote dispatch:
  - `backend/app/services/animation_dispatch_service.py`
- worker contract:
  - `lab451-animation-worker/app/models.py`
  - `source_image_url`, `request_json`, `callback_url`, `callback_token`

즉 comic still 쪽 `selected asset truth`와 animation 쪽 `image-to-video job`
사이에 얇은 bridge만 추가하면 이번 목표를 달성할 수 있다.

## Problem Statement

현재 comic export는 `teaser_handoff_manifest`를 남기지만,
그 manifest를 실제 animation job으로 승격하는 canonical path가 없다.

문제는 세 가지다.

1. 어떤 panel을 teaser source로 쓸지 operator 기준이 고정돼 있지 않다.
2. selected comic asset을 animation preset launch input으로 바꾸는 bridge가 없다.
3. successful animation mp4 1건을 comic lineage에 연결해서 재확인하는 helper가 없다.

따라서 지금 필요한 것은 `full animation registry`가 아니라
`operator-facing derivative bridge`다.

## Considered Approaches

### 1. Manifest-Only Bridge

`teaser_handoff_manifest`만 만들고 animation launch는 사람이 수동으로 한다.

장점:

- 구현 비용이 가장 작다
- 현재 export contract를 거의 안 건드린다

단점:

- 이번 목표인 `mp4 1건 확보`를 닫지 못한다
- operator가 매번 수동 매핑을 다시 해야 한다
- regression helper가 생기지 않는다

이 방향은 이번 단계 목적에 부족하다.

### 2. Selected Panel -> Existing Animation Job Bridge

selected comic panel asset을 source image로 삼아 기존 animation preset launch
surface를 그대로 재사용한다.

장점:

- `/api/v1/animation` route와 worker contract를 그대로 활용 가능
- `sdxl_ipadapter_microanim_v2` 같은 기존 identity-first preset을 재사용 가능
- comic-side 변경을 최소화하면서 실제 mp4 1건을 확보할 수 있다
- helper 하나로 다시 재현 가능하다

단점:

- comic lineage는 아직 얇은 bridge 수준이다
- `animation_shots` 같은 정식 derivative entity는 이번 단계에 없다

이번 단계에 가장 적합하다.

### 3. Full `animation_shots` Registry First

comic 전용 `animation_shots` persistence와 route를 먼저 만들고 그 위에서
animation job launch를 감싼다.

장점:

- 장기 구조는 가장 깔끔하다
- 향후 teaser batch/serial 확장에 직접 연결된다

단점:

- migration, route, repo, UI, helper가 한 번에 커진다
- 이번 목표치보다 범위가 명백히 크다
- 이미 있는 animation route 재사용 장점을 희석한다

이 방향은 다음 단계로 미루는 게 맞다.

## Recommended Direction

권장 방향은 `2. Selected Panel -> Existing Animation Job Bridge`다.

원칙은 아래와 같다.

- comic selected asset가 source truth
- animation job는 기존 route/worker contract 재사용
- preset launch는 기존 identity-first lane 우선
- 이번 단계는 `job 1건 + mp4 1개`까지
- `animation_shots` 정식 registry는 명시적으로 다음 단계

즉 canonical flow는 다음과 같다.

`episode -> selected panel asset -> source_image_url -> animation preset launch -> animation job callback -> mp4 output`

## In Scope

- selected comic panel asset 1개를 teaser source로 선택하는 canonical helper
- selected asset의 `storage_path`를 animation launch input으로 연결
- existing animation preset reuse
- animation job 1건 생성
- worker callback 완료
- `output_path(mp4)` 1개 확보
- helper output에 comic lineage와 animation job id를 같이 남김
- minimal docs update

## Out Of Scope

- `animation_shots` table / migration / registry
- teaser batch generation
- rough cut orchestration
- timeline editor
- full comic UI integration
- multiple preset comparison UX
- publish/storefront automation

## Design Details

## Canonical Source Rule

이번 단계의 teaser source는 아래 조건을 만족하는 `selected comic panel asset`이다.

- `comic_panel_render_assets.is_selected = 1`
- `asset_role = selected`
- `storage_path`가 비어 있지 않음
- `comics/previews/smoke_assets/...` placeholder가 아님

즉 animation source는 page preview가 아니라 `selected panel asset`이다.

## Launch Surface

새 comic 전용 animation route를 만들지 않는다.

기존 animation launch surface를 재사용한다.

preferred option:

- `POST /api/v1/animation/presets/{preset_id}/launch`

이유:

- preset id를 통해 identity-first 운영 규칙을 강제하기 쉽다
- local/remote worker backend 전환이 preset/request_json 레벨에서 유지된다
- helper가 짧고 재현 가능하다

이번 단계의 default preset:

- `sdxl_ipadapter_microanim_v2`

이유:

- 현재 playbook의 canonical identity-first lane
- source image 보존 성향이 가장 안정적
- teaser preview/production bridge의 baseline으로 맞다

## Bridge Payload Rule

comic helper는 selected panel asset를 animation launch payload로 바꾼다.

필수 연결 정보:

- `episode_id`
- `scene_panel_id`
- `selected_render_asset_id`
- `selected_render_asset_storage_path`
- `generation_id` of selected asset
- chosen `preset_id`

animation launch 자체는 기존 payload를 재사용한다.

helper가 할 일:

1. episode detail 조회
2. selected panel asset 1개 찾기
3. 그 asset의 generation id 확보
4. preset launch 호출
5. resulting animation job polling
6. completed `output_path` 검증

## Minimal Metadata Strategy

이번 단계에서는 comic-side 영구 registry를 추가하지 않는다.

대신 helper/report 수준에서 아래 메타데이터를 남긴다.

- source `episode_id`
- source `scene_panel_id`
- source `selected_render_asset_id`
- source `generation_id`
- created `animation_job_id`
- chosen `preset_id`
- final `output_path`

이 metadata는 다음 `animation_shots` 단계의 입력 근거가 된다.

## Helper Design

새 canonical helper를 추가한다.

proposed file:

- `backend/scripts/launch_comic_teaser_animation_smoke.py`

helper 역할:

1. local backend URL 검증
2. episode id 또는 latest one-shot result를 source로 선택
3. selected panel asset 1개 resolve
4. preset launch
5. animation job status poll
6. completed mp4 output 검증
7. summary markers 출력

expected summary markers:

- `episode_id`
- `scene_panel_id`
- `selected_render_asset_id`
- `generation_id`
- `preset_id`
- `animation_job_id`
- `output_path`
- `teaser_success`
- `overall_success`

## Preset Rule

default:

- `sdxl_ipadapter_microanim_v2`

optional later:

- `ltxv_portrait_locked`
- `ltxv_character_lock_v2`

하지만 이번 단계의 성공 기준은 preset 다양화가 아니라
`canonical preset 1개로 mp4 1건`이다.

## Validation Strategy

### Functional Validation

- one selected comic panel asset is resolved from a real episode
- one animation job is launched from that asset
- worker callback completes
- one mp4 output exists

### Operational Validation

- helper can be rerun on stable backend + stable launchd worker
- output preserves the link back to comic source ids
- failure surface is explicit:
  - no selected asset
  - placeholder asset
  - preset launch failure
  - callback timeout
  - missing mp4 output

## Success Criteria

이번 단계의 성공 상태는 다음이다.

- stable comic one-shot result 1건이 teaser source로 재사용된다
- selected panel asset 1개가 animation preset launch input으로 연결된다
- animation job 1건이 callback까지 완료된다
- mp4 output 1개가 확보된다
- operator가 같은 helper를 다시 실행해서 재현할 수 있다

이번 단계의 성공 상태는 아직 아니다.

- teaser batch system
- animation_shots registry
- editorial rough cut assembly

## Recommended Next Step

After this design is accepted:

1. write a focused implementation plan for the teaser derivative bridge
2. keep scope to `selected panel 1개 -> animation job 1건 -> mp4 1개`
3. delay `animation_shots` persistence until the bridge helper is validated

## References

- `STATE.md`
- `docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`
- `docs/HOLLOWFORGE_COMIC_PRODUCTION_DRY_RUN_20260404.md`
- `docs/superpowers/specs/2026-04-03-hollowforge-character-os-comic-animation-design.md`
- `docs/superpowers/specs/2026-04-04-hollowforge-comic-production-handoff-design.md`
- `docs/superpowers/specs/2026-04-04-hollowforge-comic-still-remote-dispatch-design.md`
