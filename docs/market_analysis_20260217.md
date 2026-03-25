# Rule34.xxx 시장 분석 리포트 (2026-02-17)

- 데이터 기준 시점: `2026-02-16 15:07~15:11`
- 사용 파일:
  - `data/tag_stats_20260216_1509.csv`
  - `data/combo_stats_20260216_1511.csv`
- 주의: 태그별 `post_count`는 중복 집계(같은 포스트가 여러 태그에 포함)라 전체 합계는 실제 총 포스트 수가 아님.

## 1) 시장 규모 분석 (공급량 기준)

### 상위 대형 시장 태그 (post_count)
| 태그 | post_count | avg_score |
|---|---:|---:|
| breasts | 7,604,053 | 1.05 |
| solo | 3,789,310 | 1.25 |
| ai_generated | 2,583,161 | 0.75 |
| 1girl | 738,685 | 1.05 |
| original | 547,206 | 9.30 |
| bondage | 421,084 | 4.00 |
| collar | 417,786 | 9.45 |
| stable_diffusion | 347,095 | 0.50 |
| stockings | 328,893 | 7.30 |
| high_heels | 273,587 | 10.05 |

### 라텍스/마스크 관련 시장 규모
| 태그 | post_count | avg_score |
|---|---:|---:|
| mask | 130,416 | 17.10 |
| latex | 109,268 | 4.35 |
| rubber | 27,551 | 12.55 |
| latex_suit | 20,921 | 37.50 |
| gas_mask | 7,745 | 19.40 |
| latex_mask | 924 | 26.60 |
| full_face_mask | 2 | 29.00 |

해석:
- `latex` 자체는 공급이 큰 편(109k+)이지만 반응도(avg_score 4.35)는 낮은 편.
- 반면 `latex_suit`, `latex_mask`, `gas_mask`는 공급 대비 반응도가 높아 니치 공략 가치가 큼.

## 2) 유저 반응도 분석 (avg_score 중심)

### 반응도 상위 태그 (sample_size=20 기준)
| 순위 | 태그 | post_count | avg_score |
|---:|---|---:|---:|
| 1 | latex_suit | 20,921 | 37.50 |
| 2 | catsuit | 4,093 | 30.75 |
| 3 | zentai | 112 | 29.50 |
| 4 | latex_mask | 924 | 26.60 |
| 5 | latex_gloves | 28,885 | 26.50 |
| 6 | bishoujo | 33 | 23.15 |
| 7 | gas_mask | 7,745 | 19.40 |
| 8 | mask | 130,416 | 17.10 |

### 공급 대비 반응(기회 관점)
- 고득점 + 저공급 조합이 가장 매력적인데, 본 데이터에서는 다음 태그가 해당:
  - `latex_suit` (20,921 / 37.5)
  - `latex_mask` (924 / 26.6)
  - `gas_mask` (7,745 / 19.4)
  - `catsuit` (4,093 / 30.75)
  - `zentai` (112 / 29.5)
- `full_face_mask`는 반응도는 높지만(`29.0`) 표본 수(`sample_size=2`)가 매우 작아 신뢰도 낮음.

## 3) AI 콘텐츠 현황

| 태그 | post_count | avg_score | sampled_comments |
|---|---:|---:|---:|
| ai_generated | 2,583,161 | 0.75 | 5 |
| stable_diffusion | 347,095 | 0.50 | 5 |
| novelai | 34,273 | 10.35 | 28 |

해석:
- AI 태그 공급량은 매우 큼 (`ai_generated`, `stable_diffusion` 대규모).
- 그러나 `avg_score`는 매우 낮아(0.5~0.75) 범용 AI 이미지는 포화/저반응 상태로 보임.
- `novelai`는 상대적으로 공급이 작고(`34k`) 반응도는 높음(`10.35`) → “스타일 특화 AI”에 대한 선호 가능성.

## 4) 콤보 태그 분석 (latex + 기타)

### 수집 결과
- `combo_stats_20260216_1511.csv`의 56개 조합 모두 `post_count = 0`.
- 즉, 현재 콤보 데이터만으로는 “어떤 조합이 가장 인기”인지 실측 판단 불가.

### 데이터 품질 관점 해석
- 가능성 1: API/쿼리 방식에서 AND 검색이 정상 동작하지 않음.
- 가능성 2: 조합 문자열 포맷(띄어쓰기/인코딩/태그명 정합성) 이슈.
- 가능성 3: 수집 스크립트에서 post_count 파싱/저장 로직 오류.

## 5) 프로젝트 타겟 적합도

프로젝트 콘셉트: **라텍스 풀페이스 마스크 미소녀**

관련 핵심 태그(현재 데이터 기준):
- 소재/의상: `latex_suit`, `latex`, `rubber`
- 마스크: `latex_mask`, `full_face_mask`, `gas_mask`, `mask`
- 캐릭터성: `bishoujo`, `1girl`, `original`

### 적합도 요약
- **수요(반응) 강함:** `latex_suit`(37.5), `latex_mask`(26.6), `gas_mask`(19.4), `mask`(17.1)
- **공급 과다/차별화 필요:** `latex`(109k, 4.35), `mask`(130k, 17.1은 높지만 경쟁 큼)
- **희소 니치:** `full_face_mask`(2, 29.0)와 `bishoujo`(33, 23.15)
  - 다만 `full_face_mask`는 표본 신뢰도 낮음(sample_size=2)

결론:
- 콘셉트와 가장 잘 맞는 실전 축은 `latex_suit + (latex_mask 또는 gas_mask) + bishoujo/1girl`.
- “풀페이스”는 직접 태그(`full_face_mask`)보다 `latex_mask`/`gas_mask`로 우회 확장하는 편이 데이터상 안전.

## 6) 전략 제안 (우선 타겟 3~5개)

콤보 실측이 0이라 단일 태그 수요-공급 지표를 기반으로 우선순위를 제안함.

### 추천 1) `latex_suit + latex_mask + 1girl`
- 근거: `latex_suit`(37.5) + `latex_mask`(26.6) 모두 고반응, 공급은 중소형(20,921 / 924).
- 기대: 콘셉트 정합성 최고, 과포화 구간 회피 가능.

### 추천 2) `latex_suit + gas_mask + 1girl`
- 근거: `gas_mask` 반응도 높음(19.4), 공급 7,745로 적정 경쟁.
- 기대: 풀페이스 인상을 유지하면서 `full_face_mask` 데이터 빈약 문제를 보완.

### 추천 3) `latex_suit + mask + bishoujo`
- 근거: `mask`는 대형 시장(130,416) + 높은 반응(17.1), `bishoujo`는 희소 고반응(23.15).
- 기대: 트래픽 풀 확장 + 캐릭터 취향 세분화 동시 달성.

### 추천 4) `catsuit(or zentai) + latex_mask + 1girl`
- 근거: `catsuit`(30.75), `zentai`(29.5)는 매우 높은 반응의 니치.
- 기대: 라텍스 보디 실루엣 강조형 파생 라인업으로 차별화.

### 추천 5) `latex_suit + rubber + original`
- 근거: `rubber`(12.55), `original`(9.3)은 중간 이상 반응과 안정 공급.
- 기대: IP 의존 없이 자체 스타일 브랜딩에 유리.

## 실행 우선순위
1. 1차 메인 라인: 추천 1, 2
2. 2차 확장 라인: 추천 3
3. 3차 실험 라인: 추천 4, 5

## 리스크 및 다음 수집 개선
- 현재 최대 리스크는 `combo_stats` 전부 0인 데이터 결손.
- 다음 수집에서는 아래를 우선 수정 필요:
  1. AND 검색 쿼리 검증(수동 5개 샘플 대조)
  2. 태그 인코딩/BOM/공백 정규화
  3. 0값 저장 전 원본 응답 로깅
  4. 조합별 `avg_score`도 함께 수집 (현재는 공급량만 존재)
