# HollowForge Character OS For Comic And Animation Design

Date: 2026-04-03

## Goal

HollowForge를 `랜덤 이미지 생성 콘솔`에서 `캐릭터 중심 성인 만화/애니 자산 운영 시스템`으로 확장한다.

첫 상업 목표는 `8~16패널 adult_nsfw 원샷 만화 1편`이다.

이 첫 작품이 성공하면 같은 자산 구조 위에서:

- episode 2 이상으로 이어지는 `연재형 화수 만화`
- 선택 panel 또는 scene을 이용한 `teaser animation`

으로 확장한다.

이번 설계의 핵심은 `Asset OS First`다. 즉 첫 작품을 빨리 만드는 것보다, 첫 작품을 만들면서 이후 연재와 애니 확장이 가능한 자산 구조를 먼저 고정한다.

## Approved Decisions

- strategy: `Asset OS First`
- system of record: `character`
- lane: `adult_nsfw`
- first commercial deliverable: `short one-shot manga`
- follow-up assumption: 반응이 좋으면 `serial manga`로 확장

## Current System Fit

HollowForge는 이미 아래 축을 갖고 있다.

- still generation
- prompt factory
- story planner
- sequence planning
- animation job orchestration
- remote animation worker split

현재 코드와 문서 기준으로 이미 `character / episode / shot` 방향의 전환 의도가 존재한다.

- `backend/app/services/story_planner_service.py`
  - story prompt를 받아 episode brief와 4-shot preview를 만든다
- `backend/app/routes/sequences.py`
  - sequence blueprint, run, shot, rough cut orchestration을 담당한다
- `backend/app/services/sequence_run_service.py`
  - shot candidate, animation job, clip lineage를 만든다
- `lab451-animation-worker/`
  - execution layer를 별도 worker로 분리한다
- `docs/LAB451_CHARACTER_SERIES_PIPELINE_20260312.md`
  - character IP + episode + shot 기반 운영 방향을 명시한다

즉 이 프로젝트는 백지 상태가 아니다. 다만 현재는 `shot-centric still/animation planning`이 중심이고, `panel/dialogue/page assembly/comic export` 계층이 비어 있다.

## Why Character OS First

세 가지 시작 전략 중 `Character OS First`를 선택한 이유는 아래와 같다.

### Comic-first thin layer만으로는 부족한 이유

단기적으로는 빠르지만, 2편 이상으로 가면 continuity, character version, panel lineage, dialogue reuse 규칙이 다시 필요해진다.

### Series-first heavy OS가 과한 이유

처음부터 volume, issue, arc, release cadence까지 고정하면 1편도 나오기 전에 운영 복잡도가 너무 커진다.

### Character OS first가 맞는 이유

- 원샷 만화 1편을 만들면서도 이후 연재 확장을 수용할 수 있다
- 현재 HollowForge의 Story Planner / Sequence / Animation Worker 축과 가장 자연스럽게 연결된다
- 캐릭터 드리프트, continuity, panel-to-animation handoff를 하나의 데이터 구조로 관리할 수 있다

## Product Direction

HollowForge는 `캐릭터 자산 운영 콘솔`이 된다.

핵심 흐름은 다음과 같다.

`Character -> Character Version -> Episode Draft -> Scene Beat -> Panel Pack -> Dialogue Pack -> Comic Page Export`

애니는 별도 제품이 아니라 같은 자산 구조의 파생 출력으로 둔다.

- selected panel 또는 selected scene 일부가 `animation_shot`으로 승격된다
- animation은 기존 remote worker contract 위에서 실행한다

즉 만화와 애니는 서로 다른 제작 시스템이 아니라, 같은 Character OS를 공유하는 두 개의 output surface다.

## Data Model

### Core entities

#### `characters`

최상위 truth다.

필드 예시:

- id
- name
- codename
- archetype
- worldline
- age_band
- status (`candidate`, `core`, `retired`)
- default_lane
- personality_core
- canon_notes

#### `character_versions`

같은 캐릭터의 운영 가능한 비주얼 버전이다.

필드 예시:

- id
- character_id
- version_code
- checkpoint
- workflow_lane
- content_mode
- canonical_prompt_anchor
- anti_drift_rules
- wardrobe_notes
- hair_notes
- body_notes
- negative_profile
- reference_set_manifest
- status

이 엔터티가 있어야 캐릭터는 고정하고 작화/레시피 운영만 분리할 수 있다.

#### `episodes`

현재는 `원샷 만화 1편 = episode 1개`로 둔다.

필드 예시:

- id
- character_id
- character_version_id
- title
- synopsis
- status (`draft`, `planned`, `in_production`, `released`)
- continuity_summary
- canon_delta
- target_output (`oneshot_manga`, `serial_episode`, `teaser_animation`)

향후 serial 확장 시에는 `series_id`를 optional로 추가한다.

#### `episode_scenes`

이야기의 beat 단위다. 현재 Story Planner의 결과를 가장 자연스럽게 수용한다.

필드 예시:

- id
- episode_id
- scene_no
- premise
- location_id or freeform_location
- tension
- reveal
- continuity_notes
- involved_character_ids

#### `scene_panels`

만화 제작의 핵심 신규 엔터티다.

필드 예시:

- id
- episode_scene_id
- panel_no
- panel_type
- framing
- camera_intent
- action_intent
- expression_intent
- dialogue_intent
- continuity_lock
- page_target_hint
- reading_order

#### `panel_dialogues`

대사와 텍스트 자산을 분리 저장한다.

필드 예시:

- id
- scene_panel_id
- type (`speech`, `thought`, `caption`, `sfx`)
- speaker_character_id
- text
- tone
- priority
- balloon_style_hint
- placement_hint

이 분리가 있어야:

- 대사 수정
- 번역
- 플랫폼별 재가공
- balloon layout 재시도

가 쉬워진다.

#### `panel_render_assets`

실제 이미지 후보와 선택본을 관리한다.

필드 예시:

- id
- scene_panel_id
- generation_id
- selected
- prompt_snapshot
- quality_score
- bubble_safe_zones
- crop_metadata
- render_notes

#### `page_assemblies`

panel들을 묶어 실제 원고 페이지를 만든다.

필드 예시:

- id
- episode_id
- page_no
- layout_template_id
- ordered_panel_ids
- export_state
- preview_path
- master_path
- export_manifest

#### `animation_shots`

같은 자산 구조의 파생 엔터티다.

필드 예시:

- id
- episode_id
- episode_scene_id
- scene_panel_id
- character_version_id
- motion_preset_id
- render_profile_id
- reference_images_manifest
- status
- selected_worker_backend

### Entity relationships

- `character -> character_versions`
- `character_version -> episodes`
- `episode -> episode_scenes`
- `episode_scene -> scene_panels`
- `scene_panel -> panel_dialogues`
- `scene_panel -> panel_render_assets`
- `scene_panel or episode_scene -> animation_shots`

## Integration With Existing HollowForge

이번 설계는 기존 Story Planner / Sequence를 버리지 않는다.

### Story Planner integration

현재 `Story Planner`는 deterministic preview planner 성격이 강하다. 이 결과를 아래로 브리지한다.

- story prompt -> episode draft
- generated shots -> scene drafts
- each shot -> panel seed candidates

초기에는 Story Planner를 완전히 새로 쓰지 않고 `episode_scenes` 초안 생성기로 재사용하는 편이 안전하다.

### Sequence integration

현재 `Sequence`는 shot, anchor candidate, clip, rough cut의 lineage를 가진다.

초기 Comic OS에서는:

- `episode_scene` 또는 `scene_panel`이 sequence handoff의 원천이 된다
- `animation_shots`는 기존 animation job contract를 감싼 comic-side registry 역할을 한다

즉 big-bang replacement 대신 `comic-side bridge layer`를 추가한다.

## Local Vs Server Boundary

## What can stay local now

### Fully local

- Character OS and metadata storage
- episode/scene/panel/dialogue planning
- adult_nsfw story and dialogue drafting through local LLM
- still generation through HollowForge + ComfyUI
- panel review and selection
- first-pass page assembly
- one-shot export (`png`, `pdf`, `zip`)

### Local-first but may get heavy

- batch panel rerender
- balloon-safe zone extraction
- page layout template variations
- continuity checking across longer works

## What should move to server

- production-grade animation rendering
- multi-shot concurrent processing
- long mp4 encoding and retry handling
- output storage and callback reliability
- later publisher execution

## Boundary rule

- `HollowForge local = creative source of truth`
- `remote worker = heavy execution`
- `shared truth = character_id / character_version_id / episode_id / scene_panel_id`

This keeps comic and animation connected by asset identity rather than by ad-hoc file paths.

## Phase Plan

## Phase 0: Operating Foundation

목표는 제작 전에 운영 기반을 정리하는 것이다.

### Scope

- Character OS design fixed in docs
- Story Planner / Sequence / Publishing connection points documented
- adult_nsfw operating rules fixed
- GitNexus health reviewed

### GitNexus note

현재 로컬에서 `gitnexus analyze`는 `gitnexus-shared` package missing 에러로 실패했다.

따라서 본 프로젝트를 `GitNexus 기반 운영`으로 가져가려면 Phase 0에서 아래 둘 중 하나가 필요하다.

- GitNexus runtime 복구
- 대체 코드 인덱싱/검색 경로를 임시 운영 표준으로 문서화

## Phase 1: Comic MVP

첫 목표는 `8~16 panel adult_nsfw one-shot manga`.

### Scope

- Character OS schema
- Story Planner -> episode/scene/panel draft bridge
- panel still generation and selection
- dialogue/sfx generation and storage
- page assembly and export

### Outcome

- character 1명 기준 one-shot manga 1편 완성
- panel lineage 저장
- dialogue assets 분리 저장
- page export 가능

## Phase 1.5: Comic Ops Hardening

목표는 반복 제작 가능성 확보다.

### Scope

- bubble-safe zone handling
- page layout template set
- continuity checks
- panel lineage UX
- faster revision loop

## Phase 2: Animation Derivative

목표는 원샷 자산 일부를 teaser animation으로 전환하는 것이다.

### Scope

- `animation_shots` introduced as comic derivative entity
- payload expands to include:
  - `character_version_id`
  - `episode_id`
  - `scene_panel_id`
  - `reference_images[]`
  - `motion_preset_id`
  - `render_profile_id`
- local preview remains contract validation only
- production render moves to remote worker

## Tooling Recommendation

## Korean webtoon PSD files

한국 웹툰 PSD는 `일본 출판 만화 구조 설계`의 핵심 참고자료로는 우선순위가 낮다.

쓸 수 있는 범위:

- layer naming ideas
- edit workflow feel
- speech bubble / text / bg separation reference

핵심 참고자료로는 부적합한 이유:

- scroll-native reading rhythm
- RGB / web delivery orientation
- page turn and spread grammar mismatch
- print margin / bleed / trim orientation mismatch

## Japanese manga production master format

우선순위는 `PSD`가 아니라 `Japanese print manga structure`다.

권장 마스터 포맷:

- `CLIP STUDIO EX` based multi-page manuscript
- working master: `.cmc + .clip`
- interchange: `.psd` only when needed

## Tool stack recommendation

### No-spend validation stack

- HollowForge
- ComfyUI
- local LLM
- minimal free editor tools
- repo-side page assembly/export

용도: Asset OS와 one-shot pipeline 검증

### Recommended low-cost start

- HollowForge for asset orchestration
- CLIP STUDIO PAINT EX as master manga tool
- ComfyUI for still generation
- local LLM for dialogue draft

판단:

- Photoshop-first is not recommended
- CLIP STUDIO EX is the better master tool for Japanese print manga workflows

## Risks

### Character drift

panel마다 얼굴, 헤어, 체형, 의상이 흔들릴 수 있다.

Mitigation:

- strong `character_versions`
- reference set snapshots
- anti-drift rules stored per version

### Comic assembly bottleneck

image generation은 되는데 balloon, text, layout에서 사람 손이 과도하게 들어갈 수 있다.

Mitigation:

- V1 is semi-auto, not full-auto
- AI drafts, human approves final bubble placement and wording

### Serial continuity collapse

원샷 이후 2편부터 continuity가 무너질 수 있다.

Mitigation:

- continuity notes per episode
- canon delta tracking
- forbidden drift memory

### Animation payload migration risk

현재 generation-centric payload를 comic-centric asset payload로 옮길 때 계약이 깨질 수 있다.

Mitigation:

- preserve current worker contract
- add comic asset identifiers incrementally

### Tooling instability

GitNexus currently fails locally.

Mitigation:

- treat GitNexus health as Phase 0 item

## Validation Strategy

### Functional validation

- one character
- one one-shot
- 8 to 16 panels
- every panel linked to character version
- dialogues stored separately
- one export produced end-to-end

### Operational validation

- record where human intervention was needed
- identify whether the slowest step is:
  - image quality
  - dialogue quality
  - page assembly

### Animation validation

- promote 1 or 2 selected panels to teaser animation candidates
- validate locally with preview lane only
- treat remote worker as production path

## Success Criteria

The first success state is not “full AI animation production”.

The first success state is:

- an adult_nsfw one-shot manga is completed
- it uses a character-centric asset system
- each panel has lineage to character/version/episode/scene
- dialogue and sfx are stored as reusable assets
- pages can be exported
- selected panels can be promoted into animation candidates
- episode 2 can be added without redesigning the asset model

## Recommended Next Step

After this design is accepted:

1. create an implementation plan for `Phase 0 + Phase 1`
2. keep scope bounded to `one character / one one-shot / one teaser derivative`
3. do not begin with serial publishing or full animation production

## References

- `STATE.md`
- `ROADMAP.md`
- `docs/LAB451_EXECUTION_ROADMAP_20260310.md`
- `docs/LAB451_CONTENT_PIPELINE_PLAN_20260310.md`
- `docs/LAB451_CHARACTER_SERIES_PIPELINE_20260312.md`
- `docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`
