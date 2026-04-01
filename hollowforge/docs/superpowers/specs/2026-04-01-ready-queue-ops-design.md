# HollowForge Ready Queue Ops Design

Date: 2026-04-01

## Goal

`/ready -> /marketing` publishing pilot 흐름에서 caption provider readiness를
operator가 더 일찍 볼 수 있게 만들고, provider secret이 없을 때 workbench가
설명 가능한 `draft-only` 모드로 degrade되도록 한다.

이번 변경의 목적은 세 가지다.

- publishing caption readiness를 batch 진입 시점에 노출한다.
- `Generate caption`이 클릭 후 `500`으로 실패하는 흐름을 줄인다.
- provider readiness가 부족해도 internal draft publish job path는 계속
  사용할 수 있게 유지한다.

## Non-Goals

이번 설계는 아래를 하지 않는다.

- caption quality 튜닝
- caption provider 교체
- secret 저장 UI 또는 key rotation 도구 추가
- publish job 외부 발행기 연동
- animation follow-up 자동화
- ready queue selection UX 전체 재설계

## Why This Scope

2026-04-01 adult pilot에서 아래 흐름은 실제로 검증됐다.

- `Story Planner`
- anchor generation
- ready toggle
- internal draft publish job 생성

하지만 caption generation은 runtime에 `OPENROUTER_API_KEY`가 없어 실제 operator가
버튼을 누른 뒤에야 실패를 알게 됐다.

즉 현재 가장 큰 문제는 "publishing tool이 없다"가 아니라:

- readiness가 진입 전에 보이지 않는다.
- key가 없을 때 UI/API가 operator에게 충분히 설명적인 방식으로 degrade되지
  않는다.

지금 필요한 것은 작은 운영 계약 보강이지, publishing stack 전체 확장이 아니다.

## Current System Fit

현재 관련 구조는 아래와 같다.

- `frontend/src/pages/ReadyToGo.tsx`
  - ready batch를 `publish_approved=1` 기준으로 선택해 `/marketing`으로 넘긴다.
- `frontend/src/pages/Marketing.tsx`
  - selected `generation_id`가 있으면 `PublishingPilotWorkbench`를 연다.
- `frontend/src/components/publishing/PublishingPilotWorkbench.tsx`
  - ready items, captions, publish jobs를 읽고 batch view를 조립한다.
- `frontend/src/components/publishing/PublishingPilotCard.tsx`
  - caption generate / approve / draft publish job create 액션을 가진다.
- `backend/app/routes/publishing.py`
  - ready-items, caption generation, caption approval, publish job 생성 route를 제공한다.
- `backend/app/services/caption_service.py`
  - runtime에 `OPENROUTER_API_KEY`가 없으면 caption generation을 실패시킨다.

현재 readiness 개념은 Prompt Factory에는 있지만, publishing domain에는 없다.
그래서 workbench가 "caption path는 지금 unavailable"이라는 사실을 미리 전달할 수
없다.

## Approaches Considered

### 1. Frontend-only guard

frontend가 key readiness를 추정해 버튼만 막는 방식이다.

장점:

- 가장 빠르게 만들 수 있다.

단점:

- API direct call path는 그대로 실패한다.
- readiness 기준이 backend와 분리된다.
- 다른 frontend surface가 생기면 로직이 흩어진다.

### 2. Backend readiness contract + frontend degrade

추천 접근이다.

장점:

- backend와 frontend가 같은 readiness 기준을 쓴다.
- operator는 batch 진입 순간에 현재 mode를 이해할 수 있다.
- API를 우회 호출해도 같은 의미의 실패를 받는다.
- draft-only fallback을 명시적으로 지원할 수 있다.

단점:

- frontend-only patch보다 구현량이 약간 늘어난다.

### 3. Full publishing preflight framework

caption, draft, animation, external posting readiness를 하나의 큰 preflight로 묶는
방식이다.

장점:

- 장기적으로는 운영 시야가 넓어진다.

단점:

- 이번 요구보다 범위가 크다.
- current blocker 하나를 해결하는 데 과하다.

이번 브랜치에는 맞지 않는다.

## Chosen Design

추천안 2를 채택한다.

새 publishing readiness endpoint를 추가하고, `Marketing`/`PublishingPilotWorkbench`/
`PublishingPilotCard`가 이 상태를 읽어 `full` 또는 `draft_only` 모드로 동작한다.

핵심 설계는 아래와 같다.

1. backend는 publishing caption readiness를 구조화된 응답으로 제공한다.
2. key가 없더라도 readiness endpoint는 실패하지 않고 `draft_only`를 반환한다.
3. caption generation action path는 readiness false일 때 더 설명적인 operator error를
   반환한다.
4. frontend는 workbench 진입 시 readiness banner를 보여준다.
5. caption 버튼만 비활성화하고, draft 생성 path는 유지한다.

## Backend Contract

새 endpoint는 아래로 둔다.

- `GET /api/v1/publishing/readiness`

응답 구조는 publishing domain 전용으로 작게 유지한다.

```json
{
  "caption_generation_ready": false,
  "draft_publish_ready": true,
  "degraded_mode": "draft_only",
  "provider": "openrouter",
  "model": "x-ai/grok-2-vision-1212",
  "missing_requirements": ["OPENROUTER_API_KEY"],
  "notes": [
    "Caption generation is unavailable until OPENROUTER_API_KEY is configured."
  ]
}
```

필드 의미는 아래와 같다.

- `caption_generation_ready`
  - live caption generation 가능 여부
- `draft_publish_ready`
  - internal draft publish job path 가능 여부
- `degraded_mode`
  - `"full"` 또는 `"draft_only"`
- `provider`
  - 현재 caption provider name
- `model`
  - 현재 caption model
- `missing_requirements`
  - operator가 바로 이해할 수 있는 부족 조건 목록
- `notes`
  - UI banner에 그대로 요약 표시 가능한 안내 문구

이번 브랜치에서 readiness 계산은 단순하게 유지한다.

- `OPENROUTER_API_KEY` 존재 시:
  - `caption_generation_ready = true`
  - `draft_publish_ready = true`
  - `degraded_mode = "full"`
- `OPENROUTER_API_KEY` 부재 시:
  - `caption_generation_ready = false`
  - `draft_publish_ready = true`
  - `degraded_mode = "draft_only"`
  - `missing_requirements = ["OPENROUTER_API_KEY"]`

이 endpoint는 `500` 중심 endpoint가 아니어야 한다. secret이 없어도 `200 OK`로
현재 운영 모드를 반환한다.

## Action Path Error Behavior

`POST /api/v1/publishing/generations/{generation_id}/captions/generate`
는 readiness false 상태일 때 operator-facing error를 반환해야 한다.

이번 브랜치에서는 아래 contract로 맞춘다.

- status: `503 Service Unavailable`
- detail:
  - `Caption generation unavailable: OPENROUTER_API_KEY is not configured`

즉 UI에서 미리 막지 못했거나 direct API call이 들어와도, 현재 상태를 설명하는
안정적인 오류를 준다.

반대로 아래 path는 계속 허용한다.

- `POST /api/v1/publishing/posts` with `status="draft"`

이 경로는 provider key가 없어도 internal draft job 생성이 가능해야 한다.

## Frontend Behavior

### Marketing Page

`frontend/src/pages/Marketing.tsx`

- publishing selection이 있으면 readiness query를 함께 수행한다.
- workbench 위에 readiness summary banner를 렌더링한다.
- `draft_only`면 아래 의미를 직접 드러낸다.
  - caption generation unavailable
  - draft creation still available

selection이 없을 때는 기존 caption generator empty state를 유지한다.

### PublishingPilotWorkbench

`frontend/src/components/publishing/PublishingPilotWorkbench.tsx`

- ready-items query와 함께 readiness query를 수행한다.
- batch header에 current mode를 노출한다.
- `missing_requirements.length > 0`면 operator warning box를 보여준다.
- `PublishingPilotCard`에 readiness 정보를 prop으로 내려준다.

이번 브랜치에서 workbench는 operator에게 "무엇이 막혔는가"를 보여주는 수준까지만
책임진다. provider setup 안내 wizard는 추가하지 않는다.

### PublishingPilotCard

`frontend/src/components/publishing/PublishingPilotCard.tsx`

- `caption_generation_ready=false`면 `Generate caption` 버튼을 비활성화한다.
- 버튼 근처에 reason text를 보여준다.
  - 예: `Caption generation unavailable: OPENROUTER_API_KEY is not configured`
- 기존 local error box는 action 실패 시 그대로 유지한다.
- `Create draft` 버튼은 readiness false여도 계속 허용한다.
- 즉 카드 단위 모드는:
  - caption: blocked
  - draft publish: allowed

## File-Level Plan

이번 설계에서 예상하는 주요 변경 위치는 아래와 같다.

- Modify: `backend/app/models.py`
  - publishing readiness response model 추가
- Modify: `backend/app/routes/publishing.py`
  - readiness endpoint 추가
  - caption generate preflight check + `503` detail 정리
- Modify: `frontend/src/api/client.ts`
  - readiness response type + fetch function 추가
- Modify: `frontend/src/pages/Marketing.tsx`
  - readiness banner wiring
- Modify: `frontend/src/components/publishing/PublishingPilotWorkbench.tsx`
  - readiness query + warning box + card prop 전달
- Modify: `frontend/src/components/publishing/PublishingPilotCard.tsx`
  - caption button disable + reason text

테스트 파일은 아래를 기준으로 한다.

- Modify: `backend/tests/test_publishing_service.py`
  - readiness filter/service 회귀 유지
- Create: `backend/tests/test_publishing_routes.py`
  - readiness endpoint와 caption `503` contract 검증
- Modify: `frontend/src/pages/Marketing.test.tsx`
  - readiness banner 상태 추가
- Modify: `frontend/src/components/publishing/PublishingPilotWorkbench.test.tsx`
  - readiness warning/mode 표시 추가
- Create: `frontend/src/components/publishing/PublishingPilotCard.test.tsx`
  - disabled caption button + draft path 유지 검증

## Testing Strategy

이번 브랜치는 TDD로 진행한다.

backend 타깃:

- key 없음:
  - readiness returns `draft_only`
  - caption generate returns `503`
  - draft publish job create still succeeds
- key 있음:
  - readiness returns `full`

frontend 타깃:

- workbench 진입 시 `draft_only` banner가 보인다.
- missing requirement 문구가 노출된다.
- card의 `Generate caption` 버튼이 비활성화된다.
- 같은 상태에서도 `Create draft`는 계속 활성화된다.

verification 범위는 아래로 제한한다.

- `pytest backend/tests/test_publishing_routes.py backend/tests/test_publishing_service.py -q`
- `npm test -- src/pages/Marketing.test.tsx src/components/publishing/PublishingPilotWorkbench.test.tsx src/components/publishing/PublishingPilotCard.test.tsx`

전체 앱 회귀나 deploy build는 이번 spec의 기본 완료 조건에 포함하지 않는다.

## Acceptance Criteria

이 브랜치는 아래가 모두 만족되면 완료다.

- `/api/v1/publishing/readiness`가 현재 mode를 `200 OK`로 반환한다.
- key가 없을 때 workbench 진입 즉시 `draft_only` 상태가 보인다.
- key가 없을 때 `Generate caption`은 disabled + 이유 문구가 보인다.
- key가 없을 때 `Create draft`는 여전히 동작한다.
- caption route direct call은 `503`과 설명적인 detail을 반환한다.
- key가 있을 때 readiness는 `full`로 보고된다.

## Why This Is Enough

이번 pilot에서 이미 `anchor generation -> ready queue -> draft publish job` path는
살아 있다는 증거를 얻었다. 다음 브랜치의 역할은 새 기능을 많이 늘리는 것이 아니라,
operator가 "지금 무엇이 가능한가"를 workbench 진입 순간 이해하게 만드는 것이다.

그 목적에는 publishing readiness contract와 `draft_only` degrade만으로 충분하다.
