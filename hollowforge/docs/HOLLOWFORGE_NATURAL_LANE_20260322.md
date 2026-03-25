# HollowForge Natural Lane

기준일: 2026-03-22

## 목적

- 최근 `canonical_still` 기반 identity pack은 캐릭터 잠금은 강했지만 `AI 생성 티`가 강했다.
- 원인은 `high-response beauty editorial` prefix, `ultimate` 계열 still 잠금, 그리고 `Face_Enhancer + DetailedEyes`의 반복 사용에 있다.
- 그래서 `사람이 그린 듯한`, `자연스럽고 아름다운` 결과를 위한 별도 레인을 분리한다.

## natural lane 원칙

- 목적은 `고반응 hero still`이 아니라 `자연스러운 캐릭터 유지`다.
- `ultimateHentai...`는 natural lane에서 제외한다.
- `prefect`, `wai140`, `wai160`만 사용한다.
- `Face_Enhancer_Illustrious`는 제거한다.
- `DetailedEyes`는 낮은 강도로만 남긴다.
- 프롬프트는 `soft ambient light`, `subtle skin texture`, `relaxed expression`, `delicate linework`, `painterly shading`, `lived-in atmosphere`를 기본 축으로 둔다.
- 샷은 `정체성 고정 + 일상성 + 자연광` 중심으로 설계한다.

## 운영 구조

- `canonical_still`: 썸네일 반응, 프로모 still, 고반응 lifestyle용
- `canonical_natural`: 자연형 character sheet, 일상형 benchmark, 후속 character LoRA 데이터셋용
- `animation_anchor`: 애니메이션 참조용

즉 앞으로 `캐릭터 일관성`을 평가할 때는 `canonical_still`만 보지 않고 `canonical_natural`도 함께 본다.

## 캐릭터별 scene pack

- 자연형 레인은 공통 샷만 반복하지 않는다.
- 각 캐릭터는 `profession`, `background`, `personality`, `natural_scene_briefs`를 가진다.
- 즉 같은 `window / kitchen / street` 계열이라도, 실제 scene brief는 캐릭터의 직업과 생활 패턴에 맞게 다르게 간다.
- 예:
  - Kaede Ren: `gallery brand strategist` 기반 출근/무드보드/북스토어 장면
  - Mina Sato: `fashion magazine editor` 기반 proof review/commute/editorial desk 장면
  - Elena Petrov: `couture atelier consultant` 기반 fitting notes/archive corridor 장면

이 구조를 쓰면 `같은 캐릭터가 왜 그 장면에 있는지`가 설명되고, 결과도 덜 템플릿처럼 보이게 된다.

## depth / perspective / background 규칙

- 같은 인물이라도 `medium close`, `waist-up environmental`, `seated medium-wide`, `35mm street`, `side-angle balcony`처럼 원근을 분리해 쓴다.
- 프롬프트에는 단순 scene 설명만이 아니라 아래 4개를 같이 넣는다.
  - `camera profile`
  - `depth staging`
  - `environment interaction`
  - `background behavior`
- 목적은 `인물이 배경 앞에 붙어 보이는 cutout 느낌`을 줄이는 것이다.
- 예:
  - 손이 창틀, 컵, 의자 팔걸이, 책등, 레일과 실제로 접촉한다.
  - foreground / subject / background가 층으로 나뉜다.
  - 배경은 `template interior` 대신 공간별 불균형과 생활 흔적을 허용한다.

또한 negative prompt에는 `sticker-like subject`, `pasted background`, `mismatched perspective`, `repeated background assets`, `weak contact shadows`를 넣어 합성감이 강한 이미지를 줄인다.

## single-subject / scene alignment 규칙

- 자연형 레인은 기본적으로 `한 명의 캐릭터를 생활 장면 안에 고정`하는 것이므로 `single subject only`, `one woman only`, `no companion`, `no reflected duplicate`를 프롬프트 상단에 둔다.
- negative prompt에도 `two women`, `twins`, `sisters`, `duplicate person`, `background pedestrian`, `mirror clone` 등을 명시해 2인 구도 오인을 더 강하게 누른다.
- `natural_scene_briefs`는 캐릭터별 맥락을 주는 용도이고, 샷 프로필은 `scene_01~06`의 카메라/깊이 역할만 담당한다.
- 즉 `window`, `kitchen`, `bookstore`처럼 장소명을 고정한 샷 템플릿으로 brief를 덮어쓰지 않는다.
- `mirror` 같이 반사로 2인처럼 보일 수 있는 단어는 가능한 한 `wait`, `panel`, `prep corner` 같은 단일 인물 중심 표현으로 정규화한다.

## shot-specific recipe override

- 특정 캐릭터가 특정 샷에서 반복적으로 `2인 구도`, `split-face`, `복합 outfit`로 무너지면, 그 샷만 별도 recipe로 분리한다.
- 이 override는 `characters.natural_shot_overrides`에 저장하고, 최소한 아래 항목을 개별적으로 바꿀 수 있게 둔다.
  - `checkpoint`
  - `loras`
  - `prompt_prefix`
  - `scene_brief`
  - `camera / depth / interaction / background`
  - `negative_prompt_extra`
- 첫 적용 대상은 `Hana Seo`의 `scene_01_close_anchor`, `scene_05_exterior_transition`이다.

## single-subject QC gate

- 자연형 배치는 생성 후 얼굴 검출 기반 QC를 반드시 한 번 더 돈다.
- 기준은 단순하다.
  - `face_count == 1` 이면 통과
  - `face_count != 1` 이면 `reject_multi_face`
- QC 스크립트는 `backend/scripts/qc_single_subject_batch.py`를 사용하고, 실패 컷은 `publish_approved=2`로 떨어뜨린다.
- 현재 WD14 태그만으로는 `duplicate_faces`가 충분히 안정적으로 잡히지 않아서, primary gate는 얼굴 검출 수를 쓴다.

## 즉시 실행

1. `character_versions.purpose='canonical_natural'` 추가
2. 12명 x 6샷 자연형 benchmark 생성
3. favorite/shortlist를 본 뒤 자연형 우승 레시피를 잠금
4. 그 레시피로 새 identity pack을 재생성
5. 그 다음 상위 캐릭터만 LoRA 후보로 승격 검토
