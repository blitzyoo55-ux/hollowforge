# HollowForge Reference-Guided Comic Still Design

기준일: 2026-04-10

## Goal

`Camila V2`의 comic still lane, 그중에서도 `establish` 패널을 `reference-guided still workflow`로 전환한다.

이번 단계의 목표는 단순히 프롬프트를 더 길게 쓰는 것이 아니다.

- 현재의 `text-only still generation` 계약을 끝내고
- `같은 사람 유지`를 generator 입력 단계에서 강하게 보장하며
- `room-first establish`를 읽히는 컷으로 만들 수 있는 구조를 도입하는 것

핵심 성공 기준은 아래 세 가지다.

1. `Camila`가 establish 후보에서 더 자주 같은 사람으로 읽힌다.
2. `REC/viewfinder/gibberish text/school-uniform drift`가 유의미하게 줄어든다.
3. selection gate가 “틀린 이미지를 버리는 단계”를 넘어 “쓸 만한 establish 후보를 실제로 받는 단계”로 이동한다.

## Current State

현재 프롬프트는 이미 구조화돼 있다. 실제 조립은
[comic_render_service.py](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend/app/services/comic_render_service.py)
의 `_build_prompt()`에서 이뤄진다.

현재 establish prompt는 대체로 아래 순서로 구성된다.

- `Panel type / Role profile`
- `Setting`
- `Scene cues`
- `Composition`
- `Subject prominence`
- `Action`
- `Quality focus`
- `Character canon`
- `Series style canon`
- `Binding`
- `Continuity`

negative prompt도 이미 강하다.

- `glamour shoot`
- `close portrait`
- `camera frame`
- `viewfinder`
- `subtitle overlay`
- `caption box`
- `unreadable text`
- `random letters`
- `gibberish text`

즉 현재 문제는 “프롬프트가 구조화되지 않았다”가 아니다.

## Root Cause

핵심 문제는 `generator contract`다.

현재 still workflow는
[workflows.py](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/lab451-animation-worker/app/workflows.py)
의 `build_sdxl_still_workflow()`를 사용하며, 구조는 사실상 아래와 같다.

- `CheckpointLoaderSimple`
- optional `LoraLoader`
- `CLIPTextEncode`
- `EmptyLatentImage`
- `KSampler`
- `VAEDecode`
- `SaveImage`

즉 다음이 전혀 없다.

- 얼굴 reference image
- 헤어 reference image
- identity-preserving image conditioning
- scene layout guidance

그래서 현재 still lane은 사실상 `prompt + negative + post-hoc selection gate`에만 의존한다.
이 구조에서는 prompt가 아무리 좋아도 아래 문제가 반복된다.

- `same-person hold` 불안정
- prompt drift
- youth drift
- overlay / fake text artifact
- room-first composition 불안정

selection은 이미 나아지고 있다. 하지만 generator가 usable 후보를 충분히 못 낸다.

## Evidence

최근 live establish 후보는 selection에서 실제로 탈락했다.

- [aa11a5fe-1b43-4836-a181-c1e823bb3c96.png](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/data/outputs/aa11a5fe-1b43-4836-a181-c1e823bb3c96.png)

이 후보는 prompt와 negative가 이미 강화된 상태에서도 아래 문제가 남았다.

- `REC/viewfinder overlay`
- `school-uniform silhouette`
- `orange-hair youth drift`
- `bottom gibberish text`
- portrait pull

DB scoring에서도 이 후보는 선택되지 않았다.

- `quality_score = 0.19`
- `identity gate: failed`

즉 지금은 “selection을 더 세게”가 아니라 “generator가 맞는 후보를 더 자주 내게” 해야 하는 단계다.

## Considered Approaches

### 1. Prompt-only refactor

장점:

- 변경 범위가 가장 작다

단점:

- 이미 current lane이 사실상 이 접근의 상한을 보여줬다
- prompt 구조는 어느 정도 정리돼 있는데도 establish가 무너진다
- text-only contract를 유지한 채로는 identity stability가 약하다

부족하다.

### 2. More checkpoints, same text-only contract

장점:

- 빠르게 시도할 수 있다

단점:

- checkpoint 바꿔도 generator contract가 그대로면 drift가 반복된다
- 최근 `establish-only style split`도 이 한계를 드러냈다

근본 해결이 아니다.

### 3. Reference-guided still lane

장점:

- identity stability를 generator 입력 단계에서 직접 강화할 수 있다
- 현재 worker에 이미 있는 `sdxl_ipadapter` 계열 자산을 재사용할 수 있다
- prompt는 role/scene grammar에 집중하고, identity는 reference가 잡게 할 수 있다

단점:

- request contract가 조금 늘어난다
- reference set 관리가 필요하다

현재 단계에 가장 적합하다.

## Recommended Direction

권장 방향은 `Camila V2 establish`를 `reference-guided still lane`으로 분기하는 것이다.

구체적으로:

- 대상은 `Camila V2 + establish`만
- generator는 기존 `sdxl_still` 대신 `sdxl_ipadapter` 계열 still workflow를 사용
- prompt는 계속 구조화하지만, 역할을 바꾼다
  - prompt = scene / action / composition / quality grammar
  - reference = identity anchor

즉 앞으로는

- `prompt`가 사람 얼굴을 만들려고 애쓰는 구조가 아니라
- `reference`가 얼굴 정체성을 잡고
- `prompt`는 컷의 읽힘과 전개를 결정하는 구조로 간다

## Design

### 1. Scope is deliberately narrow

이번 단계는 아래에만 적용한다.

- `character_id = Camila Duarte`
- `render_lane = v2`
- `panel_type = establish`

다음은 건드리지 않는다.

- legacy character lane
- beat / insert / closeup
- teaser animation preset itself

### 2. Reuse existing IPAdapter-capable worker assets

worker에는 이미 `sdxl_ipadapter` backend family와
`build_sdxl_ipadapter_frame_workflow(...)`가 있다.

이번 단계는 새 모델군을 도입하는 것이 아니라,
existing IPAdapter-capable path를 still lane에 맞게 재사용하는 것이다.

즉 새로운 방향은:

- `sdxl_still` text-only workflow를 계속 만지는 것이 아니라
- `reference-guided still request`를 새로 정의하고
- worker가 ComfyUI IPAdapter workflow로 still 1장을 생성하게 한다

### 3. New request contract

새 still request는 최소 아래를 가진다.

- `checkpoint_name`
- `width`, `height`
- `prompt`
- `negative_prompt`
- `seed`
- `reference_image_url` or uploaded image path
- `ipadapter_file`
- `ipadapter_weight`
- `ipadapter_start_at`
- `ipadapter_end_at`

핵심은 `reference_image`가 request의 first-class field가 되는 것이다.

### 4. Reference set ownership

reference set ownership은 `Character-Series Binding`에 둔다.

이유:

- 같은 캐릭터라도 시리즈 스타일에 따라 reference 적합성이 달라질 수 있다
- `Character Canon`은 사람 정의에 집중해야 한다
- 실제 생성용 reference set은 `binding`이 소유하는 것이 맞다

첫 단계에서는 Camila binding에 아래 정도만 둔다.

- hero portrait reference 1장
- half-body reference 1장
- hair / skin / facial shape가 잘 드러나는 anchor set

### 5. Prompt role changes

프롬프트는 계속 구조화하되, 목표를 바꾼다.

앞으로 establish prompt는 아래에 집중한다.

- scene readability
- prop readability
- action readability
- room-first composition
- adult subject constraint
- no second person
- no UI/text artifact intent

반대로 얼굴 정체성과 hair/skin anchor는 prompt에서 완전히 제거하지 않되,
primary signal이 아니라 보조 신호로 낮춘다.

즉:

- `identity by reference`
- `storytelling by prompt`

### 6. Selection gate remains

reference-guided lane이 들어와도 current selection gate는 유지한다.

이유:

- generator conditioning이 강해져도 bad candidate는 여전히 나올 수 있다
- overlay rejection
- multiple-face rejection
- school-uniform / youth drift rejection
- gibberish text penalty

는 그대로 필요하다

즉 설계는 `reference replaces gate`가 아니라 `reference reduces drift, gate catches leftovers`다.

### 7. Fallback and rollout

rollout은 opt-in이다.

- if `Camila V2 establish reference set` exists:
  - use reference-guided still lane
- else:
  - fallback to current text-only establish lane

이렇게 하면 초기 도입과 rollback이 쉽다.

## In Scope

- `Camila V2 establish` 전용 reference-guided still contract
- binding-owned reference set
- worker still lane에서 IPAdapter-capable path 재사용
- prompt 역할 재정의
- 기존 selection gate 유지
- one-panel establish acceptance 재검증

## Out of Scope

- 다른 캐릭터 확장
- beat / insert / closeup reference guidance
- teaser preset redesign
- CLIP STUDIO handoff
- full page layout changes

## Acceptance

이번 단계의 acceptance는 아래다.

1. `Camila V2` one-panel establish live run에서 최소 1개 후보가 `identity gate: passed`를 얻는다.
2. 선택 후보가 사람이 보기에도 같은 Camila로 읽힌다.
3. `room-first establish`가 유지된다.
4. `REC/viewfinder/gibberish text`가 이전 lane보다 줄어든다.
5. 실패하더라도 prompt-only lane보다 어디가 좋아졌고 어디가 부족한지 명확히 판정 가능하다.

## Why This Is The Right Next Step

지금 단계에서 prompt만 더 손보는 건 다시 같은 루프에 들어갈 가능성이 높다.

반면 reference-guided still lane은:

- 사용자의 최우선 요구인 `같은 캐릭터 유지`
- 현재 가장 큰 병목인 `text-only identity drift`
- establish quality 개선

을 한 번에 직접 겨냥한다.

즉 다음 단계는 `prompt tweaking`이 아니라 `generator contract upgrade`다.
