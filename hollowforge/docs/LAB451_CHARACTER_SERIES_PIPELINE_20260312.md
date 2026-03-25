# Lab451 Character-Series Animation Pipeline

기준일: 2026-03-12

## 0. 결론
- 메인 운영 구조는 `무작위 우수컷 애니메이션화`가 아니라 `캐릭터 IP + 에피소드 + 샷` 기반으로 전환한다.
- 무작위 대량 생성은 완전히 버리지 않고 `탐색용 후보 발굴`에만 쓴다.
- 본 생산은 `주인공 캐릭터 고정 → 에피소드 설계 → 샷별 anchor still 생성 → 선택 샷만 원격 I2V 렌더`로 간다.
- 샷당 필요한 이미지만 만든다. 처음부터 `100장 전량 생성`은 기본 흐름으로 삼지 않는다.

## 1. 왜 이 방향이 맞는가

### 1-1. 상품성
- 이름과 룩이 고정된 캐릭터는 시리즈화, 묶음 판매, 후속편, 팬 축적에 유리하다.
- 무작위 우수컷은 순간 반응은 얻기 쉽지만, 카탈로그 자산과 세계관 축적이 약하다.
- Lab-451은 세계관 확장이 핵심이므로 `컷 단위 상품`보다 `캐릭터 단위 상품`이 더 맞다.

### 1-2. 영상 모델 효율
- 현재 영상 모델은 임의의 1장보다 `같은 인물의 일관된 레퍼런스 묶음`이 있을 때 결과가 안정적이다.
- 샷별 anchor still을 두고 선택 렌더하는 방식이 재시도 비용을 줄인다.
- 랜덤 컷을 매번 영상화하면 캐릭터, 의상, 시점, 조명 일관성을 매회 새로 맞춰야 한다.

### 1-3. 하드웨어 / 클라우드 현실성
- still 생성은 로컬이 효율적이다.
- 본편급 I2V는 VRAM, 처리시간, 실패 비용 때문에 원격 worker가 맞다.
- 따라서 `HollowForge = 기획/선별/오케스트레이션`, `animation worker = 원격 실행` 구조를 유지한다.

## 2. 두 운영안 비교

### A. 무작위 이미지 양산 → 우수컷 애니메이션화
#### 장점
- 시작이 빠르다.
- 탐색량이 크다.
- 썸네일/포스터 실험에는 유리하다.

#### 단점
- 캐릭터 자산이 축적되지 않는다.
- 시리즈/구독형 상품성이 약하다.
- 샷 간 연속성이 낮아 영상 편집 비용이 커진다.
- 영상 생성 실패 시 다시 쓸 수 있는 레퍼런스 자산이 적다.

#### 용도
- 시장 탐색
- 캐릭터 후보 발굴
- 단발성 프로모 컷

### B. 캐릭터 선정 → 스토리보드 → 샷팩 생성 → 선택 샷 애니메이션화
#### 장점
- 세계관/캐릭터 자산이 누적된다.
- 영상 모델이 요구하는 일관성 확보에 유리하다.
- 에피소드 단위 상품화가 가능하다.
- 잘된 캐릭터는 반복 생산 시 원가가 내려간다.

#### 단점
- 초기에 설계 비용이 든다.
- 캐릭터 선정과 샷 관리 구조가 필요하다.

#### 용도
- 메인 운영
- 시리즈 제작
- 반복 가능한 고품질 생산

## 3. 권장 최종 구조

### 3-1. 운영 비율
- `탐색 20%`
- `시리즈 생산 80%`

### 3-2. 운영 루프
1. Prompt Factory로 캐릭터 후보 still 대량 생성
2. 후보 중 `주연 후보 3~5명` 선정
3. 캐릭터별 이름, 시그니처 룩, 레시피, 레퍼런스 세트 확정
4. 에피소드별 스토리보드와 샷 리스트 작성
5. 샷별 anchor still `2~4장` 생성
6. 샷별 best anchor만 원격 I2V queue
7. 결과 영상 평가 후 재생성 필요 샷만 재시도
8. 완성본 게시 후 engagement로 다음 에피소드 우선순위 조정

## 4. 100장 선생성 방식에 대한 판단
- `샷 수`가 아니라 `샷 실패율`이 비용을 결정한다.
- 그래서 에피소드마다 I2V용 이미지를 100장 먼저 만드는 것은 기본값으로는 비효율적이다.
- 더 나은 기준은 아래와 같다.
  - 에피소드 샷 수: `8~16`
  - 샷당 anchor still: `2~4`
  - 총 anchor still: `16~64`
- 이 범위에서 먼저 검증하고, 문제 샷만 추가 still을 만든다.

## 5. HollowForge가 가져야 할 새 엔터티

### 5-1. Characters
- 이름
- codename
- archetype
- worldline
- status (`candidate`, `core`, `retired`)
- 대표 이미지

### 5-2. Character Versions
- checkpoint
- lane
- LoRA recipe
- prompt profile
- negative prompt profile
- canonical tags
- canonical outfit / hair / body / color notes

### 5-3. Episodes
- episode code
- title
- synopsis
- target platform
- status (`draft`, `planned`, `in_production`, `released`)

### 5-4. Storyboard Shots
- episode id
- shot number
- beat type (`intro`, `build`, `peak`, `cooldown`, `transition`)
- camera framing
- motion intent
- duration target
- dialogue/text note

### 5-5. Shot Assets
- shot id
- anchor still generations
- selected keyframe
- rejected keyframes
- render attempts
- final video output

## 6. Prompt Factory가 바뀌어야 할 점

### 6-1. 현재 상태
- 현재는 배치 프롬프트와 lane-aware image queue까지는 된다.
- 이는 탐색용 still 생산에는 적합하다.

### 6-2. 추가 필요 기능
- `character seed pack` 생성
- `episode shot pack` 생성
- `shot intent` 기반 prompt variants
- 캐릭터 canonical tag 자동 삽입
- 샷별 금지 drift 태그 자동 삽입

## 7. 애니메이션 worker가 바뀌어야 할 점

### 7-1. 현재 상태
- provider-agnostic animation job orchestration은 이미 들어가 있다.
- 하지만 입력은 아직 generation 중심이다.

### 7-2. 추가 필요 기능
- `reference_images[]` 지원
- `character_version_id` 지원
- `storyboard_shot_id` 지원
- `motion_preset_id` 지원
- `render_profile_id` 지원
- shot batch callback 지원

## 8. 인프라 권장

### 8-1. 로컬
- 캐릭터 후보 still 생성
- shot anchor still 생성
- quality gate / ready review

### 8-2. 원격 저비용 GPU
- 짧은 후보 렌더
- 모션 테스트
- 레퍼런스 적합성 확인

### 8-3. 원격 고성능 GPU
- 본편급 최종 렌더
- 장면 수가 많은 episode render
- upscale / final encode

## 9. 우선순위 구현 단계

### Phase 1 — Character Core
- `characters`
- `character_versions`
- 캐릭터 후보 선정 UI
- canonical reference set 저장

### Phase 2 — Storyboard Core
- `episodes`
- `storyboard_shots`
- shot status board
- shot별 prompt pack 생성

### Phase 3 — Shot Asset Pipeline
- shot별 anchor still 묶음 생성
- best anchor 선택
- shot asset registry

### Phase 4 — Animation Execution
- shot 단위 animation job dispatch
- `reference_images[]` / `storyboard_shot_id` handoff
- output registry와 episode timeline 연결

### Phase 5 — Series Ops
- 에피소드 편집 큐
- 캐릭터별 성과 분석
- worldline별 성과 분석
- 후속편 자동 추천

## 10. 하지 말아야 할 것
- 랜덤 우수컷만 계속 영상화하는 것을 메인 생산 루프로 삼지 않는다.
- 매 에피소드마다 100장 이상을 먼저 만들고 나서 쓰임새를 고민하지 않는다.
- 영상 모델 실패를 프롬프트 양으로 덮으려 하지 않는다.
- 캐릭터 canonical recipe 없이 shot 생산부터 시작하지 않는다.

## 11. 다음 구현 제안
- 1순위: `characters`, `character_versions`, `episodes`, `storyboard_shots`, `shot_assets` 스키마 추가
- 2순위: Ready to Go 옆에 `Character Lab`과 `Episode Board` 추가
- 3순위: Prompt Factory를 `exploration mode`와 `shot-pack mode`로 분리
- 4순위: animation job payload를 shot 중심으로 재정의

## 12. 최종 판단
- 메인 전략은 `캐릭터 IP + 에피소드 + 샷팩 + 원격 I2V`다.
- 랜덤 대량 생성은 계속 쓰되, 이는 본 생산이 아니라 탐색 단계로 제한한다.
- 이 구조가 현재 HollowForge의 lane 기반 still 생산, Ready-to-Go 선별, animation worker 분리 구조와 가장 잘 맞는다.
