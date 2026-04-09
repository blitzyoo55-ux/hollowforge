# HollowForge Character Canon 2.0 + Series Style Canon Design

기준일: 2026-04-09

## Goal

HollowForge의 캐릭터 정체성 유지력을 최우선으로 두면서, 작품/시리즈별로 다른 화풍과 연출을 안정적으로 적용할 수 있는 새 기준선을 정의한다.

이번 설계의 목표는 세 가지다.

1. 같은 캐릭터가 여러 시리즈에 등장해도 얼굴 정체성이 유지되게 한다.
2. 시리즈별로 다른 style canon을 독립적으로 운영할 수 있게 한다.
3. 기존 `favorite still recipe`가 만화 panel 품질을 과하게 지배하는 구조를 분리한다.

이번 단계는 `legacy를 즉시 폐기`하지 않는다. 기존 캐릭터/레시피는 참조용으로 동결하고, 새 구조를 `Camila Duarte` 1캐릭터 파일럿으로 검증한다.

## Background

현재 HollowForge는 캐릭터 정체성, favorite 기반 스타일, panel role별 연출 규칙이 너무 강하게 묶여 있다.

그 결과:

- 같은 인물의 얼굴 정체성은 비교적 유지되지만
- 만화 컷에서도 `favorite still` 미학이 과적용되어
- establish/beat/insert/closeup이 서로 다른 컷 문법으로 읽히지 않는 경우가 많다.

이 구조에서는 `좋아 보이는 single still`과 `읽히는 만화 컷`이 계속 충돌한다.

따라서 다음 분리가 필요하다.

- `Character Canon` = 누구인가
- `Series Style Canon` = 어떻게 보이는가
- `Panel Render Profile` = 어떻게 찍는가

## Design Principles

### 1. Character-first

얼굴 정체성은 캐릭터 레벨에서 고정한다.

캐릭터 canon은 아래만 담당한다.

- 얼굴 구조
- 눈/코/입 인상
- 헤어 실루엣
- 체형 범위
- 표정 범위
- 금지 변형

여기에는 `glamour`, `editorial`, `resort`, `couture` 같은 스타일 지시를 넣지 않는다.

### 2. Series-owned style

화풍은 시리즈가 소유한다.

Series Style Canon은 아래를 담당한다.

- checkpoint family
- LoRA family
- line quality
- shading density
- tonal direction
- anti-AI artifact policy
- manga still / teaser animation 공통 미감

즉 시리즈가 바뀌면 같은 캐릭터라도 다른 미감을 입을 수 있다.

### 3. Binding is explicit

캐릭터와 시리즈 스타일의 결합은 별도 binding으로 관리한다.

이 binding은 아래를 담당한다.

- style-safe wardrobe
- face anchor strength
- hair anchor strength
- style-specific do / don't
- reference set

이 계층이 있어야 같은 캐릭터가 여러 시리즈 스타일에서 안정적으로 재사용된다.

### 4. Panel roles stay separate

Panel role은 별도 계층으로 유지한다.

- `establish`
- `beat`
- `insert`
- `closeup`

각 role은 구도, 비율, prompt order, negative policy를 가진다.

즉 최종 생성은 아래 네 층을 합친 결과다.

- character canon
- series style canon
- character-series binding
- panel render profile

## Proposed Model

### A. Character Canon 2.0

새 `character canon`은 스타일-중립적 identity 모델이다.

필수 필드 예시:

- `character_id`
- `display_name`
- `identity_anchor`
- `face_structure_notes`
- `hair_signature`
- `body_signature`
- `expression_range`
- `anti_drift_rules`
- `identity_reference_set_id`
- `status`

중요한 점:

- 기존 `canonical prompt anchor`는 그대로 쓰지 않는다.
- `brazilian glamour beauty` 같은 style-loaded 표현은 제거한다.
- 대신 사람 자체를 설명하는 neutral identity anchor를 사용한다.

### B. Series Style Canon

새 `series style canon`은 작품 레벨 스타일 모델이다.

필수 필드 예시:

- `series_style_id`
- `series_id`
- `display_name`
- `visual_direction_summary`
- `checkpoint_family`
- `lora_family`
- `line_policy`
- `shading_policy`
- `palette_policy`
- `artifact_avoidance_policy`
- `manga_panel_policy`
- `teaser_motion_policy`
- `status`

중요한 점:

- 기존 favorite 모델/LoRA는 참고 자료일 뿐이다.
- 새 style canon은 `현재 제작 목적에 맞는 결과`를 기준으로 다시 구성한다.
- 필요하면 기존 favorite recipe를 버릴 수 있다.

### C. Character-Series Binding

같은 캐릭터가 특정 시리즈에서 어떤 look으로 읽힐지 고정한다.

필수 필드 예시:

- `binding_id`
- `character_id`
- `series_style_id`
- `display_name`
- `binding_anchor`
- `face_lock_strength`
- `hair_lock_strength`
- `wardrobe_allowlist`
- `binding_reference_set_id`
- `binding_negative_rules`
- `status`

이 계층은 `character`와 `style`의 경계가 무너지지 않게 한다.

### D. Panel Render Profile

기존 방향을 유지하되, 상위 계층과의 책임을 더 분명히 한다.

- panel profile은 더 이상 character look을 직접 책임지지 않는다.
- panel profile은 role별 연출만 책임진다.

즉:

- `character canon`은 identity
- `style canon`은 look-and-feel
- `binding`은 compatibility
- `panel profile`은 shot grammar

## Legacy Strategy

이번 단계에서는 기존 구조를 즉시 지우지 않는다.

### Legacy freeze

다음은 `legacy reference lane`으로 동결한다.

- 기존 core character registry
- 기존 canonical recipe lock
- 기존 `character_versions` 기반 canonical still lane

이 자산들은 당장 삭제하지 않는다.

역할은 다음과 같다.

- 현재 시스템이 어디서 출발했는지 보여 주는 참조
- Camila 파일럿에서 비교 기준 제공
- 새 구조가 안정화되기 전 fallback 역할

### No immediate bulk migration

핵심 캐릭터 전체를 한 번에 옮기지 않는다.

이유:

- 기준이 아직 fully validated 되지 않았다.
- 전체를 동시에 건드리면 drift와 품질 회귀를 한꺼번에 만든다.

따라서 새 구조는 `Camila Duarte` 1캐릭터 파일럿부터 시작한다.

## Camila Duarte Pilot

### Why Camila first

Camila는 이미 comic pilot에 실제로 사용됐고, `artist loft morning`에서 establish 문제를 직접 드러낸 캐릭터다.

따라서 이 캐릭터는 다음 두 가지를 동시에 검증하기 좋다.

- 얼굴 정체성 유지
- glamour bias 억제 후에도 콘텐츠 품질 유지

### Pilot steps

1. `Camila legacy freeze`
   - 현재 core registry와 canonical recipe lock의 Camila는 그대로 둔다.
2. `Camila Character Canon 2.0`
   - neutral identity anchor를 새로 작성한다.
3. `Series Style Canon 1종`
   - 파일럿 원샷/teaser에 공통 적용할 style canon 1개를 정의한다.
4. `Camila x Series Binding`
   - 해당 시리즈에서 Camila가 어떻게 유지되는지 고정한다.
5. `Panel profile linkage`
   - establish / beat / insert / closeup에 새 상위 계층을 연결한다.
6. `Pilot validation`
   - one-shot 1편
   - teaser 1개

### Camila Character Canon 2.0 draft direction

남길 것:

- sun-kissed tan skin
- long chestnut waves
- warm hazel eyes
- refined facial structure
- soft athletic silhouette
- hair movement and warmth

제거할 것:

- `brazilian glamour beauty`
- `resort-glamour lane`
- 기타 style-loaded descriptor

즉 Camila는 `glamour trope`가 아니라 `동일 인물`로 먼저 정의되어야 한다.

## Validation Criteria

새 구조가 통과하려면 최소 아래가 만족되어야 한다.

### Character stability

- 같은 캐릭터가 still/teaser 모두에서 같은 인물로 읽힌다.
- 얼굴 구조, 눈 인상, 헤어 실루엣 drift가 허용 범위 안에 있다.

### Style flexibility

- 시리즈 스타일이 바뀌어도 character identity가 붕괴하지 않는다.
- style canon이 캐릭터 identity를 덮어쓰지 않는다.

### Comic readability

- 4패널이 서로 다른 컷 역할을 가진다.
- establish는 공간과 props가 읽힌다.
- beat/closeup은 감정 전달이 우선된다.

### AI artifact control

- 여전히 AI-generated 콘텐츠이지만 과도한 synthetic glamour 티가 줄어든다.
- airbrushed beauty still보다 `읽히는 만화 컷`에 더 가깝다.

## Out of Scope

이번 설계는 아래를 포함하지 않는다.

- 핵심 캐릭터 전체 일괄 마이그레이션
- publish automation
- full shot library redesign
- 새 teaser motion engine 교체
- 캐릭터 LoRA 학습 파이프라인 도입

## Recommendation

이번 프로젝트는 `기존 캐릭터를 전부 폐기`하는 방향이 아니라, 아래 순서로 가는 것이 맞다.

1. legacy freeze
2. Character Canon 2.0 / Series Style Canon / Binding 분리
3. Camila Duarte 파일럿
4. 파일럿 검증 통과 후 핵심 캐릭터 확장

즉 전략은 `full reset`이 아니라 `controlled migration`이다.

