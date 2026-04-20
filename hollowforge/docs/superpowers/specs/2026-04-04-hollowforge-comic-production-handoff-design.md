# HollowForge One-Shot Production Dry Run And Japanese Handoff Design

Date: 2026-04-04

## Goal

Phase 0 + Phase 1에서 만든 `Character OS Comic MVP`를 실제 상업 제작 직전 단계까지 밀어 올린다.

이번 단계의 목적은 세 가지다.

- HollowForge 안에서 `adult_nsfw one-shot` 1편을 실제 운영 플로우로 완주할 수 있는지 검증
- 결과물을 `일본식 출판 만화 원고 작업`으로 넘길 때 필요한 handoff 규격 고정
- 이후 `teaser animation`으로 이어질 수 있도록 panel/page lineage를 더 명확히 남김

이번 단계는 `새로운 제작 시스템`을 만드는 것이 아니라, 이미 구현된 Comic MVP를 `production-ready handoff surface`로 다듬는 단계다.

## Current State

현재 HollowForge는 이미 아래를 수행할 수 있다.

- approved Story Planner payload -> comic episode import
- scene/panel draft 생성
- panel별 still candidate queueing
- selected render asset 고정
- panel dialogue draft 생성
- page preview assembly
- ZIP handoff export
- teaser derivative용 manifest 출력

즉 핵심 lineage는 이미 존재한다.

`character -> character_version -> episode -> scene -> panel -> selected_render -> page -> teaser_handoff`

하지만 현재 결과물은 아직 `제작용 Asset OS MVP`에 가깝고, `일본식 원고 handoff package`로는 부족한 지점이 남아 있다.

## Problem Statement

지금 빠진 것은 품질보다 `운영 명세`다.

첫 번째 공백은 `실제 제작 드라이런`이다.

- 어떤 단계에서 사람이 개입해야 하는지
- 어디서 시간이 오래 걸리는지
- 어떤 산출물이 실제 후반 툴에서 필요한지

가 아직 구조적으로 기록되지 않는다.

두 번째 공백은 `일본식 원고 handoff contract`다.

- 현재 page preview는 존재하지만 manuscript profile이 없다
- export ZIP은 나오지만 후반 작업자가 바로 이해할 수 있는 handoff readme/checklist가 없다
- layout template과 print manuscript intent가 같은 개념으로 정리돼 있지 않다

세 번째 공백은 `다음 단계 연결 규칙`이다.

- teaser animation은 manifest 수준으로만 연결돼 있고
- 어떤 panel이 teaser 승격 후보인지 운영적으로 고정돼 있지 않다

## Considered Approaches

### 1. Dry Run Only

사람이 직접 1편을 만들어 보고 막히는 지점만 문서화한다.

장점:

- 구현 비용이 가장 낮다
- 바로 운영 감각을 얻을 수 있다

단점:

- 결과가 사람 기억과 메모에 의존한다
- handoff package 규격이 계속 흔들린다

### 2. Handoff-Centric Hardening

현재 Comic MVP에 `manuscript profile`, `production checklist`, `handoff readme`, `dry-run report` 계층을 추가한다.

장점:

- 실제 한 편 제작과 시스템 정리가 동시에 된다
- 일본식 후반 작업으로 넘기는 기준점이 생긴다
- 다음 teaser phase도 같은 asset identity를 재사용할 수 있다

단점:

- 문서와 export surface를 같이 손봐야 한다

### 3. Full Print Automation

HollowForge가 거의 완성 원고 수준의 print master를 직접 만들어 내도록 확장한다.

장점:

- 자동화 비중이 높다

단점:

- 지금 단계에서 과하다
- `.clip` 또는 상업 인쇄 최종물 자동 생성은 툴 제약과 운영 리스크가 크다
- 핵심 가치인 `character/panel lineage`보다 포맷 대응이 더 복잡해진다

## Recommended Direction

`2. Handoff-Centric Hardening`이 맞다.

이번 단계의 기준은 아래다.

- HollowForge는 `creative source of truth`
- CLIP STUDIO EX는 `manual finishing master`
- export package는 `일본식 원고 제작 입력물`
- teaser animation은 `선택 panel/scene의 derivative`

즉 이번 단계는 `자동 완성`이 아니라 `운영 가능한 정확한 handoff`를 만드는 단계다.

## Phase 1.5 Scope

## In Scope

### 1. Canonical Production Dry Run

한 개의 canonical one-shot을 정해서 아래를 실제로 완주한다.

- approved plan import
- all panel render selection
- dialogue pass
- page assembly
- handoff ZIP export
- 후반 작업 진입 체크

Phase 1.5에서 이 dry run은 `fresh import session inside /comic` 기준으로 정의한다.

- approved plan import 직후부터 export까지 한 세션 안에서 완주
- 현재 imported episode의 handoff readiness를 판단
- episode picker 또는 persisted episode reload는 이번 단계 범위 밖

즉 `/comic`은 이번 단계에서 `resume-any-episode console`이 아니라 `current in-session production workspace`다.

드라이런 산출물은 단순 성공/실패가 아니라 `production report`여야 한다.

최소 기록 항목:

- episode id
- character version id
- panel count / selected panel count
- page count
- 사용 layout template
- 사람이 직접 수정한 단계
- 막힌 지점
- 다음 수정 우선순위

### 2. Japanese Manuscript Handoff Profile

현재 `layout template`는 page preview 배치 중심이다. 여기에 `manuscript profile`을 분리해서 붙인다.

`layout template`가 의미하는 것:

- 패널 배치 방식
- 페이지 내 panel grouping

`manuscript profile`이 의미하는 것:

- 일본식 우철 방향
- trim / bleed / safe area intent
- monochrome print intent
- finishing tool target (`CLIP STUDIO EX`)
- export naming rules

초기에는 profile을 하나만 둔다.

- `jp_manga_rightbound_v1`

이 profile은 `일본식 우철 단행본/동인지용 handoff 기준`을 뜻한다. 정확한 세부 수치는 구현 시점에 CLIP STUDIO EX preset을 기준으로 고정한다.

이 profile의 persistence/API contract도 이번 단계에서 같이 고정한다.

- `comic_page_assemblies.manuscript_profile_id`에 저장
- assemble/export route는 `manuscript_profile_id`를 입력으로 받음
- assembly/export response는 같은 값을 반환
- `/comic`은 `Layout Template`과 분리된 `Manuscript Profile` 선택 surface를 가짐

### 3. Handoff Package V2

현재 export ZIP을 `후반 작업자에게 넘길 수 있는 묶음`으로 강화한다.

최소 포함물:

- page previews
- selected panel asset files
- dialogue manifest
- panel asset manifest
- page assembly manifest
- teaser handoff manifest
- manuscript profile manifest
- handoff readme
- production checklist snapshot

artifact location도 이번 단계에서 고정한다.

- episode handoff manifests: `data/comics/manifests/`
- page preview images: `data/comics/previews/`
- final handoff bundles: `data/comics/exports/`
- dry-run reports: `data/comics/reports/`

assembly/export response surface도 고정한다.

- `manuscript_profile`
- `manuscript_profile_manifest_path`
- `handoff_readme_path`
- `production_checklist_path`

핵심 원칙은 파일 수를 늘리는 것이 아니라 `받는 사람이 다음 행동을 헷갈리지 않게 하는 것`이다.

### 4. Comic Studio Operator Guidance

`/comic`은 지금도 lineage와 조립 흐름을 보여주지만, production handoff 기준 정보는 더 직접적으로 보여줘야 한다.

필요한 표면:

- 현재 episode의 handoff readiness
- selected render coverage
- chosen manuscript profile
- export package에 들어가는 항목 요약
- 후반 작업으로 넘길 때 해야 할 다음 단계

### 5. Teaser Continuity Preservation

Phase 2 애니 구현 자체는 이번 범위가 아니다. 하지만 현재 export와 report가 teaser 승격 후보를 잃지 않아야 한다.

따라서 이번 단계에서는:

- selected panel ids 유지
- page order 유지
- teaser handoff manifest 유지
- production report에서 teaser 후보 panel을 메모할 수 있게 유지

까지만 다룬다.

## Out Of Scope

- native `.clip` or `.cmc` file generation
- 완전 자동 말풍선 배치 완성
- 최종 인쇄용 입고 파일 직접 생성
- full teaser animation render pipeline
- publisher / storefront automation

## Design Details

## Source Of Truth

계속 동일하다.

- `characters` / `character_versions`
- `comic_episodes` / `comic_episode_scenes` / `comic_scene_panels`
- `comic_panel_dialogues`
- `comic_panel_render_assets`
- `comic_page_assemblies`

새로운 단계에서도 파일 경로가 아니라 `entity id`가 truth다.

## Export Contract

Handoff package는 아래 질문에 답할 수 있어야 한다.

- 어떤 episode인가
- 어떤 character version으로 만들었는가
- 어떤 panel asset들이 실제 선택됐는가
- page order는 무엇인가
- dialogue는 무엇인가
- 어떤 manuscript profile을 전제로 하는가
- 후반 작업자가 무엇부터 해야 하는가

그래서 export contract는 `render file bundle`이 아니라 `episode handoff bundle`이어야 한다.

새 artifact의 source-of-truth 규칙은 아래로 둔다.

- `manuscript_profile_id`는 DB row에 저장되는 structured truth
- `manuscript_profile_manifest`, `handoff_readme`, `production_checklist`는 export-time artifacts
- `production_report`는 local dry-run helper가 `data/comics/reports/`에 쓰는 operator artifact

즉 파일 경로 자체가 truth는 아니지만, 어떤 episode/layout/profile 조합에서 생성된 artifact인지는 ID와 응답 payload로 추적 가능해야 한다.

## Manual Finishing Position

이번 시스템은 CLIP STUDIO EX를 대체하지 않는다.

HollowForge의 역할:

- story/panel/render/dialogue/page lineage 고정
- 후반 작업 이전의 선택과 정리 자동화
- 후반 작업자가 바로 받을 수 있는 정돈된 bundle 제공

CLIP STUDIO EX의 역할:

- 최종 말풍선/텍스트 미세 조정
- 톤, 효과선, 재단 대응
- 실제 출판 원고 마스터 관리

즉 `HollowForge -> handoff package -> CLIP STUDIO EX`가 기본 흐름이다.

## Local Vs Server Boundary

이번 단계에서도 로컬 우선 원칙을 유지한다.

로컬:

- dry run execution
- export/handoff generation
- dialogue/page review

서버/원격 worker:

- existing remote worker surface는 이미 존재하지만 이번 Phase 1.5에서 변경하지 않음
- teaser derivative가 실제 animation render로 넘어갈 때만 다시 scope에 포함

즉 Phase 1.5는 `로컬 운영 신뢰도`를 높이는 단계다.

## Validation Criteria

이번 단계가 끝났다고 판단하려면 아래가 필요하다.

### Functional

- one canonical episode can be completed end-to-end in `/comic` during a fresh import session
- export ZIP contains manuscript profile + handoff readme
- every exported page is backed by selected materialized assets
- canonical production dry run must fail if synthetic placeholder fallback was used

### Operational

- operator can tell whether an episode is handoff-ready without reading raw JSON
- one dry-run report exists and records manual intervention points
- README/STATE/runbook docs explain how to repeat the flow

### Strategic

- export package preserves panel identity for later teaser derivative work
- no new duplicate character/story systems are introduced

## Risks

### Over-automating too early

후반 작업을 다 자동화하려고 하면 scope가 급격히 커진다.

Mitigation:

- CLIP STUDIO EX manual finish를 공식 위치로 유지
- HollowForge는 handoff 이전까지만 책임진다

### Handoff profile ambiguity

일본식 원고 규격이 문서상 모호하면 export package가 다시 흔들린다.

Mitigation:

- profile id를 하나로 시작
- exact preset source를 runbook에 고정

### Dry-run notes staying outside the system

사람이 메모만 남기고 구조화하지 않으면 다음 편에서 같은 문제를 반복한다.

Mitigation:

- production report template을 표준 산출물로 둔다

### Smoke success being confused with production success

현재 `launch_comic_mvp_smoke.py`는 contract/smoke 확인용이며, 로컬에서 synthetic placeholder fallback을 사용할 수 있다.

Mitigation:

- canonical production dry run은 별도 helper로 분리
- production dry run에서는 synthetic fallback을 허용하지 않는다
- materialized selected asset가 아니면 즉시 실패한다

## Implementation Boundary

이번 spec의 구현 범위는 `Phase 1.5 dry run + handoff hardening`까지다.

다음 Phase 2는 별도 구현으로 분리한다.

- `animation_shot` registry
- remote worker payload binding
- teaser render execution

이번 단계는 그 준비를 위한 export identity를 정리하는 것으로 충분하다.
