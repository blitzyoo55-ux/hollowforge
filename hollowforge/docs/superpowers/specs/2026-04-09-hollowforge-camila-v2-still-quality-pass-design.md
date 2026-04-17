# HollowForge Camila V2 Still Quality Pass Design

기준일: 2026-04-09

## Goal

`Character Canon V2 + Series Style Canon`의 구조는 유지한 채, `Camila Duarte` 파일럿 lane의 still 품질을 실제 만화 생산 기준으로 한 단계 더 끌어올린다.

이번 단계의 목표는 기능 확장이 아니다. 이미 성립한 V2 pipeline을 `읽히는 만화 컷` 수준으로 다듬는 bounded quality pass다.

이번 단계에서 반드시 만족해야 하는 기준은 아래 다섯 가지다.

1. 같은 Camila로 읽힌다.
2. 4컷이 서로 다른 panel role로 읽힌다.
3. establish 컷이 공간을 실제로 읽히게 한다.
4. 피부, 눈, 손, 포즈에서 과한 AI 티를 줄인다.
5. 같은 selected render에서 파생한 teaser에서도 동일 인물로 유지된다.

## Problem Statement

현재 V2 lane은 구조적으로는 맞다.

- `character canon`
- `series style canon`
- `character-series binding`
- `panel render profile`

이 네 층이 분리되어 있고, bounded comic/teaser pilot helper도 live acceptance를 통과했다.

하지만 실제 still 품질은 아직 `stable baseline`으로 삼기 어렵다.

문제는 세 가지다.

1. `identity information density`가 낮다.
   - 현재 V2 `character canon`은 neutral identity 방향은 맞지만, 얼굴 구조와 drift 금지 규칙이 아직 너무 얕다.
2. `style canon quality policy`가 약하다.
   - 현재 `series style canon`은 teaser motion policy 중심이고, line/shading/anti-artifact policy가 실질적으로 비어 있다.
3. `candidate selection`이 아직 storytelling-aware가 아니다.
   - 좋은 still과 읽히는 panel이 충돌할 때, 아직 selection 기준이 충분히 명시되어 있지 않다.

결과적으로 지금은 `기능은 작동하지만 품질 기준선은 약한 파일럿` 상태다.

## Scope

이번 quality pass는 아래만 다룬다.

- `Camila Duarte` V2 lane only
- comic still quality only
- teaser는 새로운 미감 확장이 아니라 `identity hold verification`만 수행
- live acceptance는 bounded helper 기준으로 유지

이번 단계에서 하지 않는 것:

- 다른 캐릭터로 V2 확장
- full model/LoRA benchmark sweep
- 새로운 frontend V2 UX 추가
- full teaser style tuning
- stable path 승격

## Design Principles

### 1. Character-first stays absolute

가장 중요한 기준은 `같은 Camila로 읽히는가`다.

따라서 이번 단계의 모든 품질 개선은 아래 원칙을 따라야 한다.

- style이 identity를 덮어쓰면 안 된다
- role grammar가 identity를 약화시키면 안 된다
- artifact suppression이 인물 정체성까지 지워선 안 된다

### 2. Favorite recipes are references, not constraints

기존 favorite checkpoint/LoRA 조합은 참고 자산일 뿐, 재사용 의무는 없다.

이번 단계에서는:

- legacy favorite aesthetics를 그대로 복원하지 않는다
- 필요한 경우 LoRA family와 artifact policy를 재구성한다
- 기준은 `좋아 보이는 single still`이 아니라 `읽히는 comic still`이다

### 3. Quality should be encoded, not improvised

품질은 prompt의 감각적 문장력에 의존하지 않고, 구조화된 필드로 관리해야 한다.

즉 이번 단계에서는 아래를 강화한다.

- `character canon`의 identity field
- `series style canon`의 quality policy field
- `binding`의 drift guard field
- `panel profile`의 readability field

## Proposed Changes

### A. Character Canon V2 enrichment

현재 Camila V2 entry는 지나치게 요약되어 있다. 아래 필드를 추가해 `identity-neutral but specific`한 설명으로 강화한다.

추가/확장 대상 예시:

- `face_structure_notes`
- `eye_signature`
- `hair_signature`
- `skin_surface_policy`
- `body_signature`
- `expression_range`
- `identity_negative_rules`

원칙:

- `glamour`, `editorial`, `resort` 같은 style-loaded 표현 금지
- 대신 실제 drift를 막는 neutral identity 표현 사용
- 피부/눈/헤어를 "예쁘게"가 아니라 "같은 사람으로 유지" 관점에서 정의

예시 방향:

- wide, observant hazel eyes instead of glamour gaze
- long chestnut waves with natural texture instead of luxury hair
- warm tan skin with natural texture, avoid waxy smoothing

### B. Series Style Canon quality policy enrichment

현재 `series style canon`은 `teaser_motion_policy`만 실질적으로 사용한다. 이를 still 품질 중심으로 확장한다.

추가 필드 예시:

- `line_policy`
- `shading_policy`
- `surface_texture_policy`
- `panel_readability_policy`
- `artifact_avoidance_policy`
- `hand_face_reliability_policy`

이 계층은 아래를 담당한다.

- 라인 밀도
- 명암 세기
- 피부/의복/배경 질감의 자연스러움
- AI 티가 강하게 나는 패턴의 회피

중요:

- checkpoint / LoRA family ownership은 여전히 style canon에 있다
- 그러나 role-specific framing은 style canon이 아니라 panel profile이 계속 소유한다

### C. Binding-level identity lock enrichment

binding은 단순 연결이 아니라 `Camila in this style`의 유지 규칙을 담아야 한다.

추가 필드 예시:

- `identity_lock_strength`
- `hair_lock_strength`
- `face_lock_strength`
- `allowed_wardrobe_family`
- `binding_negative_rules`
- `do_not_mutate`

여기서 다룰 항목:

- 얼굴 비례 drift 방지
- 헤어 길이/볼륨 drift 방지
- 과한 메이크업/광택/패션 촬영화 방지
- style-safe wardrobe만 허용

### D. Panel-role quality grammar refinement

panel profile은 role grammar를 계속 담당하되, 이번 단계에서는 quality-aware selection 기준을 명시적으로 가진다.

role별 목표:

- `establish`
  - room readability first
  - subject occupancy reduced
  - prop and depth readability required
- `beat`
  - expression readable
  - body pose natural
  - not beauty-poster framing
- `insert`
  - prop/action readability first
  - no portrait pull
- `closeup`
  - emotion clarity first
  - skin/eye artifact suppression 강화

새 규칙:

- `panel profile`은 `quality_selector_hints` 또는 동등한 구조를 가진다
- automatic or assisted selection에서 `beauty score`보다 `readability score`를 우선한다

### E. Candidate selection policy

이번 단계의 핵심은 후보를 더 많이 만드는 것이 아니라, `무엇을 좋은 후보로 볼지`를 명시하는 것이다.

Camila V2 still lane의 selection 기준:

1. same-person hold
2. role readability
3. scene readability
4. artifact suppression
5. glamour bias penalty

즉 아래는 감점 요인이다.

- close portrait로 모든 role이 수렴
- waxy skin
- dead eyes
- malformed hand detail
- floating props
- empty room despite establish role

## Acceptance Workflow

이번 단계의 acceptance는 두 단계다.

### 1. Still acceptance

bounded Camila helper로 still lane을 다시 생성한다.

검수 기준:

- Camila same-person hold
- establish / beat / insert / closeup이 role대로 읽히는지
- 피부/눈/손/포즈 artifact가 과도하지 않은지
- `AI glamour poster`보다 `comic panel`에 가까운지

### 2. Teaser identity verification

still acceptance를 통과한 selected render에서만 teaser를 다시 돌린다.

여기서의 목적은 teaser 미감 재설계가 아니다.

확인할 것:

- teaser mp4에서도 same-person hold가 유지되는지
- style canon이 motion lane에서도 너무 다르게 보이지 않는지

## Success Criteria

이번 단계는 아래를 만족하면 성공으로 본다.

1. Camila V2 one-shot에서 4컷이 서로 다른 역할로 읽힌다.
2. establish 컷에서 공간 정보가 실제로 읽힌다.
3. Camila 얼굴/헤어/인상이 still 전체에서 유지된다.
4. AI artifact가 명백하게 줄어든다.
5. same selected render 기반 teaser에서도 동일 인물로 유지된다.

## Failure Conditions

아래 중 하나면 이번 pass는 실패다.

- 여전히 모든 컷이 portrait/glamour 쪽으로 수렴
- establish가 room-first가 아니라 single-subject poster로 보임
- Camila 얼굴 정체성이 후보마다 크게 흔들림
- artifact policy 강화 때문에 오히려 인물 표현이 죽음
- teaser에서 still과 다른 인물처럼 보임

## Implementation Direction

구현은 additive bounded fix로 간다.

예상 변경 범위:

- `character_canon_v2_registry.py`
- `series_style_canon_registry.py`
- `character_series_binding_registry.py`
- `comic_render_v2_resolver.py`
- 필요 시 `comic_render_profiles.py`
- helper acceptance tests

문서/런북 변경은 acceptance가 통과한 뒤에만 반영한다.

## Recommendation

이번 단계는 `stable 승격`보다 먼저 수행되어야 한다.

이유:

- 지금 V2 lane은 작동은 하지만 품질 기준선이 아직 충분히 단단하지 않다
- 지금 stable로 올리면 `구조는 좋지만 결과물 기준이 약한 baseline`을 고정하게 된다
- Camila 한 명에서 still quality pass를 통과한 뒤 승격하는 편이 훨씬 안전하다

따라서 다음 구현 단계는 `Camila V2 still quality pass`를 bounded하게 실행하는 것이다.
