# HollowForge Manga Format / Visual Style Separation Design

기준일: 2026-04-10

## Goal

`일본 만화 스타일`을 더 이상 단일 생성 지시어로 취급하지 않고, 아래 두 층으로 분리한다.

- `Manga Format Layer`
- `Visual Style Layer`

이번 단계의 목표는 단순한 용어 정리가 아니다.

- `일본 만화`를 `출판/독서 문법`으로 다시 정의하고
- 그림체와 미감은 별도 `style canon`이 담당하게 하며
- prompt가 format과 style을 동시에 떠맡다가 품질을 무너뜨리는 구조를 끊는다

핵심 성공 기준은 아래 세 가지다.

1. 생성 prompt에서 `manga style`이 직접적인 그림체 지시로 과도하게 쓰이지 않는다.
2. `컷 역할`, `페이지 문법`, `balloon/SFX safe zone`은 format metadata가 소유한다.
3. `작화 분위기`, `매력도`, `AI artifact 완화`, `checkpoint/LoRA 조합`은 visual style이 소유한다.

## Current Problem

현재 HollowForge는 `일본 만화`를 두 의미로 동시에 사용하고 있다.

1. `포맷`
   - 컷 분할
   - 페이지 전개
   - 말풍선
   - 출판 원고
   - 우철/안전영역

2. `그림체`
   - 선
   - 톤
   - 분위기
   - 얼굴 인상
   - 배경 처리

이 둘이 prompt 안에서 섞이면서 모델이 아래처럼 오해할 가능성이 높아진다.

- `manga panel` -> 과장된 애니풍 still
- `anime heroine`에 가까운 youth drift
- `학교 / 교복 / 청춘물` 계열 상투성
- `REC / subtitle / frame` 같은 영상형 overlay artifact

즉 현재 실패는 단지 checkpoint 문제만이 아니라, 생성 계약의 의미 층이 섞여 있다는 데 있다.

## Evidence

최근 establish 실험들에서 공통적으로 드러난 것은 다음이다.

- selection gate는 점점 좋아졌다
- 하지만 generator는 `같은 Camila`, `room-first establish`, `성숙한 매력`, `overlay 없음`을 동시에 잘 못 만든다

대표 실패 예시:

- [2d4f0288-f908-489e-8472-bfea5ceb709e.png](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/data/outputs/2d4f0288-f908-489e-8472-bfea5ceb709e.png)
- [b384d539-47fb-4b58-953a-b4250725dae7.png](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/data/outputs/b384d539-47fb-4b58-953a-b4250725dae7.png)
- [d5927ec4-a07e-43af-8bce-56cb73c7bca3.png](/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/data/outputs/d5927ec4-a07e-43af-8bce-56cb73c7bca3.png)

직접 본 결과는 일관됐다.

- `room-first establish`가 잘 안 잡힘
- 성숙한 adult attractiveness보다 `anime school / youth drift`가 쉽게 튀어 나옴
- reference-guided lane도 format/style 혼선 자체를 해결해주진 못함

즉 generator가 `무슨 포맷으로 읽히게 만들 것인지`와 `어떤 미감으로 보이게 만들 것인지`를 동시에 떠맡고 있다.

## Root Cause

핵심 root cause는 `format semantics`와 `visual semantics`가 같은 prompt 블록 안에서 결합돼 있는 것이다.

현재 생성 prompt는 대체로 아래를 한 번에 싣는다.

- panel type / role
- setting / scene cues
- composition
- character canon
- series style canon
- continuity
- 일부 `manga` 관련 표현

이 구조에서는 다음 문제가 반복된다.

- `manga`가 레이아웃/독서 문법이 아니라 그림체 힌트처럼 읽힌다
- checkpoint가 그 힌트를 youth/anime shorthand로 해석한다
- prompt 길이가 길어질수록 실제 중요한 신호와 메타 신호가 섞인다

따라서 `manga`는 prompt의 style 지시가 아니라, 상위 metadata layer로 올려야 한다.

## Recommended Direction

권장 방향은 `Manga Format Layer / Visual Style Layer` 분리다.

### 1. Manga Format Layer

이 층은 아래를 소유한다.

- cut role (`establish / beat / insert / closeup`)
- page flow
- gaze direction / reading order
- panel occupancy target
- balloon-safe area
- caption-safe area
- SFX-safe area
- 일본 출판 원고 규격 metadata

이 층은 원칙적으로 `layout`, `assembly`, `handoff`, `selection hints`에서 소비한다.

생성 prompt에는 직접적인 그림체 지시 대신, 아래처럼 `scene/composition constraints`만 내려보낸다.

- `wide room view`
- `single adult subject`
- `subject secondary to environment`
- `leave negative space for dialogue`
- `props readable`

즉 `manga`는 앞으로 `reading format`이다.

### 2. Visual Style Layer

이 층은 아래를 소유한다.

- checkpoint family
- LoRA stack
- line quality
- shading density
- surface texture
- attractive adult presentation
- anti-artifact negative policy

즉 `series style canon`은 더 이상 `일본 만화` 전체를 떠안지 않고, 순수하게 `어떻게 보일 것인가`만 담당한다.

### 3. Character Identity Layer

이 층은 그대로 유지하되 역할을 더 분명히 한다.

- 얼굴
- 머리
- 피부
- 체형
- 금지 drift

즉 character canon은 style과 format을 소유하지 않는다.

### 4. Binding Layer

binding은 다음만 담당한다.

- 해당 style 안에서 캐릭터가 어떻게 유지되는가
- wardrobe family
- adult appeal notes
- reference set ownership

binding도 `manga format`을 소유하지 않는다.

## Design

### A. Prompt ownership is narrowed

앞으로 generated still prompt는 아래만 직접 포함한다.

- scene
- composition
- subject occupancy
- character identity
- visual style

반대로 아래는 prompt 직접 지시를 줄이거나 제거한다.

- `japanese manga style`
- `manga art style`
- `anime manga panel`
- 기타 format과 style을 혼합하는 표현

특히 `manga panel`은 가능한 한 `role metadata`로 남기고, prompt에서는 `room-first`, `single adult subject`, `negative space`, `prop readability` 같은 구체적 composition language로 치환한다.

### B. Page assembly owns manga-ness

`일본 만화다움`의 핵심은 아래로 이동한다.

- page layout templates
- variable panel sizing
- emphasis panel rules
- text placement metadata
- SFX anchors
- manuscript profile

즉 `만화다움`은 이미지 1장 안의 그림체보다, 여러 컷이 읽히는 방식과 텍스트/효과음이 얹히는 방식에서 구현한다.

### C. Style canon owns artistic tone

`series style canon`은 앞으로 다음 질문만 답한다.

- 성숙한가
- 매력적인가
- 과한 AI 티가 없는가
- line/shading/texture가 읽히는가

즉 `일본 만화처럼 보여라`가 아니라 `이 시리즈의 미감으로 보여라`가 된다.

## In Scope

- `manga format`과 `visual style`의 역할 정의를 문서 계약으로 고정
- 이후 prompt wording 정리 기준 제시
- page assembly / text-safe / SFX-safe가 format layer 소유임을 명시
- style canon이 visual appearance를 소유함을 명시

## Out of Scope

- 즉시 모든 prompt rewrite
- 즉시 모든 checkpoint 재선정
- CLIP STUDIO EX 도입 시점 결정
- text-safe/SFX-safe 전체 구현

이번 단계는 구조 정의까지다.

## Migration Guidance

적용 순서는 아래가 맞다.

1. 현재 실패한 `reference-guided establish lane`은 stable 승격하지 않는다.
2. `establish`는 temporary fallback lane으로 되돌린다.
3. 다음 generator 실험부터는 prompt에서 `manga style` 직접 표현을 줄인다.
4. `manga format`은 page assembly / handoff / text metadata 설계로 보낸다.
5. visual quality는 `series style canon + LoRA stack`에서 다시 잡는다.

## Acceptance Criteria

이 설계가 다음 단계에서 통과하려면 아래가 보여야 한다.

1. 새 generator 실험 prompt에서 `manga`는 style shortcut이 아니라 composition/format metadata로 취급된다.
2. establish still 품질 논의가 `일본 만화풍이냐`가 아니라 `room-first readability / same-person hold / adult appeal` 기준으로 이뤄진다.
3. 향후 page assembly와 balloon/SFX 설계가 자연스럽게 `format layer` 위에서 이어질 수 있다.
