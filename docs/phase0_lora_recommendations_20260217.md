# Phase 0 — CivitAI LoRA 추천 리포트
**Date:** 2026-02-17

---

## 베이스 모델 추천

**1순위: WAI Illustrious v16** (이미 설치됨) — NSFW 특화 파인튜닝, Illustrious LoRA 생태계 호환
**2순위: Pony Diffusion V6** (이미 설치됨) — LoRA 생태계 가장 풍부, 페티시 태그 방대

---

## 다운로드 우선순위

### 라텍스/샤이니 LoRA

| # | 이름 | CivitAI ID | 호환 | 용량 | 설명 |
|---|------|-----------|------|------|------|
| 1 | **Shiny Clothes and Skin** | [663904](https://civitai.com/models/663904) | Illustrious | ~144MB | 라텍스/오일/젖은피부/가죽 통합 |
| 2 | **Proper Latex Catsuit** | [1445079](https://civitai.com/models/1445079) | Illustrious | ~144MB | 전신 캣수트 + 가스마스크 바리언트 |
| 3 | **Glossy Latex Bodysuit** | [1279304](https://civitai.com/models/1279304) | IL + Pony | ~144MB | 글로시 바디수트, trigger: `glossy latex bodysuit` |
| 4 | **Transparent Latex** | [337681](https://civitai.com/models/337681) | Illustrious | ~100MB | 투명/반투명 라텍스 |
| 5 | **Glossy Latex Body Harness** | [2361346](https://civitai.com/models/2361346) | Illustrious | ~100MB | 하네스 |
| 6 | **Glossy Skin** | [1032320](https://civitai.com/models/1032320) | IL + Pony | ~100MB | 피부 광택 보조 (병용 시너지) |

### 가스마스크/페이스마스크

| # | 이름 | CivitAI ID | 호환 | 설명 |
|---|------|-----------|------|------|
| 1 | **Polyhedron Gas Mask** | [501166](https://civitai.com/models/501166) | SDXL 전체 | 가스마스크 전문, NSFW 지원 |
| 2 | Proper Latex Catsuit | 1445079 | Illustrious | 가스마스크 바리언트 포함 (위와 중복) |

### BDSM/본디지

| # | 이름 | CivitAI ID | 호환 | 설명 |
|---|------|-----------|------|------|
| 1 | **Harness Panel Gag** | [1209663](https://civitai.com/models/1209663) | IL/Pony/XL | 패널 갭, 3버전 제공 |
| 2 | **Duct Tape Gag/Blindfold** | [1894680](https://civitai.com/models/1894680) | Illustrious | 갭+블라인드폴드 동시 |
| 3 | **Transparent Blindfold** | [798480](https://civitai.com/models/798480) | IL + Pony | 투명 블라인드폴드 |
| 4 | **Bondage: Ballgagged** | [2327335](https://civitai.com/models/2327335) | Illustrious | 볼갭 전문 |
| 5 | **Clothing: Bondage Pack** | [2220375](https://civitai.com/models/2220375) | Illustrious | 본디지 의상 통합 팩 |

---

## 실전 LoRA 조합 예시

```
# 전신 라텍스 + 가스마스크
<lora:shiny_clothes_skin_latex:0.7>
<lora:proper_latex_catsuit:0.8>
prompt: 1girl, latex catsuit, gas mask, shiny, glossy, full body

# BDSM 본디지 + 갭
<lora:glossy_latex_body_harness:0.7>
<lora:harness_panel_gag:0.8>
prompt: 1girl, body harness, panel gag, latex, restrained

# 기존 latex_huger + 신규 LoRA 병용
<lora:latex_huger_c7:0.6>
<lora:shiny_clothes_skin_latex:0.5>
prompt: 1girl, latex bodysuit, shiny, glossy skin
```

**LoRA 병용 규칙:**
- 개별 강도: 0.6~0.8
- 복수 LoRA 총합: 1.5 이하 유지
- CivitAI 계정 로그인 + NSFW 필터 해제 필요

**총 다운로드 용량:** ~1.2~1.5 GB (10개 기준) — 디스크 여유 170GB로 충분.
