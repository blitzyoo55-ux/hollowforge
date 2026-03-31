# Adult Grok Default Provider Design

Date: 2026-03-31

## Goal

`Prompt Factory`의 `adult_nsfw` lane 기본 prompt provider를 `OpenRouter -> Grok`로 전환하고, `Story Planner`의 adult policy metadata를 같은 provider 방향에 맞춰 정렬한다.

이번 변경의 목적은 세 가지다.

- adult 파일럿에서 local LLM 기본값 대신 Grok 위임 경로를 기본선으로 검증한다.
- `Prompt Factory + Story Planner metadata` 범위에서만 변경을 적용해, sequence/orchestration 계층까지 한 번에 흔들지 않는다.
- adult lane의 provider 기본값을 명시적으로 분리해, 이후 prompt-facing surfaces와 sequence runtime defaults를 독립적으로 운영할 수 있게 한다.

## Non-Goals

이번 설계는 아래를 하지 않는다.

- `sequence/orchestration`의 adult 기본 prompt profile 변경
- animation executor 기본값 변경
- adult lane 정책 완화 또는 금지 규칙 축소
- 노골적인 프롬프트 템플릿 추가
- safe lane 기본값 변경

## Why This Scope

현재 코드에서는 `Prompt Factory`가 adult 기본 provider를 sequence default 설정에서 그대로 읽는다. 그래서 지금 구조에서 단순히 adult default profile을 바꾸면, 의도와 다르게 sequence/orchestration adult default까지 함께 바뀐다.

이번 파일럿의 검증 대상은 `Story Planner -> anchor still -> Ready to Go -> publishing pilot` 흐름이다. sequence/orchestration adult runtime까지 동시에 바꾸면, 문제 발생 시 원인을 분리하기 어려워진다.

따라서 이번 변경은 `prompt-facing surfaces`와 `sequence runtime`을 기본값 수준에서 분리하는 것이 핵심이다.

## Current System Fit

현재 관련 구조는 이렇게 나뉜다.

- `sequence_registry.py`
  - lane별 prompt provider profile registry 보유
- `prompt_factory_service.py`
  - content mode default를 해석하고 capabilities에 노출
- `policy_packs.json`
  - Story Planner lane별 policy metadata 보유
- `story_planner_service.py`
  - policy pack을 선택해 `policy_pack_id`와 anchor metadata를 유지하지만, planning 단계에서 provider를 직접 호출하지는 않음

즉 이번 변경은 실제 planning 문장 생성기보다도 `default resolution`, `profile metadata`, `capabilities surface`, `adult policy pack metadata`를 정렬하는 작업이다.

## Approaches Considered

### 1. Global adult default를 통째로 Grok로 변경

`HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE`와 registry default를 직접 바꾸는 방식이다.

장점:

- 구현이 가장 단순하다.

단점:

- sequence/orchestration adult runtime까지 함께 바뀐다.
- 파일럿 실패 시 Prompt Factory 문제인지 sequence runtime 문제인지 분리하기 어렵다.

이 접근은 이번 범위에 비해 너무 넓다.

### 2. Prompt-facing defaults를 sequence defaults에서 분리하고 adult Grok profile을 추가

추천 접근이다.

장점:

- `Prompt Factory + Story Planner`에만 영향이 간다.
- adult 파일럿의 원인 분리가 쉽다.
- 이후 sequence runtime은 기존 local LLM 기본값을 유지할 수 있다.

단점:

- 설정 키가 2개 정도 늘어난다.

### 3. 요청 단위 opt-in만 지원하고 기본값은 유지

장점:

- runtime 리스크가 가장 낮다.

단점:

- 사용자가 원하는 “adult lane 기본 provider를 Grok로 잡기”를 충족하지 못한다.
- 파일럿 운영자가 매번 명시적으로 provider를 고르게 된다.

이번 요구에는 맞지 않는다.

## Chosen Design

추천안 2를 채택한다.

핵심 설계는 아래와 같다.

1. `sequence_registry.py`에 `adult_openrouter_grok` prompt provider profile을 추가한다.
2. `Prompt Factory`는 adult lane에 한해서 기존 sequence default 환경변수가 아니라, prompt-facing 전용 adult default 설정을 읽는다.
3. 새 prompt-facing adult default의 기본값은 `adult_openrouter_grok`로 둔다.
4. `Story Planner`의 `adult_nsfw` policy pack metadata도 `adult_openrouter_grok`를 가리키도록 바꾼다.
5. `sequence/orchestration`의 adult 기본값은 계속 `adult_local_llm` 계열로 둔다.

추가 범위 주의:

- 새 profile은 shared registry에 등록되므로, 이후 sequence/orchestration 호출자가 `prompt_provider_profile_id`를 명시적으로 `adult_openrouter_grok`로 지정하면 opt-in 형태로 사용할 수 있다.
- 하지만 이번 변경은 sequence/orchestration의 기본값, runbook 권장 경로, preflight 기대값을 바꾸지 않는다.

## Provider Profile Shape

새 profile은 아래 속성을 갖는다.

- `id`: `adult_openrouter_grok`
- `content_mode`: `adult_nsfw`
- `provider_kind`: `openrouter`
- `structured_json`: `True`
- `strict_json`: `False`

`strict_json`을 `False`로 두는 이유는 OpenRouter/Grok 경로의 실제 JSON 안정성을 adult 파일럿에서 먼저 확인하려는 목적 때문이다. 기존 local strict-json profile은 sequence/orchestration 쪽 fallback/기존 경로로 남겨둔다.

이 profile은 일반 OpenRouter profile이 아니라 `Grok`로 고정된 adult profile이어야 한다. 따라서 구현은 profile 해석 시 adult lane 전용 model source를 사용하거나, 최소한 `x-ai/grok` 계열 model로 핀된 설정만 허용해야 한다.

## Configuration Changes

새 설정은 adult prompt-facing 기본값에만 한정해서 추가한다.

- `HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE`
- `HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL`

기본값은 아래처럼 둔다.

- adult: `adult_openrouter_grok`
- adult model: `x-ai/grok-4.1-fast`

이 설정은 `Prompt Factory`와 그 capability surface의 adult default 해석에만 사용한다. safe lane은 현행 sequence-safe 기본값을 그대로 따른다. sequence runtime이 사용하는 기존 설정:

- `HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE`
- `HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE`

는 그대로 유지한다.

## Story Planner Impact

`Story Planner`는 현재 planning 단계에서 provider를 직접 호출하지 않는다. 또한 current preview/anchor queue contract는 `policy_pack_id`와 anchor render snapshot을 주로 전달하지, `prompt_provider_profile_id`를 직접 handoff payload에 싣지는 않는다.

따라서 이번 변경에서 `policy_packs.json`의 `canon_adult_nsfw_v1`를 `adult_openrouter_grok`로 바꾸는 목적은 contract expansion이 아니라:

- catalog metadata 정렬
- adult policy metadata와 Prompt Factory adult default 방향 통일
- 이후 adult planner/provider lineage의 의미적 일관성 확보

에 있다.

중요한 점:

- `policy_pack_id` 자체는 유지한다.
- forbidden baseline과 negative prompt behavior는 유지한다.
- adult lane의 approval gate는 유지한다.

즉 이번 변경은 provider metadata 변경이지, adult lane policy relaxation이 아니다.

## File Changes

### Backend

- Modify: `backend/app/config.py`
  - adult prompt-facing default profile/model settings 추가
- Modify: `backend/app/services/sequence_registry.py`
  - `adult_openrouter_grok` profile 추가
- Modify: `backend/app/services/prompt_factory_service.py`
  - adult content mode default resolution이 prompt-facing adult settings를 읽도록 변경
  - `adult_openrouter_grok` profile이 Grok-pinned model source를 사용하도록 변경
- Modify: `backend/app/story_planner_assets/policy_packs.json`
  - `canon_adult_nsfw_v1.prompt_provider_profile_id`를 `adult_openrouter_grok`로 변경

### Tests

- Modify: `backend/tests/test_sequence_registry.py`
  - capabilities/default resolution 회귀를 prompt-facing defaults 기준으로 갱신
- Modify: `backend/tests/test_story_planner_catalog.py`
  - adult policy pack prompt profile expectation 갱신
- Modify: `backend/tests/test_story_planner_routes.py`
  - adult lane preview metadata regression 보강

## Runtime Behavior After Change

### Prompt Factory

- `content_mode="adult_nsfw"` + provider default 해석 시 `adult_openrouter_grok`를 선택한다.
- `Prompt Factory capabilities`의 adult default 항목은 `provider_kind="openrouter"`와 adult Grok-pinned model을 노출한다.
- `OPENROUTER_API_KEY`가 없으면 adult default readiness는 false가 된다.

### Story Planner

- adult plan preview의 `policy_pack_id`는 그대로 `canon_adult_nsfw_v1`
- 해당 policy pack metadata는 `adult_openrouter_grok`를 참조
- approval 후 still handoff contract는 그대로 유지

### Sequence / Orchestration

- 기본 adult prompt profile은 현행 `adult_local_llm` 계열 유지
- preflight/runbook 기대값도 그대로 유지

## Testing Strategy

### Unit / Service

- `Prompt Factory capabilities`가 adult default를 `adult_openrouter_grok`로 보고하는지 검증
- adult default readiness가 `OPENROUTER_API_KEY` 기준으로 계산되는지 검증
- sequence runtime default 테스트는 기존 `adult_local_llm` 기대값을 유지하는지 검증
- Story Planner catalog adult policy pack이 새 profile id를 노출하는지 검증

### Route / Contract

- adult Story Planner preview route가 기존 `policy_pack_id`와 anchor contract를 유지하는지 검증
- Story Planner catalog/policy metadata의 adult `prompt_provider_profile_id`가 registry에서 유효한 adult profile로 해석되는지 검증
- adult `provider="default"` Prompt Factory generation이 새 prompt-facing default path를 타는지 검증
- adult `provider="default"` 해석 결과가 `provider_kind="openrouter"`와 non-strict JSON runtime option을 갖는지 검증

### Runtime Verification

최소 검증은 아래 두 개다.

1. adult `Prompt Factory` preview 또는 generate 호출 1건
2. adult `Story Planner` preview + anchor queue handoff 1건

이번 runtime verification은 explicit content 산출 자체보다:

- provider resolution correctness
- refusal/JSON stability
- queue handoff continuity

를 본다.

## Risks And Mitigations

- OpenRouter/Grok가 adult high-heat 요청에서 거절 또는 약화 응답을 낼 수 있다.
  - mitigation: strict-json 강제 대신 structured-json 중심으로 두고, small pilot에서 refusal rate를 본다.

- Grok-specific default라고 해놓고 실제 model source가 일반 OpenRouter model로 흐를 수 있다.
  - mitigation: adult OpenRouter profile은 adult 전용 Grok model setting으로 핀한다.

- Prompt-facing default와 sequence default가 분리되면 운영자가 혼동할 수 있다.
  - mitigation: capabilities surface와 spec/plan 문서에 분리 의도를 명시한다.

- Story Planner metadata만 바뀌고 실제 runtime planner 품질은 그대로일 수 있다.
  - mitigation: 이번 변경의 목표를 provider default alignment로 한정하고, 품질 평가는 파일럿 회고에서 분리한다.

## Success Criteria

- `Prompt Factory` adult default provider가 `adult_openrouter_grok`로 해석된다.
- `Prompt Factory capabilities` adult default가 OpenRouter/Grok readiness를 정확히 반영한다.
- `Story Planner` adult policy pack metadata가 `adult_openrouter_grok`를 가리킨다.
- `sequence/orchestration` adult default는 기존 local LLM profile을 유지한다.
- adult pilot에서 provider resolution과 queue handoff가 깨지지 않는다.

## References

- `backend/app/config.py`
- `backend/app/services/sequence_registry.py`
- `backend/app/services/prompt_factory_service.py`
- `backend/app/story_planner_assets/policy_packs.json`
- `docs/GROK_PROMPT_FACTORY_20260311.md`
- `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md`
