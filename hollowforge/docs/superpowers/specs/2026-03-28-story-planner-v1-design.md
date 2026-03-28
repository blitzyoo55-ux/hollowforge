# Story Planner V1 Design

## Goal

`/prompt-factory`에 `Story Planner` 모드를 추가해, 사용자가 자유 문장으로 짧은 에피소드 아이디어를 입력하면 HollowForge가 이를 `episode brief + shot plan`으로 정리하고, 사람 승인 후 shot별 anchor still을 생성할 수 있게 한다.

이번 범위의 목표는 세 가지다.

- 자유 문장 기반의 서사 입력을 사람이 검수 가능한 planning artifact로 바꾼다.
- 기존 캐릭터 registry와 자유 문장 캐릭터를 함께 지원한다.
- 전연령/성인향 레인을 세계관과 분리된 policy pack으로 처리한다.

이번 문서는 기존 [2026-03-28-character-profile-builder-design.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/docs/superpowers/specs/2026-03-28-character-profile-builder-design.md)의 후속 서브프로젝트다. `Character Profile Builder`가 정적 profile set 생성에 초점을 두었다면, `Story Planner v1`은 짧은 내러티브를 structured shot plan으로 바꾸는 데 초점을 둔다.

## Current System Fit

현재 HollowForge에는 이미 sequence 기반의 shot/anchor/animation orchestration 골격이 있다. 하지만 이 계층은 `character_id`, `location_id`, `beat_grammar_id`, `content_mode` 같은 구조화된 입력을 직접 요구한다. 또한 첫 Stage 1 shot planning은 고정된 continuity 규칙과 단일 장소 중심 grammar를 전제로 한다.

즉 현재 시스템은 “정리된 blueprint를 실행하는 엔진”이고, 이번 설계는 그 앞단에 “자유 문장을 blueprint로 바꾸는 planner”를 붙이는 일이다.

## User Outcomes

사용자는 아래 흐름으로 작업한다.

1. 자유 문장으로 에피소드 아이디어를 적는다.
2. 필요하면 `등장인물 참조` 토글을 켜고 registry 캐릭터를 주인공/보조 인물로 선택한다.
3. 콘텐츠 레인을 고른다.
4. `Plan Episode`를 눌러 `episode brief + shot plan preview`를 본다.
5. preview를 검토하고 승인한다.
6. 승인 뒤 shot별 anchor still 생성만 수행한다.
7. 생성 결과를 `/queue` 또는 `/gallery`에서 확인한다.

핵심은 사용자가 프롬프트 문법이 아니라 서사 단위로 작업한다는 점이다. 또한 생성 전 승인 게이트가 있어 “AI가 멋대로 렌더링했다”는 느낌 대신 “내가 감독처럼 해석안을 승인했다”는 UX를 만든다.

## Scope Guardrails

첫 버전은 아래 제약을 둔다.

- 단일 장소
- 주인공 1명
- 보조 인물 최대 1명
- 주인공 중심 framing 우선
- 길이 30~60초 내외의 짧은 에피소드
- shot count 4~6
- still anchor generation까지만 자동화

첫 버전에서 하지 않는 것:

- multi-location episode
- 3인 이상 cast
- dialogue/lipsync planning
- 애니메이션 자동 dispatch
- rough cut review UI
- full world bible editor

보조 인물 최대 1명은 “서사상 존재 가능”을 의미한다. 첫 버전의 시각적 기본값은 주인공 중심 framing이며, 보조 인물이 실제 프레임 안에 함께 등장하는 shot은 제한적으로만 허용한다. 이 제약은 현재 HollowForge의 단일 주체 continuity 강점을 해치지 않기 위한 것이다.

## Information Architecture

`/prompt-factory` 상단 mode switch는 아래 세 가지가 된다.

- `Character Profile`
- `Story Planner`
- `Advanced Batch`

이번 문서의 범위는 `Story Planner` 모드다.

화면은 네 단계로 구성한다.

1. `Story Input`
2. `Plan Review`
3. `Approval`
4. `Anchor Results`

모바일에서는 세로 스택으로 접되, preview cards가 중심이 되도록 한다.

## Story Input

기본 입력은 자유 문장이다.

사용자가 입력하는 최소 값:

- `story prompt`
- `lane`
- `등장인물 참조` 토글
- `lead character` 선택 optional
- `support character` 선택 optional
- `tone` optional
- `target duration` optional

### Input rules

- 자유 문장은 항상 허용한다.
- `등장인물 참조` 토글이 켜지면 registry 캐릭터를 주인공 또는 보조 인물로 고정할 수 있다.
- 토글이 꺼져 있으면 문장 속 이름/묘사는 freeform cast로 해석한다.
- 장소는 첫 버전에서 별도 selector 없이 자유 문장에서 해석하되, 내부 구조는 이후 registry location 확장을 수용하도록 설계한다.

## Canon Layer Vs Story Draft Layer

데이터는 두 층으로 나눈다.

### 1. Canon Layer

장기 보관되고 재사용되는 자산이다.

- `canon_character`
- `canon_location`
- `canon_policy_pack`
- 향후 `worldline`

### 2. Story Draft Layer

이번 생성 작업만을 위한 planning artifact다.

- `story_plan`
- `story_plan_cast`
- `story_plan_shot`

이 분리가 중요하다. canon은 장기 기억이고, story draft는 개별 에피소드 해석이다. 자유 문장을 production prompt로 바로 쓰지 않고, 반드시 draft 계층을 거친 뒤 사람이 승인한다.

## Canon Assets

첫 버전의 canon 자산은 구조화된 파일 기반 catalog로 시작한다.

### `canon_character`

최소 필드:

- `id`
- `name`
- `canonical_anchor`
- `anti_drift`
- `wardrobe_notes`
- `personality_notes`
- `preferred_checkpoints`

### `canon_location`

최소 필드:

- `id`
- `name`
- `setting_anchor`
- `visual_rules`
- `restricted_elements`

### `canon_policy_pack`

최소 필드:

- `id`
- `lane`
- `prompt_provider_profile_id`
- `negative_prompt_mode`
- `forbidden_defaults`
- `planner_rules`
- `render_preferences`

초기 source of truth는 사람이 읽을 수 있고 git diff가 쉬운 구조화 파일로 둔다. markdown 설명 문서는 남길 수 있지만, runtime은 markdown을 직접 파싱하지 않는다.

## Story Draft Models

### `story_plan`

최소 필드:

- `id`
- `raw_user_prompt`
- `lane`
- `status`
- `episode_brief_json`
- `continuity_risk_json`

상태는 아래를 쓴다.

- `draft`
- `planned`
- `approved`
- `rendering`
- `completed`
- `failed`

### `story_plan_cast`

최소 필드:

- `story_plan_id`
- `role`
- `source_type`
- `resolved_character_id` nullable
- `freeform_description`

`role`은 아래만 지원한다.

- `lead`
- `support`

`source_type`은 아래만 지원한다.

- `registry`
- `freeform`

### `story_plan_shot`

최소 필드:

- `story_plan_id`
- `shot_no`
- `beat_type`
- `shot_goal`
- `camera_intent`
- `action_intent`
- `emotion_intent`
- `continuity_rules`
- `expected_anchor_prompt_summary`
- `render_status`

## Planning Flow

planner는 자유 문장을 바로 prompt로 넘기지 않는다. 아래 순서로 structured output을 만든다.

1. `Input interpretation`
2. `Cast/location resolution`
3. `Episode brief generation`
4. `Shot plan generation`
5. `Approval gate`

### 1. Input interpretation

문장에서 아래 값을 추출한다.

- 주인공
- 보조 인물 유무
- 장소
- 핵심 사건
- 감정선
- 예상 길이
- 금지 요소

### 2. Cast/location resolution

- 사용자가 명시적으로 고른 registry 캐릭터는 우선 고정한다.
- 자유 문장 속 이름은 registry fuzzy match를 시도하고, 실패하면 freeform cast로 둔다.
- 장소도 동일한 구조로 해석하되 첫 버전은 freeform 우선 허용한다.

### 3. Episode brief generation

planner는 shot plan 전에 아래 구조를 만든다.

- `one_line_premise`
- `cast_summary`
- `location_summary`
- `tone_summary`
- `lane_policy_summary`
- `continuity_risks`

### 4. Shot plan generation

첫 버전은 4~6 shots만 허용한다.

각 shot은 아래를 가진다.

- `beat_type`
- `shot_goal`
- `camera_intent`
- `action_intent`
- `emotion_intent`
- `continuity_rules`
- `expected_anchor_prompt_summary`

shot planning은 sequence engine의 기존 강점을 활용해 단일 장소 continuity를 우선한다.

### 5. Approval gate

사용자는 raw prompt가 아니라 planning result를 본다.

수정 가능한 값:

- 주인공/보조 인물 참조
- 장소 해석
- lane
- tone
- shot count

사용자가 승인하기 전에는 GPU 작업을 시작하지 않는다.

## Policy Packs

세계관과 레인을 분리한다. 같은 캐릭터와 같은 장소를 써도, 표현 강도와 render 제약은 `policy pack`이 결정한다.

첫 버전의 pack:

- `unrestricted`
- `all_ages`
- `adult_nsfw`

`unrestricted`는 planner lane 개념이고, generation contract에서는 기존 `Character Profile Builder` 설계와 맞춰 `content_mode = null`, `prompt_provider_profile_id = null`로 해석한다.

### Shared rule

모든 pack은 공통 canon을 쓴다. 별도의 “전연령 세계관”과 “성인향 세계관”을 따로 만들지 않는다.

### `unrestricted`

- 기본값
- planner 해석 폭이 가장 넓다.
- negative prompt 기본 모드는 `blank`
- generation handoff 시 `content_mode`는 비워 둔다.
- 다만 하드 금지 항목은 공통 유지한다.

### `all_ages`

- planner가 scene을 안전 표현으로 재기술할 수 있다.
- safe prompt profile을 사용한다.
- recommended negative를 기본 사용한다.
- preview에서 lane-safe rewrite가 있었다면 표시한다.

### `adult_nsfw`

- 성인 전용 레인
- 등장 인물은 adult canonical identity여야 한다.
- adult lane용 prompt/render preference를 사용한다.
- canon identity drift는 여전히 금지한다.

## UI Design

`Story Planner` 모드는 아래 네 단계 UX를 사용한다.

### 1. Story Input

- 자유 문장 입력
- lane 선택
- 등장인물 참조 토글
- lead/support registry selector
- tone / duration
- advanced settings 접힘

### 2. Plan Review

- `episode brief` 카드
- `cast resolution` 카드
- `continuity risk` badge
- 4~6개 `shot cards`

각 shot card는 아래를 보여 준다.

- beat
- shot goal
- camera
- action
- emotion
- continuity note
- expected anchor prompt summary

### 3. Approval

CTA는 아래 세 가지다.

- `Edit Input`
- `Regenerate Plan`
- `Approve And Generate Anchors`

### 4. Anchor Results

- shot별 render status
- queue / gallery 링크
- best still review 링크
- 향후 animation action 영역

애니메이션 CTA는 첫 버전에서 비활성 상태 또는 명시적 다음 단계 안내로 둔다.

## Backend Scope

백엔드 변경 범위는 아래다.

- story planner request/response schema 추가
- story planner service 추가
- canon asset loader 추가
- story_plan persistence 또는 equivalent runtime store 추가
- approval 이후 shot still batch generation handoff 추가
- lane-aware policy pack resolution 추가

현재 sequence/orchestration 계층을 재사용할 수 있는 부분은 재사용하되, 첫 버전은 “planner -> still batch”에 집중한다.

## Frontend Scope

프론트 변경 범위는 아래다.

- [PromptFactory.tsx](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/frontend/src/pages/PromptFactory.tsx)
  - `Story Planner` mode 추가
  - story input form 추가
  - plan review cards 추가
  - approval CTA 추가
  - anchor results state 추가
- 필요 시 작은 하위 컴포넌트로 분리

새 top-level route는 만들지 않는다.

## Runtime Flow

승인 후 생성 흐름은 아래다.

1. approved story plan을 shot rows로 정규화
2. 각 shot에 대해 기본 2-candidate anchor still generation request 생성
3. batch queue 등록
4. queue / gallery handoff
5. 사람이 shot 결과를 검토하고 best still을 고른다
6. 이후 애니메이션 단계는 별도 서브프로젝트에서 수행

## Testing Strategy

### Frontend

- `Story Planner` mode 렌더링
- 자유 문장 입력
- registry character toggle / selection
- lane 전환
- plan preview 렌더링
- approval CTA
- anchor result state

### Backend

- story planner request normalization
- registry + freeform cast resolution
- lane별 policy pack 선택
- shot plan count and schema validation
- approval 후 still batch handoff
- unrestricted/all_ages/adult lane 회귀

### Runtime verification

- unrestricted 1건
- all_ages 1건
- 필요 시 adult_nsfw 1건
- queue/gallery에서 결과 확인

## Deployment Sequence

1. canon asset foundation
2. planner contract and service
3. Story Planner UI
4. approval -> still batch handoff
5. local smoke
6. server HollowForge 반영
7. server smoke

## Risks And Mitigations

- 자유 문장이 planner를 과도하게 흔들 수 있다.
  - mitigation: 첫 버전은 cast/location/shot count 범위를 강하게 제한한다.
- registry와 freeform cast가 섞이면 continuity가 약해질 수 있다.
  - mitigation: preview 단계에서 registry matched / freeform을 명시적으로 보여 준다.
- world bible을 markdown-only로 두면 runtime 재사용성이 떨어진다.
  - mitigation: canon은 structured catalog를 source of truth로 둔다.
- 생성 전 승인 없이 바로 render하면 실패 비용이 커진다.
  - mitigation: approval gate를 강제한다.

## Success Criteria

- 사용자가 자유 문장으로 짧은 episode idea를 넣고 planning result를 검수할 수 있다.
- registry character와 freeform character가 함께 동작한다.
- 전연령/성인향이 같은 canon 위에서 policy pack으로 분리된다.
- 승인 뒤 shot별 anchor still이 정상 생성된다.
- 기존 `Character Profile`과 `Advanced Batch` 흐름은 깨지지 않는다.
