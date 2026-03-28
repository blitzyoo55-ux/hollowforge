# Character Profile Builder Design

## Goal

`/prompt-factory`를 기존의 전문가용 배치 프롬프트 도구에서, 사람이 바로 사용할 수 있는 `Character Profile Builder` 중심 UX로 확장한다.

이번 범위의 핵심 목표는 세 가지다.

- 특정 캐릭터를 더 쉽게 선택하고 재사용할 수 있게 한다.
- 콘텐츠 제약을 `기본 무제한 / NSFW / 전연령`으로 명확히 분리한다.
- 사용자는 `캐릭터 선택 -> 콘텐츠 레인 선택 -> 생성`의 최소 흐름만으로 프로필 세트를 만들 수 있게 한다.

이번 설계는 새 전용 페이지를 만들지 않고, 기존 [PromptFactory.tsx](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/frontend/src/pages/PromptFactory.tsx)에 사람 중심의 builder shell을 넣는 방향으로 진행한다.

## User Outcomes

사용자는 다음 두 수준의 경험을 갖는다.

### 1. 기본 사용자 흐름

기본 사용자는 아래 세 단계만 이해하면 된다.

1. 캐릭터를 고른다.
2. 콘텐츠 레인을 고른다.
3. `Generate Now`를 누른다.

그 뒤 내부적으로는 다음이 자동 처리된다.

- canonical anchor 채움
- 권장 shot mix 채움
- 적절한 content lane 기본값 적용
- negative prompt 정책 결정
- prompt generation
- queue 등록
- 이미지 생성

### 2. 고급 사용자 흐름

고급 사용자는 `Advanced Settings`를 열어 아래 항목을 직접 수정할 수 있다.

- prompt provider profile override
- tone / heat / autonomy
- direction pass
- forbidden elements
- negative prompt custom 입력
- raw prompt batch preview

기본 UX는 사람 친화형으로 유지하고, 기존 전문가용 제어는 숨기되 제거하지 않는다.

## Information Architecture

`/prompt-factory` 상단에 `Creation Mode`를 추가한다.

- `Character Profile`
- `Advanced Batch`

기본 진입은 `Character Profile`로 한다. 기존 Lab-451 중심 배치 도구는 `Advanced Batch` 모드로 유지한다.

`Character Profile` 모드는 아래 블록 순서로 구성한다.

1. `Character Picker`
2. `Content Lane`
3. `Profile Goal / Shot Mix`
4. `Style Notes / Forbidden / Negative Prompt Mode`
5. `Preview Cards`
6. `Queue Handoff`

`Advanced Settings`는 접힌 상태로 시작한다.

## Character Picker

캐릭터 선택 UX는 범용성과 재사용성을 위해 네 가지 진입으로 나눈다.

- `Recent`
- `Favorites`
- `Registry`
- `Custom`

### Behavior

- 사용자가 registry 기반 캐릭터를 선택하면 아래 값이 자동 채워진다.
  - `name`
  - `canonical_anchor`
  - `anti_drift`
  - `preferred_checkpoints`
  - `default_shot_mix`
  - `default_style_notes`
- 사용자가 `Custom`을 고르면 빈 폼에서 직접 작성한다.
- 사용자는 자동 채워진 값을 수정할 수 있다.

### Data Source

문서형 markdown registry를 프론트가 직접 파싱하지 않는다. 대신 구조화된 character catalog를 서버가 제공한다.

각 catalog item은 최소 아래 필드를 가진다.

- `id`
- `name`
- `tier`
- `favorite_score`
- `canonical_anchor`
- `anti_drift`
- `preferred_checkpoints`
- `default_shot_mix`
- `default_style_notes`

초기 seed 데이터는 [HOLLOWFORGE_RESERVE_CHARACTER_REGISTRY_20260321.md](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/docs/HOLLOWFORGE_RESERVE_CHARACTER_REGISTRY_20260321.md) 같은 기존 문서를 기반으로 별도 catalog 자산으로 정리한다.

## Content Lane

사용자는 prompt 제약을 직접 프롬프트 문법으로 다루지 않고, 콘텐츠 레인 선택으로 제어한다.

레인은 세 가지다.

- `Unrestricted`
- `NSFW`
- `All Ages`

### UX rules

- 기본값은 `Unrestricted`
- 사용자는 콘텐츠 강도를 “제약 있음/없음” 관점이 아니라 작업 레인으로 이해한다.
- 기본 화면에서는 내부 구현 키(`content_mode`, `prompt_provider_profile_id`)를 노출하지 않는다.

### Backend contract

- `Unrestricted`
  - `content_mode = null`
  - `prompt_provider_profile_id = null`
- `NSFW`
  - `content_mode = adult_nsfw`
  - `prompt_provider_profile_id`는 adult 기본 profile 추천값 사용
- `All Ages`
  - `content_mode = all_ages`
  - `prompt_provider_profile_id`는 safe 기본 profile 추천값 사용

현재 backend는 `content_mode` 기반 default profile 선택 로직을 이미 일부 가지고 있으므로, 이번 범위에서는 “optional content_mode”를 합법적인 계약으로 승격하는 방향으로 맞춘다.

## Negative Prompt Mode

negative prompt는 더 이상 전역 문자열 하나를 강제로 주입하지 않는다. 대신 모드 기반으로 결정한다.

모드는 세 가지다.

- `blank`
- `recommended`
- `custom`

### Default mapping

- `Unrestricted` -> `blank`
- `NSFW` -> `recommended`
- `All Ages` -> `recommended`

### Lane policy

- `Unrestricted + blank`
  - backend는 negative prompt를 자동 주입하지 않는다.
- `NSFW + recommended`
  - 품질 결함 + 미성년 방지 중심 negative prompt 사용
- `All Ages + recommended`
  - 품질 결함 + 미성년 방지 + explicit/fetish 차단 negative prompt 사용
- `custom`
  - 사용자 입력값을 그대로 사용

### Important behavior change

현재 [generation_service.py](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/backend/app/services/generation_service.py)는 빈 negative prompt를 받으면 `settings.DEFAULT_NEGATIVE_PROMPT`를 자동 주입한다. 이번 설계에서는 “빈 값을 의도적으로 유지”할 수 있는 신호가 필요하다. 구현 시에는 `negative_prompt_mode` 또는 동등한 필드로 자동 주입 여부를 분기한다.

## Profile Goal And Shot Mix

기본 사용자가 추가 설명 없이도 품질 있는 profile set을 만들 수 있어야 한다.

초기 기본값은 아래와 같다.

- `Profile Goal`: `Reference Set`
- `Shot Mix`: 5-shot default
  - front portrait x2
  - three-quarter x2
  - medium full-body x1

사용자는 필요하면 goal과 shot mix를 수정할 수 있다. 다만 기본 흐름에서는 “캐릭터 선택 + 레인 선택 + 생성”만으로도 적당한 결과가 나오도록 기본값을 자동 채운다.

## Preview Experience

preview는 raw JSON 표보다 `shot cards` 중심으로 보여 준다.

각 card는 최소 아래 정보를 보여 준다.

- shot title
- anchor summary
- checkpoint
- selected LoRA
- positive prompt 펼치기
- negative prompt 펼치기

기본 화면에서는 사람이 읽을 수 있는 요약을 우선하고, full prompt는 펼쳐서 보게 한다.

CTA는 두 가지다.

- `Generate Now`
- `Preview First`

`Generate Now`는 내부적으로 preview를 포함한 generate-and-queue 흐름처럼 동작할 수 있지만, 사용자에게는 한 번의 생성 액션으로 보이게 한다.

## Queue Handoff

queue 성공 후 사용자는 다음 세 가지 액션을 즉시 볼 수 있어야 한다.

- `Open Queue`
- `Open Gallery`
- `Generate Another Set`

즉 생성 성공 후 사용자가 막히지 않게 한다. `/queue`와 `/gallery`는 현재 라우트를 재사용한다.

## Frontend Scope

프론트 변경 범위는 아래와 같다.

- [PromptFactory.tsx](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/design-character-profile-builder-20260328/hollowforge/frontend/src/pages/PromptFactory.tsx)
  - builder shell 추가
  - creation mode switch 추가
  - character picker UI 추가
  - content lane UI 추가
  - negative prompt mode UI 추가
  - preview cards presentation 추가
- 필요 시 관련 UI를 작은 하위 컴포넌트로 분리한다.

이번 범위에서는 새 top-level route를 만들지 않는다.

## Backend Scope

백엔드 변경 범위는 아래와 같다.

- character catalog read endpoint 추가
- prompt generation request에서 optional `content_mode` 허용
- negative prompt policy 계약 추가
- `Unrestricted + blank`일 때 default negative auto-injection 방지
- `NSFW / All Ages`일 때만 lane별 recommended negative 사용
- 기존 `generate`, `queue`, `generate-and-queue` 라우트는 최대한 재사용

또한 이미 수정 중인 safe all-ages prompt 흐름은 이번 설계의 일부로 정식화한다.

## Out Of Scope

이번 범위에서 하지 않는 것:

- 별도 `/character-profiles` 신규 페이지
- 캐릭터 contact sheet 전용 리뷰 페이지
- 캐릭터 catalog 관리용 admin UI
- animation/sequence UX 통합
- registry markdown 자동 파싱 엔진

## Testing Strategy

### Frontend

- creation mode switch 렌더링
- character picker autofill
- content lane 전환
- negative prompt mode 전환
- `Generate Now`와 `Preview First` 흐름
- preview cards 렌더링
- queue handoff CTA

### Backend

- `Unrestricted / NSFW / All Ages` request normalization
- `blank` negative mode가 실제 blank로 유지되는지
- `recommended` mode에서 lane별 negative가 맞게 들어가는지
- safe all-ages prompt drift 회귀 유지
- 기존 adult lane이 깨지지 않는지

### Runtime verification

- `Character Profile` UX로 실제 1회 generate smoke
- `Unrestricted` 1건, `All Ages` 1건, 필요 시 `NSFW` 1건 smoke
- 결과가 `/queue`, `/gallery`, `/gallery/:id`에서 보이는지 확인

## Deployment Sequence

1. 로컬 UX/contract 구현
2. frontend/backend 테스트 통과
3. 실제 profile generation smoke
4. 서버 HollowForge에 반영
5. 배포 후 `/prompt-factory`, `/queue`, `/gallery` smoke

## Risks And Mitigations

- `Unrestricted` 기본값이 기존 safe/adult default injection과 충돌할 수 있다.
  - mitigation: request contract에 `negative_prompt_mode`와 optional `content_mode`를 명시적으로 추가한다.
- 캐릭터 catalog가 문서형 자산과 분리되면 drift가 생길 수 있다.
  - mitigation: 초기에는 curated catalog를 명시 자산으로 관리하고, source doc 링크를 남긴다.
- 기존 Prompt Factory 사용자가 새 UX에 방해받을 수 있다.
  - mitigation: `Advanced Batch` 모드를 유지하고 기존 흐름을 보존한다.

## Success Criteria

- 사용자가 `캐릭터 선택 -> 콘텐츠 레인 선택 -> 생성` 흐름만으로 프로필 세트를 만들 수 있다.
- `Unrestricted`가 실제로 기본 무제한으로 동작한다.
- `All Ages`는 explicit/fetish drift 없이 안전하게 동작한다.
- 기존 Prompt Factory 전문가 흐름은 유지된다.
