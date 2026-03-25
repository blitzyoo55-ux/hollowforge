# Lab451 실행 로드맵

기준일: 2026-03-12

## 0. 목표
- HollowForge를 `이미지 생성/선별/카피/오케스트레이션` 콘솔로 고정한다.
- SNS 운영과 애니메이션 실행은 외부 실행기로 분리한다.
- `고품질 프롬프트 양산 → 대량 생성 → 선별 → 게시글 생성 → SNS 게재 → 반응 기반 애니메이션화`를 하나의 운영 루프로 만든다.
- 메인 생산 구조를 `랜덤 우수컷 영상화`가 아니라 `캐릭터 IP + 에피소드 + 샷` 기반으로 전환한다.

## 1. 현재 상태

### 완료
- 로컬 이미지 생성 파이프라인 안정화
- 프런트 경량화 및 전체 린트/빌드 통과
- `caption_variants`, `publish_jobs`, `engagement_snapshots`, `animation_candidates`, `animation_jobs` 기반 추가
- 캡션 생성 서비스 분리
- 퍼블리싱 API 및 애니메이션 후보/잡 API 추가
- `lab451-animation-worker` 스캐폴드 및 `stub` executor 추가
- HollowForge ↔ worker dispatch/callback 계약 추가
- lane 기반 image production 경로 추가
- `generate-and-queue` 기반 one-step prompt batch queue 추가
- `sdxl_illustrious` lane 기본값 교정 및 Prompt Factory backend 연결 완료
- HollowForge 프런트에 `Prompt Factory` 페이지 추가
- 오퍼레이터가 브리프 입력 후 `25장 Generate & Queue`를 바로 실행할 수 있는 테스트 흐름 구축
- 저신호 체크포인트 `oneObsession_v19Atypical.safetensors` 정리 완료

### 미완료
- `characters`, `character_versions`, `episodes`, `storyboard_shots`, `shot_assets` 스키마
- `Character Lab` / `Episode Board` 운영 화면
- `Ready to Go Ops` UI
- 프롬프트 팩토리의 character-linked lineage / shot-pack mode / CSV 계보 추적
- 실제 SNS 게시 실행기
- 실제 애니메이션 executor
- motion template / render profile 자산 관리
- 성과 데이터 기반 자동화 룰 고도화

## 2. 아키텍처 원칙

### HollowForge가 담당
- 이미지 생성
- 캐릭터 후보 탐색 및 canonical recipe 관리
- 에피소드 / 샷 설계
- ready-to-go 선별
- 캡션 초안 생성과 승인
- 게시 작업 생성
- 반응 수집과 애니메이션 후보 선정
- 애니메이션 잡 생성 / dispatch / 상태 추적

### 외부 서비스가 담당
- SNS 계정 인증, 예약 발행, 재시도
- GPU 무거운 애니메이션 실행
- 실행기별 인증, 호환성, 비용 통제

## 3. 핵심 의사결정

### 이미지
- 계속 로컬 우선
- 이유:
  - 반복 실험 속도
  - 자산 통제
  - 기존 HollowForge 구조와 정합
  - 캐릭터 후보 still / 샷 anchor still 생산에 최적

### 애니메이션
- 원격 worker 우선
- 이유:
  - 로컬 PC 스펙 불확실성
  - 영상 생성은 VRAM/처리시간/운영 안정성 요구가 큼
  - 실행기 교체 필요성이 높음

### 외부 GPU 호스트
- `Runpod`은 기술적 후보로만 유지
- 실제 운영 전 정책 적합성 검토가 선행되어야 함
- 장기적으로는 `특정 호스트 종속`이 아니라 `remote worker adapter` 전략 유지

### 운영 구조
- `탐색 20% + 시리즈 생산 80%`
- 무작위 대량 생성은 `캐릭터 후보 발굴`에만 사용
- 본 생산은 `캐릭터 확정 → 에피소드 설계 → 샷팩 생성 → 선택 샷만 I2V 렌더`로 운영

## 4. 우선순위 로드맵

## Phase 1 — Character Core
목표: 랜덤 이미지 운영에서 캐릭터 자산 운영으로 전환한다.

### 1-1. Character Schema
- 범위:
  - `characters`
  - `character_versions`
  - canonical recipe / reference set
- 완료 기준:
  - 이미지가 아닌 캐릭터 단위로 생산 레시피와 대표 레퍼런스를 저장 가능

### 1-2. Character Lab
- 범위:
  - 캐릭터 후보 still 묶음
  - 주연 후보 선정
  - 이름 / codename / worldline / archetype 입력
- 완료 기준:
  - 주연 후보 3~5명을 UI에서 고정 관리 가능

### 1-3. Character-linked Prompt Factory
- 범위:
  - 탐색용 prompt batch
  - 캐릭터 seed pack 생성
  - canonical tag 자동 주입
- 현재 상태:
  - generic exploration UI와 `generate-and-queue`는 완료
  - character-linked batch lineage는 아직 미완료
- 완료 기준:
  - prompt batch가 character version과 연결됨

## Phase 2 — Storyboard Core
목표: ready 이미지 선별 중심에서 shot 생산 중심으로 전환한다.

### 2-1. Episode Schema
- 범위:
  - `episodes`
  - `storyboard_shots`
- 완료 기준:
  - episode / shot 단위로 기획과 상태 관리 가능

### 2-2. Episode Board
- 범위:
  - shot 번호
  - beat type
  - camera / motion intent
  - target duration
- 완료 기준:
  - 한 episode의 shot list를 UI에서 설계 가능

### 2-3. Shot Pack Prompting
- 범위:
  - shot별 anchor still `2~4`장 생성
  - drift suppress tags
  - shot intent 기반 변주
- 현재 상태:
  - 현재 Prompt Factory는 exploration batch만 지원
  - shot-pack mode는 아직 없음
- 완료 기준:
  - 한 shot을 위한 still pack을 Prompt Factory에서 직접 생성 가능

## Phase 3 — 운영 가능한 콘텐츠 파이프라인 완성
목표: 이미지 선정 후 게시 직전까지를 매일 돌릴 수 있게 만든다.

### 3-1. Ready Queue Ops UI
- 범위:
  - ready 이미지 목록
  - 캡션 3안 생성
  - 승인/수정
  - 게시 작업 생성
- 산출물:
  - 운영자가 브라우저에서 게시 직전 묶음을 완성 가능
- 완료 기준:
  - `publish_jobs`를 UI만으로 생성 가능
  - 승인된 캡션이 이미지 단위로 저장됨

### 3-2. Prompt Factory V1
- 범위:
  - recipe 기반 프롬프트 조합
  - variation matrix
  - CSV export
  - exploration mode / shot-pack mode 분리
- 산출물:
  - 대량 생성용 CSV와 shot pack을 UI에서 바로 생산
- 완료 기준:
  - prompt batch id / row id / campaign id가 generation metadata와 연결됨

### 3-3. Curation Metadata
- 범위:
  - 왜 선택했는지
  - 어느 플랫폼에 맞는지
  - 어떤 후속 액션 후보인지
- 완료 기준:
  - ready 이미지에 `reason`, `platform_fit`, `animation_potential` 같은 운영 태그 부여 가능

## Phase 4 — SNS 발행 실행기 구축
목표: HollowForge 밖에서 실제 게시를 수행한다.

### 4-1. `lab451-publisher` 생성
- 범위:
  - draft / queued / scheduled / published / failed 처리
  - 외부 플랫폼별 어댑터
  - 결과를 HollowForge `publish_jobs`에 반영
- 완료 기준:
  - HollowForge의 publish job이 실제 외부 포스트로 연결됨

### 4-2. 플랫폼 어댑터 우선순위
- 1순위:
  - 텍스트/이미지 게시가 단순한 채널
- 2순위:
  - 업로드 포맷과 검수 흐름이 복잡한 채널
- 원칙:
  - 하나씩 붙인다
  - 계정 인증 / 재시도 / 감사 로그를 공통층으로 둔다

### 4-3. 반응 수집
- 범위:
  - likes / reposts / bookmarks / impressions 수집
  - 수동 입력 + 자동 수집 혼합
- 완료 기준:
  - `engagement_snapshots`가 실제 운영 데이터로 채워짐

## Phase 5 — 애니메이션 운영 전환
목표: 반응 좋은 이미지가 아니라 `샷 단위 자산`을 실제 애니메이션 생산 큐로 넘긴다.

### 5-1. Worker 실전 executor 추가
- 범위:
  - 현재 `stub`를 실제 executor로 교체
  - 최소 1개 real backend 구현
- 후보:
  - remote self-hosted ComfyUI/video stack
  - Hunyuan 계열 실행기
  - 기타 원격 image-to-video / avatar executor
- 완료 기준:
  - worker가 실제 mp4 결과물을 생성하고 HollowForge에 callback

### 5-2. Shot-Centric Asset Handoff
- 범위:
  - `storyboard_shot_id`
  - `character_version_id`
  - `reference_images[]`
  - template video
  - motion preset
  - render profile
  - prompt / negative prompt
- 완료 기준:
  - 애니메이션 job 하나에 필요한 shot 단위 입력이 표준 JSON으로 정리됨

### 5-3. Result Registry
- 범위:
  - 생성된 영상 URL / 썸네일 / 실패 로그 저장
  - 갤러리 / 게시 파이프라인과 연결
  - episode timeline과 연결
- 완료 기준:
  - shot 원본과 영상 결과가 운영 화면에서 연결 조회됨

## Phase 6 — 자동화 룰 고도화
목표: 운영자가 모든 판단을 수동으로 하지 않아도 되게 만든다.

### 6-1. 애니메이션 후보 점수 고도화
- 범위:
  - 반응 절대값
  - 반응 속도
  - platform fit
  - curation quality
  - character / worldline priority
- 완료 기준:
  - 단순 bookmark threshold보다 정교한 추천 가능

### 6-2. 자동 dispatch 룰
- 범위:
  - approved candidate 중 특정 조건 만족 시 자동 queue
- 완료 기준:
  - 승인된 일부 후보는 수동 클릭 없이 worker로 전달 가능

### 6-3. 운영 대시보드
- 범위:
  - 생성량
  - 게시량
  - 반응 상위 포스트
  - 애니메이션 성공률 / 비용
  - character / episode / worldline 성과
- 완료 기준:
  - 주간 운영 판단을 한 화면에서 할 수 있음

## 5. 권장 구현 순서

### 즉시
1. `characters`, `character_versions` 스키마
2. `Character Lab`
3. `episodes`, `storyboard_shots`, `shot_assets` 스키마
4. `Episode Board`

### 그 다음
5. `Ready to Go Ops` UI
6. `Prompt Factory`를 `exploration mode` / `shot-pack mode`로 확장
7. worker real executor 1종
8. shot-centric asset handoff
9. animation result registry

### 마지막
10. `lab451-publisher` 최소 골격
11. 자동 dispatch 룰
12. 운영 대시보드
13. 비용/성능 최적화

## 6. 리스크와 대응

### 정책 리스크
- 문제:
  - 외부 API/호스트 정책 변동
- 대응:
  - HollowForge는 provider-agnostic 유지
  - worker executor를 교체 가능하게 설계

### 성능 리스크
- 문제:
  - 영상 생성 속도와 비용이 예측보다 큼
- 대응:
  - local fallback + remote worker 병행
  - render profile을 low / medium / premium으로 분리

### 운영 리스크
- 문제:
  - SNS 플랫폼별 업로드 규칙, 인증, 제한이 제각각
- 대응:
  - publisher를 별도 서비스로 격리
  - 플랫폼 어댑터를 순차 도입

### 품질 리스크
- 문제:
  - 이미지 품질과 영상 품질의 판단 기준이 다름
- 대응:
  - 캐릭터 canonical recipe를 먼저 고정
  - shot anchor still을 거친 후 영상화
  - motion preset과 render profile 표준화 후 자동화 확대

### 구조 리스크
- 문제:
  - 랜덤 우수컷 위주 운영이 캐릭터 자산 누적을 방해함
- 대응:
  - 탐색과 본 생산을 분리
  - 본 생산은 character / episode / shot 엔터티를 기준으로 운영

## 7. 완료 정의

### 단기 완료
- 캐릭터 후보를 고르고
- canonical recipe를 확정한 뒤
- episode와 shot을 만들고
- shot별 still pack을 생성할 수 있다

### 중기 완료
- 실제 publisher가 외부 포스트를 생성한다
- 실제 animation worker가 shot 단위 mp4를 생산한다
- HollowForge에서 character → episode → shot → post → video 전 과정을 추적할 수 있다

### 장기 완료
- 운영자는 캐릭터 / 세계관 / 에피소드 설계에 집중하고
- 게시와 애니메이션 실행은 시스템이 보조한다

## 8. 다음 재개 지점
- 작업을 다시 시작할 때 첫 우선순위는 `characters`, `character_versions`, `episodes`, `storyboard_shots`, `shot_assets` 스키마다.
- 그 다음은 `Character Lab`과 `Episode Board`다.
- `Prompt Factory`는 현재 테스트용 브리프 → 25장 queue 흐름까지 완료됐고, 다음 확장은 character-linked lineage와 shot-pack mode다.
- 애니메이션 쪽은 현재 `worker scaffold + stub executor`에서 멈춘 상태이며, 다음 재개 시 `shot-centric asset handoff + real executor 1종`을 붙이면 된다.
