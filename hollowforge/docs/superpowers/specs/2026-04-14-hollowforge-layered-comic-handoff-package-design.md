# HollowForge Layered Comic Handoff Package Design

Date: 2026-04-14

## Goal

`/comic`의 현재 Japanese handoff export를 “page preview ZIP” 수준에서 멈추지 않고,
CLIP STUDIO EX finishing을 위한 `layered handoff package`로 끌어올린다.

이번 설계의 목표는 아래 다섯 가지다.

1. HollowForge를 comic production의 `source of truth`로 유지한다.
2. CLIP STUDIO EX를 `first-class finishing target`으로 취급한다.
3. handoff package의 우선순위를 `컷/페이지 구조 정확도 -> 텍스트 anchor 정확도 -> 텍스트 의미 정확도` 순으로 고정한다.
4. export 전에 `/comic` 내부에서 geometry와 text anchor를 검수할 수 있게 한다.
5. 현재의 `assemble/export` 계약을 깨지 않고, 더 정밀한 layered package로 확장한다.

핵심은 “CSP에 바로 넘길 수 있는 패키지”를 만드는 것이지, HollowForge 안에 최종 만화 편집기를 새로 만드는 것이 아니다.

## Approved Decisions

- strategy: `혼합형 2 > 1`
- operational principle: `HollowForge source of truth, CLIP STUDIO EX finishing target`
- primary success metric: `정확도`
- priority order: `컷/페이지 구조 정확도 -> 텍스트 배치 정확도 -> 텍스트 의미 정확도`
- package direction: `layered handoff package`
- text payload: `editable draft text`
- initial review capability: `검수 전용 overlay + export gate`
- deferred capability: `anchor 위치 수동 수정 UI`
- backward compatibility rule: `strictly additive`

## Current System Fit

현재 HollowForge는 이미 comic handoff의 기초를 갖고 있다.

- `/comic`에서 story import, panel render selection, dialogue drafting, page assembly, handoff ZIP export가 가능하다.
- `ComicManuscriptProfileResponse`는 이미 `finishing_tool=clip_studio_ex`, `print_intent=japanese_manga`를 명시한다.
- `assemble_episode_pages()`와 `export_episode_pages()`는 아래 artifact를 이미 만든다.
  - page preview
  - dialogue JSON
  - panel asset manifest
  - page assembly manifest
  - teaser handoff manifest
  - manuscript profile manifest
  - handoff readme
  - production checklist

즉 handoff의 뼈대는 이미 있다.

부족한 부분은 세 가지다.

1. export artifact가 `page-centered layered package`로 정리되지 않았다.
2. geometry와 text anchor를 export 전에 검수하는 명시적 단계가 없다.
3. CSP finishing 관점에서 필요한 `frame / balloon / text draft` 레이어 계약이 아직 없다.

이번 슬라이스는 이 공백만 메운다. panel render, dialogue generation, teaser derivation 같은 기존 생산 경로는 유지한다.

## Backward Compatibility Rule

이번 슬라이스는 `strictly additive`로 구현한다.

유지해야 하는 기존 계약:

- `ComicPageAssemblyBatchResponse` / `ComicPageExportResponse`의 기존 field
- 기존 artifact path field
  - `export_manifest_path`
  - `dialogue_json_path`
  - `panel_asset_manifest_path`
  - `page_assembly_manifest_path`
  - `teaser_handoff_manifest_path`
  - `manuscript_profile_manifest_path`
  - `handoff_readme_path`
  - `production_checklist_path`
- 기존 ZIP 안의 legacy manifest artifact path와 filename

이번 슬라이스에서 추가되는 것:

- root `manifest.json`
- `handoff_validation.json`
- `pages/<page>/...` subtree
- `panels/<panel>/...` subtree
- 신규 layered package field가 필요하면 `추가`만 허용

즉 v1.5에서는:

- 기존 field rename/remove 금지
- 기존 artifact filename/path change 금지
- 새 package contract는 additive-only

새 layered package가 canonical entrypoint가 되더라도, 기존 response field와 legacy manifest artifact는 병행 유지한다.

## Problem Statement

현재 export는 운영 proof로는 충분하지만, 사람 편집 공정으로 넘기기에는 아직 느슨하다.

### 1. Package는 존재하지만 레이어 계약이 없다

현재 ZIP에는 preview와 manifest가 들어가지만, 편집자가 바로 이해할 수 있는 `art layer / frame layer / balloon layer / text draft layer` 분리가 없다.

### 2. Page truth가 부족하다

현재 HollowForge 내부 진실은 여전히 panel 중심이다. 그러나 CSP finishing 단계의 진실은 page다. 이 전환 계층이 약하면 편집자가 page 구조를 다시 구성해야 한다.

### 3. Export gate가 너무 넓다

현재는 selected render completeness 중심으로 assemble/export가 열린다. 하지만 정확도 우선 목표라면 geometry, reading order, anchor mapping도 gate에 포함돼야 한다.

### 4. 사람 친화 출력과 기계 친화 출력이 분리돼 있지 않다

현재 artifact는 mostly machine-friendly JSON과 preview 묶음이다. 앞으로는:

- editor-friendly `handoff_readme`
- machine-friendly `handoff_validation.json`

둘 다 필요하다.

## Non-Goals

이번 슬라이스에서 하지 않는 것:

- `.clip` 파일을 직접 생성하는 것
- CLIP STUDIO 전용 import plugin 작성
- anchor/bubble/text의 자유 배치 편집기를 `/comic`에 넣는 것
- final lettering, kerning, font packaging, Japanese SFX style authoring
- panel crop나 selected render를 export 단계에서 다시 생성하는 것
- animation timeline authoring과의 통합 편집

이번 목표는 `정밀 handoff contract`를 고정하는 것이지, `최종 authoring surface`를 완성하는 것이 아니다.

## Considered Approaches

### 1. Manifest-First

현재 export artifact를 조금 더 늘리고, geometry는 JSON으로만 추가한다.

장점:

- 구현이 가장 빠르다
- 현재 contract 위에 얇게 붙일 수 있다

단점:

- CSP 편집 시작 속도가 낮다
- 사람이 다시 레이어 의미를 해석해야 한다
- 정확도 우선 목표에 비해 약하다

부족하다.

### 2. Layered Handoff Package

현재 assemble/export를 유지하되, episode export를 `page-centric layered package`로 승격한다.

장점:

- HollowForge를 source of truth로 유지할 수 있다
- CSP 편집자에게 바로 쓸 수 있는 정리된 package를 준다
- geometry, text anchor, text draft를 별도 레이어로 고정할 수 있다

단점:

- 현재 manifest 구조를 재편해야 한다
- UI에 `Handoff Review` 개념이 추가된다

현재 목표에 가장 적합하다.

### 3. CSP-Native Early

처음부터 CSP import를 직접 겨냥한 asset layout을 강하게 설계한다.

장점:

- finishing 진입은 가장 빠를 수 있다

단점:

- HollowForge 내부 계약이 먼저 흔들린다
- export validation보다 특정 external tool 형식에 종속된다
- automation과 dry-run 관점에서 경직된다

지금 단계에서는 이르다.

## Recommended Direction

권장 방향은 `Layered Handoff Package`다.

원칙은 단순하다.

- 내부 생산 단위는 `panel`
- 외부 편집 단위는 `page`
- export 순간에 `panel truth -> page-centric handoff package`로 변환한다

즉, HollowForge는 “컷을 만든 뒤 페이지로 묶고, 그 페이지를 편집자에게 넘기는 공장” 역할을 한다.

## Package Contract

episode export는 하나의 ZIP을 만든다.

```text
episode_<episode_id>_handoff.zip
  manifest.json
  handoff_readme.md
  handoff_validation.json
  manuscript_profile.json
  pages/
    page_001/
      page_preview.png
      page_manifest.json
      frame_layer.json
      balloon_layer.json
      text_draft_layer.json
    page_002/
      ...
  panels/
    panel_<panel_id>/
      selected_render.png
      panel_manifest.json
  reports/
    production_checklist.json
```

현재 존재하는 manifest artifact는 완전히 없애지 않는다. v1.5에서는 위 구조를 새로 추가하고, 기존 manifest artifact는 그대로 병행 유지한다.

### Root `manifest.json`

패키지 전체 인덱스다.

필수 필드:

- `package_version`
- `episode_id`
- `work_id`
- `series_id`
- `content_mode`
- `layout_template_id`
- `manuscript_profile`
- `page_count`
- `panel_count`
- `pages[]`
- `panels[]`
- `exported_at`
- `source_lineage`
- `warnings[]`

top-level shape는 아래처럼 고정한다.

```json
{
  "package_version": "1.5",
  "episode_id": "ep_123",
  "work_id": "work_1",
  "series_id": "series_1",
  "content_mode": "all_ages",
  "layout_template_id": "jp_2x2_v1",
  "manuscript_profile": {},
  "page_count": 2,
  "panel_count": 8,
  "pages": [],
  "panels": [],
  "warnings": [],
  "source_lineage": {},
  "exported_at": "2026-04-14T00:00:00+00:00"
}
```

### `pages/<page>/page_manifest.json`

page 단위 canonical summary다.

필수 필드:

- `page_id`
- `page_no`
- `canvas_size`
- `reading_direction`
- `trim_box`
- `bleed_box`
- `safe_box`
- `panel_order[]`
- `layer_files`
- `status`

top-level shape:

```json
{
  "episode_id": "ep_123",
  "page_id": "page_001",
  "page_no": 1,
  "status": "complete",
  "canvas_size": {"width": 0, "height": 0},
  "reading_direction": "right_to_left",
  "trim_box": {},
  "bleed_box": {},
  "safe_box": {},
  "panel_order": [],
  "layer_files": {
    "frame_layer": "pages/page_001/frame_layer.json",
    "balloon_layer": "pages/page_001/balloon_layer.json",
    "text_draft_layer": "pages/page_001/text_draft_layer.json"
  }
}
```

`page_manifest.json`은 page summary이며, layer file 자체는 각각 `items[]`를 가진 독립 파일이다.

`status` enum은 아래만 허용한다.

- `complete`
- `warning`
- `blocked`

### Art Layer

이번 설계에서 visual source layer의 공식 명칭은 `art layer`다.

`art layer`는 새 JSON file이 아니라 아래 asset 조합으로 정의한다.

- `pages/<page>/page_preview.png`
- `panels/<panel>/selected_render.png`
- `panels/<panel>/panel_manifest.json`

즉 art layer는 “선택된 panel render와 page preview가 실제로 존재하는 상태”를 뜻한다.

readiness 기준:

- page별 preview 존재
- panel별 selected render 존재
- panel manifest가 selected render lineage를 가리킴

`page layer`라는 용어는 쓰지 않는다. page는 layer가 아니라 package 단위다.

### `frame_layer.json`

이 파일이 `컷/페이지 구조 정확도`의 정답이다.

필수 필드:

- `panel_id`
- `scene_no`
- `panel_no`
- `reading_order`
- `frame_rect`
- `frame_shape_hint`
- `source_render_asset_id`
- `source_generation_id`

top-level shape:

```json
{
  "episode_id": "ep_123",
  "page_id": "page_001",
  "page_no": 1,
  "layer": "frame",
  "status": "complete",
  "items": []
}
```

`items[]`의 각 entry가 위 필수 field를 가진다. page당 frame item cardinality는 `1..N`이다.

layer `status` enum은 아래만 허용한다.

- `complete`
- `warning`
- `blocked`

### `balloon_layer.json`

이 파일이 `텍스트 배치 정확도`의 기준점이다.

필수 필드:

- `anchor_id`
- `panel_id`
- `type`: `speech | thought | caption | sfx`
- `anchor_rect`
- `tail_target_hint`
- `priority`
- `z_index`
- `safe_area_violation`

top-level shape:

```json
{
  "episode_id": "ep_123",
  "page_id": "page_001",
  "page_no": 1,
  "layer": "balloon",
  "status": "complete",
  "items": []
}
```

`items[]`의 각 entry가 위 필수 field를 가진다. page당 balloon item cardinality는 `0..N`이다.

### `text_draft_layer.json`

편집 가능한 문안 초안이다.

필수 필드:

- `anchor_id`
- `speaker`
- `type`
- `draft_text`
- `locale`
- `rewrite_status`
- `style_hint`

top-level shape:

```json
{
  "episode_id": "ep_123",
  "page_id": "page_001",
  "page_no": 1,
  "layer": "text_draft",
  "status": "complete",
  "items": []
}
```

`items[]`의 각 entry가 위 필수 field를 가진다. page당 text draft item cardinality는 `0..N`이다.

### `panels/<panel>/panel_manifest.json`

panel 원본 lineage용이다.

필수 필드:

- `panel_id`
- `page_no`
- `scene_no`
- `panel_no`
- `selected_render_asset_id`
- `selected_render_generation_id`
- `selected_render_path`
- `crop_notes`

top-level shape:

```json
{
  "episode_id": "ep_123",
  "panel_id": "panel_001",
  "page_no": 1,
  "scene_no": 1,
  "panel_no": 1,
  "selected_render_asset_id": "asset_1",
  "selected_render_generation_id": "gen_1",
  "selected_render_path": "panels/panel_001/selected_render.png",
  "crop_notes": null
}
```

## Layer Semantics

이번 설계의 핵심은 레이어 의미를 export contract에 명시하는 것이다.

- `art layer`
  - selected render와 page 내 배치 정보
- `frame layer`
  - 컷 경계, 읽는 순서, geometry
- `balloon layer`
  - 말풍선/SFX/caption 위치와 타입
- `text draft layer`
  - editable draft text

HollowForge는 이 네 레이어가 모두 준비됐을 때만 “정밀 handoff package”를 만들었다고 본다.

## UI Structure

`/comic`은 여전히 comic authoring 화면이 아니라 `Comic Handoff` 화면으로 유지한다. 다만 내부 관점을 세 개로 분리한다.

### 1. `Panels`

기존 panel render selection, dialogue generation, selected asset lineage 중심.

### 2. `Pages`

page assembly 결과와 page readiness 중심.

여기서는 아래를 보여준다.

- page preview
- page별 panel order
- layout template
- manuscript profile
- page readiness summary

### 3. `Handoff`

export 직전 검수와 package summary 중심.

여기서는 아래를 보여준다.

- art layer readiness
- frame layer readiness
- balloon/text draft readiness
- validation summary
- hard block / soft warning
- latest export summary

핵심은 `Assemble Pages -> Export Handoff ZIP` 사이에 명시적 `Handoff Review` 단계가 생긴다는 점이다.

## Operator Flow

### 1. Panel readiness

- episode import 완료
- 모든 panel에 selected render 존재

### 2. Page assembly

- layout template 선택
- manuscript profile 선택
- `Assemble Pages`

### 3. Handoff review

- page preview 확인
- frame geometry 확인
- balloon/text anchor completeness 확인
- editable draft text 확인

### 4. Export

- hard block이 없으면 `Export Handoff ZIP`
- latest export summary를 바로 확인

## Validation Rules

정확도 우선이므로 `hard block`과 `soft warning`을 구분한다.

### Hard Block

아래 조건 중 하나라도 있으면 export를 막는다.

- selected render 없는 panel 존재
- page geometry 누락
- reading order 충돌 또는 누락
- balloon/text anchor가 panel에 매핑되지 않음
- draft text가 anchor 없이 떠 있음
- manuscript profile 누락
- root manifest 또는 layer file 생성 실패

### Soft Warning

아래 조건은 export를 허용하되 warning으로 남긴다.

- speech balloon 밀도 과다
- SFX anchor가 safe area를 침범
- draft text 길이가 anchor에 비해 과도함
- panel crop가 너무 타이트해서 말풍선 여유가 부족함
- 한 page의 anchor 밀도가 manuscript safe area 대비 과도함

## Export Gate

`Export Handoff ZIP`은 아래 조건을 모두 만족할 때만 활성화한다.

- selected render completeness = complete
- page assembly exists
- art layer readiness = complete
- frame layer readiness = complete
- balloon layer readiness = complete
- text draft readiness = complete
- hard block count = 0

`warning count > 0`은 export를 막지 않는다. 다만 summary와 ZIP 안의 validation artifact에 반드시 남긴다.

## Output Artifacts

이번 슬라이스에서 새 canonical output은 두 개다.

### `handoff_validation.json`

machine-friendly validation summary.

필수 필드:

- `episode_id`
- `hard_blocks[]`
- `soft_warnings[]`
- `page_summaries[]`
- `generated_at`

top-level shape:

```json
{
  "episode_id": "ep_123",
  "hard_blocks": [],
  "soft_warnings": [],
  "page_summaries": [],
  "generated_at": "2026-04-14T00:00:00+00:00"
}
```

`page_summaries[]` entry shape:

```json
{
  "page_id": "page_001",
  "page_no": 1,
  "art_layer_status": "complete",
  "frame_layer_status": "complete",
  "balloon_layer_status": "warning",
  "text_draft_layer_status": "complete",
  "hard_block_count": 0,
  "soft_warning_count": 1
}
```

### `handoff_readme.md`

editor-friendly export summary.

최소 포함 항목:

- episode / work / series 정보
- manuscript profile
- page 수 / panel 수
- hard block 없음 확인
- 남은 soft warning
- 편집자가 먼저 손볼 page / anchor 목록

`latest export summary`는 frontend에서 아래 필드를 기준으로 보여준다.

- `export_zip_path`
- `manifest_path`
- `handoff_validation_path`
- `page_count`
- `hard_block_count`
- `soft_warning_count`
- `exported_at`

## Error Handling

### Assembly-Level Errors

- page split 실패
- selected render materialization path 누락
- manuscript profile 해석 실패

이 경우 `Assemble Pages` 자체가 실패한다.

### Review-Level Errors

- frame layer 생성 불가
- balloon/text draft mapping 불가

이 경우 assemble는 성공할 수 있지만, handoff readiness는 `blocked`가 된다.

### Export-Level Errors

- ZIP packaging 실패
- root manifest write 실패
- artifact path collision

이 경우 export response는 실패하고, UI는 이전 successful export summary를 유지해야 한다.

## Testing Strategy

### Backend

- layer manifest schema contract test
- handoff validation artifact generation test
- export ZIP content test
- hard block vs soft warning 분기 test
- current assembly/export regression test

### Frontend

- `Pages` readiness surface test
- `Handoff` tab validation summary test
- hard block 시 export disabled test
- warning only 시 export allowed test
- latest export summary rendering test

### Smoke

현재의 `launch_comic_production_dry_run.py`와 `launch_comic_remote_one_shot_dry_run.py`는 유지하되, 최종 성공 기준에 아래를 추가한다.

- layered artifact files 존재
- handoff validation artifact 존재
- export ZIP 안에 `pages/...` subtree와 `art/frame/balloon/text_draft` 관련 file 포함

## Rollout Shape

이 슬라이스는 2단계로 구현한다.

### Phase A

- backend layered artifact contract
- validation artifact
- existing export ZIP 구조 확장

### Phase B

- `/comic`의 `Pages` / `Handoff` surface
- export gate and latest export summary

수동 anchor edit는 다음 슬라이스로 미룬다. 이번 단계에서는 `검수와 차단 규칙`만 고정한다.

## Why This Design

이 설계는 두 가지를 동시에 만족한다.

1. HollowForge는 자동화 가능한 production engine으로 남는다.
2. 사람 편집자는 CSP에서 바로 finishing을 시작할 수 있다.

즉, `HollowForge 내부 생산성`과 `CLIP STUDIO 외부 마감 품질`을 충돌시키지 않는다.
