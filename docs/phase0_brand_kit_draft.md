# Phase 0 — Brand Identity Kit (Draft)
**Date:** 2026-02-17

---

## 1. 계정명 후보

| # | 계정명 | 콘셉트 | 장점 | 단점 |
|---|--------|--------|------|------|
| A | `@lab_xx_official` | 비밀 연구소 피험자 | 세계관 명확, 넘버링 자연스러움 | 약간 generic |
| B | `@hollow_doll` | 속이 빈 인형 (faceless) | 페티시 감성 직관적, 짧고 기억 용이 | 인형 = 인격 부재 뉘앙스 |
| C | `@latex_phantom` | 유령/환영 (얼굴 없는 존재) | 미스터리 감성, latex 키워드 포함 | phantom이 공포 뉘앙스 |
| D | `@glossy_unit` | 광택 + 유닛 | 질감 강조, 기술적 느낌 | 덜 sexy |
| E | `@void_figure` | 공허한 형상 | 아트 감성, 고급스러움 | 직관성 부족 |

> **추천:** `B. @hollow_doll` — 짧고 기억하기 쉬우며, "faceless"와 "fetish" 둘 다 암시. 전 플랫폼 통일 가능.

---

## 2. 세계관 (3가지 안)

### 안 A: "Lab-XX" (연구소)
> 미래의 비밀 연구소. 피험자들은 번호로만 불리며, 전신 라텍스 슈트와 마스크를 착용한 채 다양한 '실험'에 투입된다.
- 장점: 설정이 풍부, 스토리텔링 가능
- 단점: 다소 어두운 톤

### 안 B: "Hollow Collection" (패션 컬렉션)
> 얼굴 없는 마네킹이 된 모델들의 하이엔드 페티시 패션쇼. 각 시즌마다 새로운 '컬렉션'이 공개된다.
- 장점: 패션 감성, 시즌제 운영 가능, 밝은 톤 가능
- 단점: BDSM 요소 연결이 약간 부자연스러움

### 안 C: "The Vault" (금고/비밀 공간)
> 접근이 제한된 지하 공간. 입장자에게는 라텍스 슈트와 마스크가 지급되며, 안에서는 모든 정체성이 지워진다.
- 장점: 비밀스러운 분위기, 유료 콘텐츠 전환 시 "Vault access" 컨셉으로 자연스러움
- 단점: 클럽 느낌이 강할 수 있음

> **추천:** `안 A "Lab-XX"` 또는 `안 C "The Vault"` — 유료 전환 시 세계관 연결이 자연스러움.

---

## 3. 컬러 팔레트

### Primary (베이스)
| 컬러 | Hex | 용도 |
|------|-----|------|
| Obsidian Black | `#0A0A0A` | 라텍스 슈트 기본색 |
| Deep Charcoal | `#1A1A2E` | 배경, UI |

### Accent (포인트 — 2~3개 중 택 1)
| 세트 | 컬러 1 | 컬러 2 | 분위기 |
|------|--------|--------|--------|
| **Neon Toxic** | Hot Pink `#FF1493` | Neon Green `#39FF14` | 사이버펑크, 자극적 |
| **Clinical** | Ice Blue `#00D4FF` | White `#F0F0F0` | 연구소, 차가운 |
| **Luxury** | Gold `#FFD700` | Crimson `#DC143C` | 고급, 에로틱 |
| **Cyber Orange** | Orange `#FF6600` | — | 기존 이미지(37-38번) 스타일 계승 |

> **추천:** 기존 생성물(37-38번)의 **블랙+오렌지** 조합이 이미 강렬하고 차별화됨. `Cyber Orange` 세트로 시작하되, 시리즈별 악센트 변주 가능.

---

## 4. 마스크 타입 (시리즈별)

| 시리즈 | 마스크 타입 | 노출도 | Phase |
|--------|------------|--------|-------|
| **Series A: Sealed** | 풀페이스 가스마스크 (눈도 가림) | 최소 | Phase 1 |
| **Series B: Gaze** | 하프마스크 (눈만 노출, 입 가림) | 중간 | Phase 1 |
| **Series C: Silent** | 볼개그 + 블라인드폴드 | BDSM | Phase 2 |
| **Series D: Doll** | 키구루미 마스크 (무표정 인형 얼굴) | 중간 | Phase 2 |
| **Series E: Hood** | 라텍스 후드 (전체 커버) | 최소 | Phase 2 |

---

## 5. 체형 가이드라인

| 요소 | 규칙 | 프롬프트 키워드 |
|------|------|-----------------|
| 연령 | Mature adult only | `mature_female`, `adult`, `woman` |
| 체형 | Voluptuous, athletic | `voluptuous`, `curvy`, `athletic_build` |
| 신장 | Tall (170cm+) 느낌 | `tall`, `long_legs` |
| 네거티브 | 미성년 연상 금지 | Neg: `child`, `loli`, `flat_chest`, `school_uniform` |

---

## 6. 배경 세트 (3종 순환)

| 세트 | 설명 | 프롬프트 키워드 |
|------|------|-----------------|
| **Lab** | 하얀 타일벽, 형광등, 스테인리스 장비 | `laboratory`, `white_tiles`, `fluorescent_light`, `sterile` |
| **Dungeon** | 콘크리트 벽, 쇠사슬, 어두운 조명 | `dungeon`, `concrete_wall`, `chains`, `dim_light` |
| **Neon** | 사이버펑크 거리, 네온사인, 비 | `cyberpunk`, `neon_lights`, `rain`, `night_city` |

---

## 7. 워터마크 사양

| 요소 | 사양 |
|------|------|
| 위치 | 이미지 우하단 |
| 형태 | 계정명 텍스트 (`@hollow_doll` 또는 선택된 계정명) |
| 투명도 | 30~40% 반투명 |
| 크기 | 이미지 가로의 15~20% |
| 폰트 | 산세리프, 가는 두께 (예: Montserrat Light) |

---

*이 문서는 Phase 0 브랜드 킷 초안입니다. 사용자 확인 후 확정합니다.*
