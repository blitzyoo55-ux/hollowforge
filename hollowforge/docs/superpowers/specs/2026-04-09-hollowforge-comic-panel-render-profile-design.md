# HollowForge Comic Panel Render Profile Design

Date: 2026-04-09

## Goal

현재 HollowForge의 `favorite-informed canonical still recipe`를 그대로 comic panel generation에 재사용하는 구조를 분리한다.

이번 단계의 목표는 세 가지다.

- `identity-friendly still recipe`와 `storytelling-friendly comic panel recipe`를 분리한다
- `establish / beat / insert / closeup` 패널 역할마다 다른 생성 프로필을 적용한다
- 결과적으로 `AI 티가 과도하게 나는 glamour portrait 반복`을 줄이고, `사람이 읽을 만한 만화 컷 흐름`을 만든다

이번 설계는 “AI 티를 완전히 숨긴다”가 목적이 아니다.
목표는 `AI 생성임을 느낄 수는 있지만, 몰입을 깨지 않을 정도로 정돈된 만화/티저 품질`이다.

## Current State

현재 stable runtime 기준으로 comic pipeline은 실제로 동작한다.

- story import
- remote still render
- selected render selection
- dialogue
- page assembly
- Japanese handoff ZIP export
- selected render 기준 teaser mp4 파생

그러나 직접 검수한 결과, `storytelling quality`는 아직 충분하지 않다.

대표 문제:

- 4컷이 거의 같은 얼굴/같은 구도로 반복된다
- establish panel도 `environment read`가 아니라 `glamour portrait`로 수렴한다
- AI 특유의 `copy-paste face`, `airbrushed skin`, `dead-eyed beauty shot` 인상이 강하다

즉 현재 시스템은 `좋아 보이는 still`은 만들지만,
`읽히는 comic panel sequence`는 충분히 만들지 못한다.

## Evidence

### Local product evidence

- current preview:
  - `data/comics/previews/61cdb8e2-a3b9-4f9b-b73d-26eaabb6a2ce_jp_2x2_v1_page_01.png`
- current establish candidates:
  - `data/outputs/573f7c0c-d1a7-468d-8294-c6881babe443.png`
  - `data/outputs/f22003df-922a-4360-bb0d-3c5443a499b3.png`

직접 확인한 결과:

- 컷 역할은 분화됐지만 실제 이미지 결과는 여전히 `portrait bias`가 강하다
- prompt 구조 개선만으로는 establish / insert를 충분히 분리하지 못한다
- 따라서 병목은 `prompt wording only`가 아니라 `render recipe selection`이다

### HollowForge internal evidence

현재 canonical still lock은 favorite priors와 animation-safe 운영을 기준으로 잠겨 있다.

- `Camila Duarte -> combo_a`
- `combo_a = prefectIllustriousXL_v70 + DetailedEyes_V3 + Face_Enhancer_Illustrious`

문제는 이 조합이 `still attractiveness`에는 강하지만,
comic panel 전체에 동일하게 쓰면 `glamour still overfit`이 발생한다는 점이다.

즉 현재 recipe는 틀린 것이 아니라,
`적용 대상이 잘못 넓어져 있다`.

## External Signals

최근 사례로 사용자가 언급한
`妻よ、僕の恋人になってくれませんか？`
를 참고했다.

공개적으로 확인 가능한 팩트:

- Comic Cmoa 작품 페이지는 `생성AI 사용`을 명시한다
- 2026-04-09 기준 작품 페이지에는 `3.7 / 453 reviews`, `青年マンガ 2位`, `先行作品 1位`로 표시된다
- 즉 `AI 사용 공개 + 상업적 클릭/판매`는 동시에 가능하다

공식/공개 반응에서 읽히는 신호:

- 긍정:
  - 히로인 매력
  - 관계성 공감
  - 보기 쉬운 컬러/광 연출
- 부정:
  - 반복된 얼굴과 컷
  - AI 티가 강한 표정/연기
  - 설명적인 전개

STUDIO ZOON의 공식 인터뷰에서 읽히는 원칙:

- 일본 만화 문법을 중시한다
- 플랫폼 기대치에 맞추되, 개성과 임팩트를 잃지 않으려 한다
- 읽히는 작품을 위해 편집 강도를 높게 가져간다
- 제작 체계를 내제화해 작품별 적합한 완성도를 추구한다

HollowForge에 적용할 수 있는 해석:

- AI 여부 자체보다 `읽히는 편집과 컷 설계`가 더 중요하다
- 하나의 예쁜 모델/LoRA 조합으로 모든 컷을 밀어붙이면 상업적 거부 포인트가 커진다
- 작품이 먹히는 핵심은 `캐릭터 매력`과 `관계성`이지만,
  이 둘을 살리려면 `패널 역할별 연출 차이`가 선행되어야 한다

## Problem Statement

현재 HollowForge comic render lane의 근본 문제는 아래 네 가지다.

1. `favorite still recipe`와 `comic panel recipe`가 분리되어 있지 않다
2. `panel_type`이 prompt에는 반영되지만 `checkpoint / LoRA / aspect / negative`에는 반영되지 않는다
3. establish / insert에도 portrait-bias enhancer가 들어간다
4. 패널 역할별 기대 결과물이 시스템적으로 고정되어 있지 않다

이 상태에서는 프롬프트를 아무리 다듬어도,
모델이 가장 잘하는 `high-response beauty still`로 계속 회귀한다.

## Considered Approaches

### 1. Prompt Tuning Only

지금 구조를 유지하고 prompt wording만 더 세게 손본다.

장점:

- 구현 비용이 가장 작다
- migration이 필요 없다

단점:

- 이미 한계가 확인됐다
- recipe 자체가 그대로라 establish / insert를 충분히 분리하지 못한다
- 결과가 계속 모델 기본 성향으로 회귀할 가능성이 크다

이번 문제에는 부족하다.

### 2. Panel-Role-Aware Comic Render Profiles

`establish / beat / insert / closeup`마다 별도 comic render profile을 둔다.

장점:

- 현재 pipeline 위에 얹을 수 있다
- 가장 작은 구조 변경으로 가장 큰 품질 차이를 기대할 수 있다
- favorite still recipe를 버리지 않고 용도만 분리할 수 있다
- 이후 `panel family`, `genre profile`, `teaser profile`로 확장 가능하다

단점:

- profile resolver와 테스트가 늘어난다
- 초기 profile 튜닝이 필요하다

이번 단계에 가장 적합하다.

### 3. Full Comic Model Lane Split

comic용 캐릭터 버전, comic용 benchmark, comic용 checkpoint league를 별도로 만든다.

장점:

- 장기적으로 가장 강하다
- still / comic / animation을 완전히 분리 관리할 수 있다

단점:

- 지금 범위에서는 과하다
- DB / UI / 운영 루틴 전부 다시 키워야 한다
- 파일럿 검증 없이 가면 불필요한 복잡도를 만든다

이번 단계에는 과설계다.

## Recommended Direction

권장 방향은 `2. Panel-Role-Aware Comic Render Profiles`다.

핵심 원칙:

- `canonical_still`은 캐릭터 정체성 앵커로 유지
- comic generation은 `comic_panel_render_profile`이 결정
- profile은 `panel_type`를 기본 키로 선택
- same character + same scene라도 panel role에 따라 recipe가 달라진다

즉 앞으로의 결정 구조는 아래와 같다.

- character identity:
  - `character_version`
- comic panel visual behavior:
  - `comic_panel_render_profile`

그리고 최종 lineage는 다음과 같이 해석한다.

`character_version -> scene_panel(panel_type) -> comic_panel_render_profile -> generation -> selected_render_asset`

## In Scope

- panel-role-aware comic render profile abstraction 추가
- `establish / beat / insert / closeup` 기본 profile 4종 추가
- current comic generation request builder에서 profile resolve 적용
- panel role별 `checkpoint / LoRA / width / height / negative additions / anchor filtering` 제어
- live re-generation으로 `4컷 role separation` 확인
- tests update

## Out Of Scope

- character canonical still 재잠금
- full benchmark matrix 재실행
- teaser animation preset overhaul
- publish automation
- comic-only dedicated character_versions table
- full shot grammar rewrite

## Design Details

## Profile Layer

새 추상화:

- `comic_panel_render_profiles`

첫 구현은 `DB migration`보다 `code-backed registry`가 적합하다.
이유:

- 현재 문제는 실험이 필요한 bounded fix다
- 운영 중 바로 profile 내용을 바꿔볼 가능성이 높다
- persistence보다 resolver/behavior가 먼저 중요하다

초기 구현 위치 권장:

- `backend/app/services/comic_render_profiles.py`

registry entry fields:

- `profile_id`
- `panel_types`
- `checkpoint_mode`
  - `inherit`
  - `override`
- `checkpoint`
- `workflow_lane_mode`
  - `inherit`
  - `override`
- `workflow_lane`
- `lora_mode`
  - `inherit_all`
  - `filter_beauty_enhancers`
  - `override`
- `loras`
- `width`
- `height`
- `prompt_prefix_mode`
  - `inherit`
  - `soften_beauty_bias`
- `negative_prompt_append`
- `anchor_filter_mode`
  - `keep_all`
  - `drop_portrait_bias`
  - `drop_face_gloss_bias`

## Default Profiles

### `establish_env_v1`

target panels:

- `establish`

intent:

- 공간을 읽게 하는 컷
- 캐릭터는 frame 안에 있지만 주인공 얼굴 쇼케이스가 아님

default behavior:

- wider landscape bias
- beauty enhancer 제거 또는 약화
- environment readability 우선
- negative에 `close portrait`, `fashion shoot`, `glamour pose`, `airbrushed skin`, `copy-paste framing` 추가

recommended initial values:

- checkpoint: `inherit`
- lora_mode: `filter_beauty_enhancers`
- width / height: `1216 x 832`
- anchor_filter_mode: `drop_portrait_bias`

### `beat_dialogue_v1`

target panels:

- `beat`

intent:

- 인물과 핵심 소품/행동을 함께 읽는 중간 컷

default behavior:

- 현재 canonical still의 장점을 가장 많이 유지
- 다만 과한 editorial bias는 줄임

recommended initial values:

- checkpoint: `inherit`
- lora_mode: `inherit_all`
- width / height: `960 x 1216`
- anchor_filter_mode: `drop_face_gloss_bias`

### `insert_prop_v1`

target panels:

- `insert`

intent:

- 손, 소품, 시선 방향, 특정 디테일을 읽는 컷

default behavior:

- 얼굴보다 오브젝트 우선
- 과한 face enhancer 제거
- 손/소품/책상/메모 등 디테일 확보

recommended initial values:

- checkpoint: `inherit`
- lora_mode: `filter_beauty_enhancers`
- width / height: `1024 x 1024`
- anchor_filter_mode: `drop_portrait_bias`

### `closeup_emotion_v1`

target panels:

- `closeup`

intent:

- 감정 전달용 컷

default behavior:

- canonical still recipe 장점을 가장 많이 사용
- 대신 glossy AI finish를 줄이는 negative를 추가

recommended initial values:

- checkpoint: `inherit`
- lora_mode: `inherit_all`
- width / height: `832 x 1216`
- anchor_filter_mode: `drop_face_gloss_bias`

## Prompt Assembly Rule

현재 개선된 structured prompt 포맷은 유지한다.
다만 prompt는 이제 `final quality lever`가 아니라 `profile-selected recipe` 위의 설명 계층으로 본다.

즉 우선순위는 다음 순서다.

1. panel role
2. resolved profile
3. prompt structure
4. random seed

이렇게 해야 `establish`가 문장상으로만 establish이고 실제 결과는 portrait로 나오는 문제를 줄일 수 있다.

## Anchor and LoRA Policy

현재 문제의 핵심은 `beauty-focused enhancer`가 모든 panel에 동일 적용된다는 점이다.

따라서 첫 구현은 aggressive override보다 conservative filtering으로 간다.

규칙:

- `closeup`:
  - current canonical loras largely kept
- `beat`:
  - current canonical loras mostly kept
- `establish`:
  - face/detail enhancer 제거 또는 약화
- `insert`:
  - face/detail enhancer 제거 또는 약화

이 단계에서는 `checkpoint split`보다 `LoRA filtering + aspect split + negative split`의 효과를 먼저 검증한다.
필요하면 다음 단계에서만 checkpoint override를 연다.

## Negative Prompt Policy

이번 단계의 negative additions는 `AI 티 완화`가 목적이지, generic quality dump가 목적이 아니다.

공통 방향:

- `plastic skin`
- `waxy face`
- `airbrushed skin`
- `dead eyes`
- `copy-paste composition`
- `duplicated pose`
- `glamour shoot`
- `fashion editorial`
- `symmetrical mannequin face`

panel role별로 일부만 추가한다.

원칙:

- establish / insert는 `glamour shoot`, `fashion editorial`, `close portrait` 억제
- closeup은 `dead eyes`, `waxy skin`, `plastic skin` 억제 중심

## Acceptance Criteria

이 설계가 성공했다고 보려면 아래 조건을 만족해야 한다.

1. 동일 episode 4컷이 육안상 명확히 다른 역할을 가진다
2. establish panel에서 공간/배경/소품이 얼굴보다 먼저 읽힌다
3. insert panel에서 손/소품/행동 디테일이 우선 읽힌다
4. closeup에서만 strong face-focus가 허용된다
5. current `selected render -> export -> teaser` pipeline을 깨지 않는다

## Validation Plan

validation은 새 benchmark보다 `pilot regeneration`이 우선이다.

1. existing Camila sample episode 재생성
2. 4 panel candidates 육안 검수
3. 기존 preview와 side-by-side 비교
4. selected render 4개 확정 가능 여부 확인
5. export ZIP과 teaser derivation smoke 확인

핵심 평가지표:

- role separation
- repeated-face reduction
- background readability
- emotional readability
- “too AI-looking glamour still” 감소

## Risks

### 1. Wider aspect가 character consistency를 해칠 수 있다

대응:

- establish / insert에서만 넓은 비율 적용
- beat / closeup은 기존 portrait 비율 유지

### 2. enhancer 제거로 전반 화질이 약해질 수 있다

대응:

- 제거보다 `filter_beauty_enhancers` 방식으로 완화부터 시작
- closeup은 enhancer 유지

### 3. prompt 구조와 profile 규칙이 충돌할 수 있다

대응:

- prompt는 role-resolved profile 뒤에서 조립
- role-specific composition hint를 profile과 일치시킨다

## Follow-Up

이번 단계가 성공하면 다음 우선순위는 아래 순서다.

1. `comic_panel_render_profile` live tuning round
2. 필요 시 `checkpoint override`를 포함한 profile v2
3. favorite still / comic panel / teaser keyframe을 분리하는 `multi-lane recipe strategy`

## References

- Comic Cmoa title page:
  - `https://www.cmoa.jp/title/346887/`
- STUDIO ZOON official interview:
  - `https://www.cyberagent.co.jp/way/list/detail/id=30909`
- Stability AI prompt guide:
  - `https://stability.ai/learning-hub/stable-diffusion-3-5-prompt-guide`
- Black Forest Labs prompting fundamentals:
  - `https://docs.bfl.ai/guides/prompting_guide_t2i_fundamentals`
- Black Forest Labs FLUX.2 prompt guide:
  - `https://docs.bfl.ai/guides/prompting_guide_flux2`
