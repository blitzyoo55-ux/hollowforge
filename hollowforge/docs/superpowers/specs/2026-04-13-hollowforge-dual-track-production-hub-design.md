# HollowForge Dual-Track Production Hub Design

Date: 2026-04-13

## Goal

HollowForge를 `만화/애니 완성 툴`이 아니라 `스토리, 자산, 선택, 핸드오프를 관리하는 production hub`로 재정의한다.

이번 설계의 목표는 아래 네 가지다.

1. HollowForge의 책임을 `Story OS + Still Forge + Comic Handoff + Animation Handoff`로 고정한다.
2. 만화 최종 authoring은 `CLIP STUDIO`로, 애니 최종 마감은 외부 편집 툴로 분리한다.
3. 만화와 애니를 같은 출력으로 취급하지 않고, 공통 story/core 위에 `comic track`과 `animation track`을 병렬로 둔다.
4. `all_ages`와 `adult_nsfw`를 일부 기능 옵션이 아니라 전 단계 공통 축으로 올린다.

이 설계는 기능 추가보다 먼저 제품 경계를 바로잡는 단계다.

## Approved Decisions

- product role: `production hub`
- manga authoring target: `CLIP STUDIO`
- animation finish target: `external editing tool`
- architecture: `dual-track`
- animation generation assumption: `Seedance 2.0` 같은 외부 생성기에서 나온 clip을 조합하는 구조
- content modes: `all_ages | adult_nsfw`

## Current System Fit

현재 HollowForge는 이미 아래를 갖고 있다.

- story planner
- approved story import
- comic panel render queue
- selected render asset lineage
- dialogue draft
- page assembly preview and handoff export
- animation worker dispatch and callback
- teaser derivative path
- character canon v2 / series style canon / binding layer

즉 프로젝트는 백지 상태가 아니다.

하지만 현재 구조는 아래 세 역할이 한 workspace에 섞여 있다.

- still generation engine
- comic operator workspace
- teaser derivative workspace

그 결과 `/comic`은 `production hub surface`와 `authoring surface` 사이에서 애매한 상태가 되었다.

## Problem Statement

핵심 문제는 “기능이 많다”가 아니다.

핵심 문제는 `object boundary`가 흐리다는 점이다.

### 1. Comic object와 animation object가 분리되지 않았다

만화의 최소 단위는 `panel/page`다.

애니의 최소 단위는 `shot/clip`이다.

둘은 story, character, scene, style을 공유하지만 같은 출력 객체가 아니다.

지금 HollowForge는 selected panel -> teaser derivative를 먼저 붙이면서 둘의 차이를 충분히 명시하지 못했다.

### 2. Handoff와 authoring이 섞여 있다

현재 page assembly와 export는 강한 handoff 기능이다.

그러나 운영 맥락에서는 이것이 종종 “완성 원고에 가까운 출력”처럼 다뤄진다.

이 해석은 잘못이다.

HollowForge는 CLIP STUDIO 원고 편집을 대체하지 않는다.

### 3. Content mode가 일부 서브시스템에만 있다

현재는 sequence/animation 일부 registry와 dialogue 쪽에 `all_ages | adult_nsfw` 흔적이 있다.

하지만 story, still, comic export, animation handoff 전체에 일관된 1급 도메인 축으로 반영되어 있지 않다.

이 상태로 가면 나중에 safe lane과 adult lane을 단계별로 다시 쪼개며 큰 비용을 치르게 된다.

## Non-Goals

이번 단계에서 하지 않는 것:

- HollowForge 안에서 `.clip`을 직접 생성하는 것
- HollowForge 안에서 최종 대사/말풍선/SFX 레이아웃을 완성하는 것
- HollowForge 안에서 최종 애니 편집 타임라인을 제공하는 것
- 특정 NLE나 compositing 툴을 지금 당장 고정하는 것
- 기존 comic MVP와 teaser MVP를 폐기하는 것

## Considered Approaches

### 1. All-in-One Expansion

HollowForge 안에 story, still, page, dialogue, teaser, animation를 계속 넣는다.

장점:

- 한 제품 안에서 다 보인다

단점:

- 책임이 계속 섞인다
- image quality tuning과 page authoring 요구가 충돌한다
- animation shot logic가 comic panel logic에 끌려간다

권장하지 않는다.

### 2. Asset Factory Only

HollowForge를 거의 still/clip 생성 공장으로만 둔다.

장점:

- 단순하다
- 품질 실험에 집중하기 쉽다

단점:

- 당신이 원하는 `서사 중심 IP 생산 허브`가 되지 못한다
- story, episode, scene, lineage 가치가 약해진다

부족하다.

### 3. Dual-Track Production Hub

공통 story/core를 두고, 만화는 `comic track`, 애니는 `animation track`으로 분리한다.

장점:

- 현실적이다
- 책임이 선명하다
- CLIP STUDIO와 외부 편집 툴 handoff를 자연스럽게 지원한다
- 현재 HollowForge 구현 자산을 대부분 재사용할 수 있다

단점:

- 데이터 모델을 더 명확히 나눠야 한다
- 기존 teaser logic를 animation track으로 옮기는 정리가 필요하다

현재 목표에 가장 적합하다.

## Recommended Direction

권장 방향은 `Dual-Track Production Hub`다.

HollowForge의 최종 책임은 아래 네 모듈로 고정한다.

### 1. Story OS

공통 세계관과 서사 구조를 관리한다.

범위:

- work
- series
- episode
- scene
- beat grammar
- character canon
- series style
- content mode

### 2. Still Forge

만화와 애니가 공유하는 still asset 생산 계층이다.

범위:

- panel still generation
- shot anchor still generation
- expression pack
- location pack
- favorite-informed quality recipe
- identity/style binding

### 3. Comic Handoff

CLIP STUDIO authoring 입력물을 만든다.

범위:

- panel selection truth
- dialogue/SFX row manifest
- bubble safe zones
- frame/page layout guides
- manuscript profile
- CLIP STUDIO handoff package

### 4. Animation Handoff

외부 영상 편집 툴이 받을 shot package를 만든다.

범위:

- shot intent
- shot anchor still
- generated clip variants
- timing notes
- edit manifest
- tool-neutral export package

## System Boundary

### HollowForge owns

- story planning
- character and style canon
- still/clip generation orchestration
- candidate selection
- lineage
- quality gating
- export manifest generation
- production handoff packaging

### CLIP STUDIO owns

- final page composition
- panel border adjustments
- speech balloon placement
- dialogue typography
- SFX typography
- print/layout finishing

### External animation editor owns

- shot ordering and trimming
- transitions
- subtitle/SFX/music
- color finishing
- final render

## Data Model

## Shared Core

### `works`

최상위 IP 단위다.

필드 예시:

- id
- title
- format_family (`comic`, `animation`, `mixed`)
- default_content_mode
- status
- canon_notes

### `series`

작품 안의 연재/브랜드 단위다.

필드 예시:

- id
- work_id
- title
- delivery_mode (`oneshot`, `serial`, `anthology`)
- visual_identity_notes
- audience_mode

### `episodes`

만화와 애니가 공유하는 이야기 단위다.

필드 예시:

- id
- work_id
- series_id
- title
- synopsis
- content_mode
- target_outputs
- continuity_summary
- status

### `episode_scenes`

장면 단위다.

필드 예시:

- id
- episode_id
- scene_no
- location
- purpose
- continuity_notes
- emotional_state

### `characters`

- id
- work_id
- name
- codename
- archetype
- age_band
- default_content_mode

### `character_versions`

- id
- character_id
- version_code
- lane
- identity_anchor
- anti_drift_rules
- reference_manifest

### `series_style_canons`

작품/시리즈별 작화와 연출 톤을 정의한다.

### `content_mode`

모든 track과 export에 공통으로 붙는다.

- `all_ages`
- `adult_nsfw`

이 값은 story planner, still generation, dialogue draft, comic handoff, animation handoff 모두에 내려간다.

## Comic Track

### `scene_panels`

만화 패널 객체다.

필드 예시:

- id
- episode_scene_id
- panel_no
- panel_type
- reading_order
- framing
- action_intent
- dialogue_intent
- page_target_hint

### `panel_render_assets`

panel still 후보와 선택본이다.

### `panel_dialogues`

대사, 캡션, SFX를 저장한다.

필드 예시:

- type (`speech`, `thought`, `caption`, `sfx`)
- speaker
- text
- placement_hint
- balloon_style_hint

### `page_layout_guides`

실제 authoring이 아니라 handoff guide다.

필드 예시:

- episode_id
- layout_template_id
- manuscript_profile_id
- panel_order
- frame_guides
- safe_area_guides

### `comic_handoff_packages`

CLIP STUDIO 입력용 패키지다.

포함물:

- selected panel assets
- dialogue manifest
- SFX manifest
- page order manifest
- frame guide manifest
- manuscript profile manifest
- handoff readme

## Animation Track

### `scene_shots`

애니 샷 객체다.

필드 예시:

- id
- episode_scene_id
- shot_no
- shot_type
- camera_intent
- motion_intent
- duration_target_sec
- dialogue_reference

### `shot_anchor_assets`

애니 shot용 still anchor다.

panel still과 공유 asset을 참조할 수 있지만, 객체는 분리한다.

### `shot_clip_variants`

Seedance 등 생성기에서 나온 clip 후보다.

필드 예시:

- id
- scene_shot_id
- provider
- preset_id
- duration_sec
- storage_path
- quality_notes
- is_selected

### `animation_handoff_packages`

편집툴 중립 패키지다.

포함물:

- selected shot clips
- shot order manifest
- timing notes
- continuity notes
- subtitle reference
- contact sheet / preview reel

## What To Keep

- story planner and approved import
- selected render truth
- remote worker dispatch and callback contract
- character canon v2 / series style canon / binding stack
- page assembly manifest and export thinking
- animation worker split

## What To Refactor

### 1. `/comic`

`final manga maker`가 아니라 `comic handoff workspace`로 재정의한다.

UI 문구와 model naming도 여기에 맞춰 바꾼다.

### 2. Teaser ops

현재 teaser는 animation MVP의 일부가 아니라 `animation track preview surface`로 이름과 위치를 조정한다.

### 3. Dialogue generation

현재 adult profile 고정으로 보이는 부분을 제거하고 `content_mode`에 따라 provider profile을 고르게 바꾼다.

### 4. Page assembly

현재 preview/export 중심 구현은 유지하되, “완성 출력”이 아니라 “CLIP STUDIO handoff”라는 의미를 더 강하게 명시한다.

## What To Add

### Phase A. Production Hub Core

- `works`
- `series`
- episode-level `content_mode`
- shared naming and lineage rules

### Phase B. Comic Handoff V2

- clip studio handoff profile
- dialogue/SFX separation hardening
- frame guide manifest
- handoff readme standardization

### Phase C. Animation Handoff V1

- `scene_shots`
- `shot_anchor_assets`
- `shot_clip_variants`
- edit manifest export
- teaser logic -> animation handoff migration

### Phase D. Mode-Aware Routing

- safe/adult story planner profiles
- safe/adult still recipes
- safe/adult dialogue profiles
- safe/adult animation preset routing

## Delivery Strategy

실행 순서는 아래가 맞다.

1. `boundary first`
   기존 comic MVP와 teaser MVP의 목적을 문서와 UI 용어에서 먼저 바로잡는다.
2. `comic handoff hardening`
   CLIP STUDIO로 넘기는 입력 패키지 품질부터 올린다.
3. `animation handoff introduction`
   teaser 파생 로직을 shot package 중심 구조로 옮긴다.
4. `quality engine split`
   still generation을 `panel`용과 `shot anchor`용으로 분리한다.
5. `content-mode unification`
   safe/adult를 전 단계에서 일관되게 사용한다.

## Risks

### 1. Legacy terminology drift

기존 문서와 UI가 여전히 `/comic = 만화 완성기`, `teaser = 애니 파이프라인`처럼 읽힐 수 있다.

이건 설계보다 운영 혼선을 키운다.

### 2. Shot and panel duplication

scene_panels와 scene_shots를 너무 비슷하게 만들면 같은 문제를 다시 만든다.

둘은 공유 core를 가지되 출력 책임은 달라야 한다.

### 3. CLIP STUDIO dependence

최종 만화 authoring을 CLIP STUDIO로 잡았으므로, handoff package는 `.clip 직접 생성`보다 `규칙 있는 PSD/PNG/manifest 입력물`에 우선 초점을 둬야 한다.

### 4. Editor-neutral animation package ambiguity

최종 애니 편집툴이 아직 고정되지 않았으므로, 초기 animation handoff는 `JSON + CSV + media package` 중심으로 설계해야 한다.

## Verification

이 설계가 반영되면 아래가 가능해야 한다.

1. 하나의 episode가 comic track과 animation track을 동시에 가진다.
2. comic track은 CLIP STUDIO 입력 패키지를 안정적으로 만든다.
3. animation track은 Seedance 등에서 생성된 clip 후보를 편집툴 중립 패키지로 묶는다.
4. `all_ages`와 `adult_nsfw`가 story, still, dialogue, animation 전부에서 일관되게 적용된다.
5. teaser는 animation track의 일부로 읽히고, 더 이상 comic panel의 임시 파생물로만 남지 않는다.

## Immediate Next Step

다음 구현 단계는 `Production Hub Core + Comic/Animation dual-track domain plan`이다.

여기서 먼저 할 일은:

- 공통 core schema 정의
- comic track와 animation track의 책임 분리
- 기존 `/comic`과 teaser surfaces를 새 경계에 맞게 재명명
- Clip Studio handoff package와 animation handoff package의 최소 contract 정의

이 단계를 끝낸 뒤에야 still quality tuning이 구조적으로 의미를 갖는다.
