# HollowForge Scene-First Establish Recipe Design

Date: 2026-04-09

## Goal

현재 `comic panel render profile` 분리 이후에도 `establish` 컷이 여전히 `story panel`보다 `좋아 보이는 single still`에 가깝다.

이번 bounded fix의 목표는 하나다.

- `establish`를 `scene-first storytelling panel`로 강제해서, 인물 중심 glamour 수렴을 더 약하게 만든다

이번 단계는 `AI 티를 완전히 숨기는 것`이 아니다.
목표는 `AI 생성 만화라는 점은 느껴지지만, 컷을 읽는 몰입을 깨지 않을 정도로 정돈된 만화 컷`이다.

## Current Failure

live acceptance 기준으로 아래는 이미 해결됐다.

- worker payload `seed` 전파 누락 버그 수정
- `Artist Loft Morning` location resolution 복구
- role-aware profile 적용

그러나 직접 확인한 최신 establish 결과물:

- `data/outputs/a9d50865-f0a3-4ad5-9aee-64b324fab7bc.png`

판단:

- bathhouse glamour portrait보다는 좋아졌다
- 하지만 여전히 `room-first establishing panel`은 아니다
- 인물 점유율이 너무 크고
- loft를 읽게 하는 핵심 props가 약하며
- 결과적으로 `예쁜 1장 일러스트` 쪽으로 읽힌다

즉 현재 병목은 `seed`, `location`, `panel role` 자체가 아니라
`scene-first composition recipe`의 부재다.

## Problem Statement

현재 `establish_env_v1`는 아래 한계를 가진다.

1. same checkpoint + same beauty-friendly prompt spine 위에서 동작한다
2. setting이 prompt 앞에 와도 subject styling block이 여전히 강하다
3. location anchor는 들어가지만 `scene cue visibility`가 없다
4. framing rule은 문장으로만 존재하고, recipe 수준의 강제력이 약하다

그래서 모델은 결국 다음 쪽으로 회귀한다.

- large single subject
- centered or near-centered beauty focus
- weak room readability
- weak prop storytelling

## Considered Approaches

### 1. Prompt Wording Only

establish prompt 문장을 더 세게 조정한다.

장점:

- 구현이 가장 빠르다

단점:

- 이미 한계가 확인됐다
- `scene-first`를 구조적으로 강제하지 못한다

부족하다.

### 2. Scene-First Establish Recipe

`establish` 전용 recipe를 강화한다.

핵심:

- scene block을 prompt의 절대 우선순위로 올린다
- scene cues를 강제한다
- subject prominence를 낮춘다
- beauty-biased checkpoint/anchor influence를 더 약하게 만든다

장점:

- 가장 작은 수정으로 live failure에 직접 대응한다
- 현재 profile layer 위에 자연스럽게 얹을 수 있다

단점:

- profile field와 prompt builder가 조금 더 복잡해진다

이번 단계에 가장 적합하다.

### 3. Full Comic Recipe Split

comic 전용 checkpoint league와 character-version family까지 새로 분리한다.

장점:

- 장기적으로 가장 강하다

단점:

- 지금 단계에서는 과하다
- live failure를 닫기 전에 구조만 커진다

이번 단계에는 제외한다.

## Recommended Direction

권장안은 `2. Scene-First Establish Recipe`다.

핵심 원칙:

- `beat`와 `closeup`은 현재 profile split을 유지
- `establish`만 추가 강화
- `canonical_still`은 identity anchor로만 사용
- `scene readability`는 별도 recipe가 책임진다

즉 앞으로의 책임 분리는 아래와 같다.

- `character_version`: 인물 정체성
- `comic_render_profile`: 컷 역할
- `scene-first recipe`: 공간 읽힘과 소품 가시성

## In Scope

- `ComicPanelRenderProfile`에 establish-only scene-first knob 추가
- `establish_env_v2` recipe 도입
- `Artist Loft Morning`에 한정된 optional scene cues 추가
- prompt builder가 establish에서만 scene cues를 front-load
- establish negative append 강화
- live single-panel validation으로 scene readability 재확인

## Out Of Scope

- 새로운 DB table
- shot registry 변경
- teaser preset 변경
- full storyboard system
- publish/export automation

## Design

## 1. Profile Model Extension

`backend/app/services/comic_render_profiles.py`의 profile model에 아래 필드를 추가한다.

- `prompt_order_mode`
  - `default_subject_first`
  - `scene_first`
- `subject_prominence_mode`
  - `default`
  - `reduced`
- `scene_cue_mode`
  - `none`
  - `artist_loft_scene_cues`

이번 단계의 초기 의도:

- `establish_env_v2`
  - `prompt_order_mode=scene_first`
  - `subject_prominence_mode=reduced`
  - `scene_cue_mode=artist_loft_scene_cues`

`beat_dialogue_v1`, `insert_prop_v1`, `closeup_emotion_v1`는 유지한다.

## 2. No Checkpoint Split In This Phase

이번 단계에서는 checkpoint override를 하지 않는다.

이유:

- 현재 live evidence는 `room-first composition` 실패에 직접 묶여 있다
- checkpoint split은 범위를 불필요하게 키우고 identity drift risk를 늘린다

즉 이번 단계는 `same checkpoint, different establish recipe`로 간다.

## 3. Location Metadata Extension

`backend/app/story_planner_assets/locations.json`에 아래 optional field를 추가한다.

- `scene_cues`

`Artist Loft Morning` 예시:

- `scene_cues`
  - `tall factory windows`
  - `easel`
  - `canvas`
  - `worktable`
  - `coffee mug`
  - `sketchbook`

규칙:

- 이 field는 optional이다
- 값이 없는 다른 location은 기존 동작을 유지한다
- 이번 단계에서 selection logic은 deterministic하게 앞의 2개 cue만 사용한다
- `artist_loft_morning`만 실제로 값을 채운다

즉 전역 schema overhaul이 아니라,
`Artist Loft Morning live failure`를 닫기 위한 최소 metadata 추가다.

## 4. Establish / Insert Prompt Assembly

현재 structured prompt는 유지하되,
`establish`에 한해 prompt block 순서를 바꾼다.

기존 경향:

- setting
- action
- composition
- style and subject
- emotion
- continuity

새 `scene_first` 순서:

- setting
- scene cues
- composition rule
- subject prominence rule
- action
- minimal subject identity
- continuity

`minimal subject identity`는 인물 식별에 필요한 최소 요소만 남긴다.

예:

- character name
- hair / skin / silhouette anchor

반대로 establish에서는 아래를 제거하거나 약화한다.

- `tasteful adult allure`
- glamour-adjacent editorial phrasing
- face-first attraction cues

## 5. Negative Prompt Policy

`establish`에 아래 negative 개념을 추가한다.

- `single-subject glamour poster`
- `pinup composition`
- `beauty key visual`
- `empty background`
- `minimal room detail`
- `subject filling frame`

문구는 모델 친화적으로 짧게 정리하되,
의도는 `room unreadable + subject dominant`를 억제하는 것이다.

## 6. Acceptance Criteria

이번 bounded fix의 acceptance는 aesthetic perfection이 아니다.

아래 기준을 만족하면 통과다.

1. `Artist Loft Morning` establish selected image에서 loft로 읽히는 prop이 최소 2개 이상 보인다
2. subject가 frame 대부분을 차지하지 않는다
3. 이전 `a9d50865...` establish보다 room readability가 분명히 좋아진다
4. 세 candidate가 서로 거의 같은 portrait로 붕괴하지 않는다

반대로 아래면 실패다.

- still은 예쁘지만 establishing panel로 읽히지 않음
- room보다 얼굴이 먼저 읽힘
- location을 바꿔도 비슷한 인물 컷이 반복됨

## Testing

테스트는 세 층으로 둔다.

### Unit

- profile resolver가 `establish_env_v2`를 돌려주는지
- `Artist Loft Morning` scene cue selection이 deterministic하게 2개를 반환하는지
- scene-first prompt block builder가 subject-first 순서를 쓰지 않는지

### Integration

- establish payload가 scene-first prompt order를 쓰는지
- establish payload가 same checkpoint를 유지하는지
- establish payload에 selected scene cues가 실제로 들어가는지
- establish payload negative prompt에 scene-first negatives가 들어가는지

### Live Acceptance

- stable runtime에서 single-panel remote smoke 재실행
- selected output 직접 검수
- acceptance 기준 충족 여부를 눈으로 판단

## Risks

### Risk 1: scene cue overfit

scene cue를 너무 세게 넣으면 컷이 기계적으로 보일 수 있다.

완화:

- cue는 2개만 사용
- cue는 setting 뒤에만 넣고, checklist처럼 길게 나열하지 않는다

### Risk 2: overcorrection

scene가 읽히더라도 컷이 너무 밋밋해질 수 있다.

완화:

- beat/closeup/insert는 기존 profile 유지
- establish만 제한적으로 조정

### Risk 3: prompt bloat

scene cue를 너무 많이 넣으면 prompt가 산만해질 수 있다.

완화:

- scene cue는 최대 2개만 front-load

## Exit Condition

이번 단계가 성공하면 다음 상태가 된다.

- `favorite-informed still`과 `scene-first establish`가 실제로 분리된다
- AI 티를 완전히 지우지 않아도 `읽을 수 있는 패널` 쪽으로 품질 기준이 올라간다
- 이후 더 큰 model-lane split이 필요하더라도, 그 필요성을 live evidence로 판단할 수 있다
