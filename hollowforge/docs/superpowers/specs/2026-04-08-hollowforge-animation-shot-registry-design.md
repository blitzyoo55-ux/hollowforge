# HollowForge Animation Shot Registry Design

Date: 2026-04-08

## Goal

`selected comic render asset`를 teaser animation의 단발성 launch input으로만 쓰지 않고,
재실행 가능하고 확장 가능한 `shot asset`으로 승격한다.

이번 단계의 목표는 세 가지다.

- current `/comic` teaser ops를 `job history` 중심에서 `shot + variants` 중심으로 올린다
- `selected render -> teaser rerun -> latest mp4` 흐름을 유지하면서 lineage를 더 정확하게 남긴다
- 이후 `scene-level shot packs`, `multi-variant teaser sets`, `publish/export automation`으로 확장할 수 있는 최소 registry를 만든다

핵심은 `새 animation system`을 만드는 것이 아니라,
이미 검증된 `selected render asset -> animation job -> mp4` 경로 위에
`shot registry`를 얹는 것이다.

## Current State

stable runtime 기준으로 지금 이미 닫힌 것:

- comic one-shot import / render / select / dialogue / assembly / handoff export
- remote still production lane
- teaser derivative helper
- stale teaser reconciliation
- `/comic` 안의 `Teaser Ops For Selected Render` UI

canonical operator artifacts:

- comic operator SOP:
  - `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`
- teaser helper:
  - `backend/scripts/launch_comic_teaser_animation_smoke.py`
- stale reconcile helper:
  - `backend/scripts/reconcile_stale_animation_jobs.py`

current teaser ops behavior:

- source truth는 `selected render asset`
- history view는 사실상 `animation_jobs where generation_id = selected_generation_id`
- rerun은 selected render 기준 새 animation job launch
- success/failure/stale recovery는 모두 `job` 단위

즉 teaser는 동작하지만,
현재 persistence 단위가 `creative asset`이 아니라 `execution log`에 가깝다.

## Problem Statement

현재 구조는 운영에는 충분하지만, 콘텐츠 파이프라인 자산 구조로는 약하다.

문제는 네 가지다.

1. 같은 selected render에서 여러 teaser variant를 묶는 상위 entity가 없다.
2. job history는 남지만, 어떤 teaser가 같은 source shot의 파생인지 명확하지 않다.
3. selected render가 바뀌었을 때 이전 teaser lineage와 현재 teaser lineage가 같은 row-set 안에서 섞인다.
4. 이후 `9:16`, `1:1`, `different preset`, `different pacing`, `publish candidate` 같은 확장이 오면 `animation_jobs` 조회만으로는 자산 관리가 안 된다.

즉 지금 필요한 것은 `full cinematic shot system`이 아니라,
`selected render`를 기반으로 하는 `shot registry lite`다.

## Considered Approaches

### 1. Job History Only

지금 구조를 유지하고 `/comic`에서 animation job list만 더 잘 보여준다.

장점:

- 구현 비용이 가장 작다
- 현재 ops UI와 helper를 거의 그대로 유지한다

단점:

- teaser 파생이 계속 `운영 로그`에 머문다
- 같은 source render에서 나온 variant grouping이 불가능하다
- 장기적으로 publish/export lineage가 약하다

콘텐츠 파이프라인 기준으로는 부족하다.

### 2. Shot Registry Lite

`selected render asset`를 source truth로 삼는 `animation_shot`을 만들고,
그 아래에 teaser variant와 animation job을 연결한다.

장점:

- current teaser UX를 거의 유지하면서 lineage를 크게 개선한다
- same-source rerun과 multi-variant 축적이 가능하다
- scene-level registry와 publish/export 확장의 기반이 된다
- 첫 구현 범위를 작게 유지할 수 있다

단점:

- migration, route, service, UI query가 조금 늘어난다
- 첫 단계에서는 registry browsing을 크게 열지 못한다

이번 단계에 가장 적합하다.

### 3. Full Shot Library First

scene-level packs, ranking, tags, publish mapping, reuse search까지 한 번에 설계하고 구현한다.

장점:

- 장기 구조는 가장 풍부하다
- teaser, clips, campaign assets를 한 테이블 군으로 다루기 쉽다

단점:

- 지금 단계 목적보다 범위가 명백히 크다
- `/comic` current ops를 빨리 개선하는 데 비해 비용이 과하다
- 정식 browsing / curation / publish contract가 같이 따라와야 한다

이번 단계에는 과설계다.

## Recommended Direction

권장 방향은 `2. Shot Registry Lite`다.

원칙은 아래와 같다.

- `selected render asset`가 teaser source truth
- `animation_shot`은 same-source teaser lineage의 상위 자산
- `animation_shot_variant`는 preset / pacing / rerun 등의 실행 단위
- `animation_job`은 execution layer로 유지
- `/comic`은 `selected panel context` 안에서 `current shot + recent variants`를 보여준다

즉 canonical lineage는 다음과 같다.

`episode -> scene_panel -> selected_render_asset -> animation_shot -> animation_shot_variant -> animation_job -> mp4`

이번 단계는 `full library`가 아니라
`library로 확장 가능한 최소 registry`를 고정하는 것이다.

## In Scope

- `animation_shots` persistence 추가
- `animation_shot_variants` persistence 추가
- selected render 기준 current shot resolve rule
- teaser rerun 시 shot reuse / variant append rule
- selected render 변경 시 new shot creation rule
- `/comic` teaser ops를 shot-aware query로 전환
- latest success / latest failure / variant history 표시
- stale reconcile과 callback terminal-state guard의 shot-variant integration
- minimal docs update

## Out Of Scope

- scene-level shot packs
- arbitrary historical shot browsing page
- cross-episode shot search
- ranking / tagging / curation UI
- publish candidate scoring
- automatic teaser preset comparison
- non-teaser animation families
- rough cut / timeline editor

## Design Details

## Source Truth Rule

shot registry의 source truth는 항상 current `selected render asset`이다.

필수 조건:

- `comic_panel_render_assets.is_selected = 1`
- `storage_path`가 비어 있지 않음
- placeholder asset이 아님
- `generation_id` 존재

중요한 규칙:

- `scene_panel_id`만으로 shot identity를 잡지 않는다
- `selected_render_asset_id`가 바뀌면 다른 shot이다

이유:

- 같은 panel이라도 winning render를 바꾸면 시각적 source truth가 달라진다
- 반대로 같은 selected render에서 여러 teaser variant를 만드는 것은 같은 shot의 파생이다

## Registry Model

### `animation_shots`

`selected render` 기준의 상위 creative asset.

proposed columns:

- `id`
- `source_kind`
  - initial value: `comic_selected_render`
- `episode_id`
- `scene_panel_id`
- `selected_render_asset_id`
- `generation_id`
- `is_current`
- `created_at`
- `updated_at`

uniqueness rule:

- active/current shot uniqueness는 `selected_render_asset_id` 기준
- 같은 selected render에 대해 shot는 하나만 존재

expected behavior:

- same selected render rerun: existing shot reuse
- selected render 변경: new shot create, old shot stays for lineage

### `animation_shot_variants`

shot 아래의 실행/결과 단위.

proposed columns:

- `id`
- `animation_shot_id`
- `preset_id`
- `launch_reason`
  - initial enum: `initial`, `rerun`, `manual`
- `animation_job_id`
- `status`
- `output_path`
- `error_message`
- `created_at`
- `completed_at`

variant는 execution metadata를 요약하지만,
authoritative execution state는 여전히 `animation_jobs`에 있다.

즉 variant는 registry-facing projection이고,
job는 runtime-facing truth다.

## Shot Resolution Rule

teaser launch 직전에는 아래 순서로 current shot을 resolve한다.

1. current selected render asset resolve
2. matching `animation_shot` 존재 여부 확인
3. 있으면 reuse
4. 없으면 create

matching key:

- `selected_render_asset_id`

초기 구현에서는 `source_kind = comic_selected_render`만 지원한다.

## Variant Creation Rule

새 teaser launch는 항상 새 `animation_job`를 만든다.

그리고 launch 직후 variant row를 만든다.

필수 연결:

- `animation_shot_id`
- `animation_job_id`
- `preset_id`
- `launch_reason`
- initial `status`

이후 callback이나 reconcile 시 variant status를 job status와 동기화한다.

initial operator rules:

- UI 버튼 launch는 `launch_reason = rerun`
- future automatic first-launch helper는 `launch_reason = initial`
- shell/manual recovery launch는 `launch_reason = manual`

## Callback And Reconcile Integration

current animation callback terminal-state guard는 유지한다.

추가 rule:

- job callback success -> linked variant `completed`, `output_path`, `completed_at` update
- job callback failure -> linked variant `failed`, `error_message`, `completed_at` update
- stale reconcile fail-then-rerun -> stale linked variant도 `failed / Worker restarted` 반영

shot row 자체는 terminal status를 가지지 않는다.

shot은 lineage container이고,
terminal state는 variant/job에 있다.

## UI Contract

current `/comic`의 `Teaser Ops For Selected Render` 패널은 유지한다.

하지만 query surface는 아래처럼 바뀐다.

current:

- recent `animation_jobs` filtered by `generation_id`

target:

- current shot summary
- recent variants for current shot
- latest successful variant
- latest failed variant

즉 UI는 여전히 selected panel context를 유지하지만,
내부적으로는 `current shot`을 먼저 resolve한 뒤 그 shot의 variants를 보여준다.

### Current Panel UX

selected render가 materialized되기 전까지:

- current shot summary는 비어 있음
- rerun disabled
- readiness message 유지

selected render가 준비되면:

- current shot summary 표시
- recent variants 표시
- latest success mp4 / latest failure 표시
- rerun enabled

### Copy Principle

UI copy는 `job history`보다 `selected render lineage`를 강조해야 한다.

recommended examples:

- `Current Teaser Shot`
- `Recent Variants For Selected Render`
- `Latest Successful Variant`

## API Surface

이번 단계는 brand-new standalone page를 만들지 않는다.

minimal additional surfaces:

- `GET /api/v1/animation/shots/current`
  - query:
    - `scene_panel_id`
    - `selected_render_asset_id`
  - returns:
    - current shot summary + recent variants

optional alternative:

- `GET /api/v1/animation/shots/{shot_id}/variants`

그러나 첫 단계에서는 `/comic` integration이 목적이므로
`current shot + bounded recent variants`를 한 번에 주는 surface가 더 적합하다.

launch surface는 기존 것을 유지한다.

- `POST /api/v1/animation/presets/{preset_id}/launch`

다만 service layer에서 launch 이후 variant linkage를 기록한다.

## Migration Strategy

새 registry는 additive migration으로 간다.

required work:

- `animation_shots`
- `animation_shot_variants`
- existing successful teaser jobs를 current selected render 기준으로 backfill하는 optional script

첫 단계에서는 backfill이 필수는 아니다.

추천:

- migration 추가
- new launches only registry populate
- existing historical jobs는 best-effort로만 표시

이유:

- operational value는 새 launches부터 바로 얻을 수 있다
- full historical normalization은 범위가 커진다

## Operator Flow After This Change

새 canonical operator flow:

1. operator selects winning render
2. `/comic` resolves current teaser shot for that selected render
3. operator launches teaser rerun
4. system creates animation job + shot variant
5. callback/reconcile updates variant status
6. latest successful mp4 and variant history appear under current shot

이 구조가 되면 operator는 더 이상 단순한 job log를 보는 것이 아니라,
`현재 winning render의 teaser lineage`를 보게 된다.

## Future Extension Path

이 설계는 아래 확장을 열어둔다.

### Scene-Level Shot Packs

여러 panel shot를 묶어 `scene shot pack`으로 승격.

### Multi-Variant Teaser Sets

same shot 아래:

- `1:1`
- `9:16`
- short / long
- different preset families

를 자연스럽게 그룹화.

### Publish / Export Automation

`latest successful variant`나 `best-performing variant`를 export/publish candidate로 승격.

### Shot Library UI

추후 `/comic` 밖의 registry browsing page에서
episode / panel / selected render / preset 기준 탐색 가능.

## Risks

### 1. Variant vs Job State Drift

job와 variant를 이중으로 저장하면 drift risk가 있다.

mitigation:

- job를 authoritative execution record로 유지
- variant는 callback/reconcile/service에서만 갱신
- direct variant mutation route는 두지 않는다

### 2. Selected Render Change Semantics

panel의 winning render가 바뀌면 new shot를 만들어야 한다.

mitigation:

- selected_render_asset_id를 shot identity key로 고정
- old shot는 soft historical row로 남김

### 3. Historical Backfill Complexity

기존 teaser jobs를 완벽히 registry에 옮기려 하면 범위가 커진다.

mitigation:

- first phase는 new launches only
- backfill은 optional maintenance task로 분리

## Acceptance Criteria

이 설계가 구현되면 아래가 가능해야 한다.

1. selected render를 기준으로 current shot를 resolve할 수 있다
2. same selected render rerun은 same shot 아래 새 variant를 만든다
3. selected render가 바뀌면 새 shot가 만들어진다
4. latest success / latest failure가 current shot 기준으로 `/comic`에 보인다
5. stale reconcile 이후 failed variant 상태가 current shot history에 반영된다
6. current teaser ops UX는 유지되되, 내부 persistence는 library-friendly registry로 승격된다

## Recommendation

다음 단계 구현은 `shot registry lite`까지만 간다.

즉:

- current `/comic` teaser ops 유지
- selected render 기준 `animation_shots` 추가
- shot 아래 `variants` 추가
- launch/callback/reconcile 연동

그리고 `scene-level shot packs`, `publish linkage`, `library browsing`은 그다음 단계로 미룬다.
