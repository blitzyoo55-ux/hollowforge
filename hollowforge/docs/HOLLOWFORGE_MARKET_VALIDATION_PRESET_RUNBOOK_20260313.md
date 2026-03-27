# HollowForge Market Validation Preset Runbook

작성일: 2026-03-13
대상: HollowForge Prompt Factory / Batch Import

관련 파일:
- `HOLLOWFORGE_MARKET_VALIDATION_PHASE1_DIRECT_IMPORT_20260313.csv`
- `HOLLOWFORGE_MARKET_VALIDATION_PHASE1_QUEUE_PAYLOAD_20260313.json`
- `HOLLOWFORGE_MARKET_VALIDATION_REQUEST_PRESETS_20260313.json`
- `HOLLOWFORGE_MARKET_VALIDATION_MATRIX_20260313.md`

## 0. 목적

- Phase 1 시장 검증을 실제 발주 가능한 형태로 고정한다.
- `1 batch = 25 images` 원칙을 유지한다.
- 이번 산출물은 `12 packs x 25 images = 300 images`를 바로 만들 수 있다.

## 1. 어떤 파일을 언제 쓰는가

### CSV

- 용도: Batch Import 페이지에 바로 붙여 넣거나 업로드할 때
- 특징: `300 rows`, 각 행이 `1 generation`
- 구조: `12 packs x 5 prompt variants x 5 random-seed repeats`

### Queue Payload JSON

- 용도: `/api/tools/prompt-factory/queue` 또는 `/api/v1/tools/prompt-factory/queue`에 바로 POST할 때
- 특징: Prompt Factory 응답 스키마에 맞춰서 바로 큐에 넣을 수 있다.

### Request Presets JSON

- 용도: Prompt Factory Generate UI/API에서 pack별 preset을 불러 수동 검토 후 생성할 때
- 특징: direct queue보다 덜 고정적이지만, pack별 creative brief를 유지하기 쉽다.

## 2. Pack 범위

| Pack | Row Range | Images | Line |
|---|---:|---:|---|
| A1 | 1-25 | 25 | Line A - Original Beauty / Editorial / Luxury Editorial Baseline |
| A2 | 26-50 | 25 | Line A - Original Beauty / Editorial / Star Quality / Red Carpet Glam |
| A3 | 51-75 | 25 | Line A - Original Beauty / Editorial / Dark Romance / Elegant Drama |
| B1 | 76-100 | 25 | Line B - Alt / Goth / Non-IP Cosplay-coded / Alt Goth Core |
| B2 | 101-125 | 25 | Line B - Alt / Goth / Non-IP Cosplay-coded / Sci-fi Cosplay-coded |
| B3 | 126-150 | 25 | Line B - Alt / Goth / Non-IP Cosplay-coded / Occult Fashion |
| C1 | 151-175 | 25 | Line C - Fetish-adjacent Broad Appeal / Legwear / Heels / Choker |
| C2 | 176-200 | 25 | Line C - Fetish-adjacent Broad Appeal / Boots / Authority |
| C3 | 201-225 | 25 | Line C - Fetish-adjacent Broad Appeal / Harness / Accessory Tension |
| D1 | 226-250 | 25 | Line D - Latex / BDSM Premium / Latex Editorial Baseline |
| D2 | 251-275 | 25 | Line D - Latex / BDSM Premium / Signature Masked Latex |
| D3 | 276-300 | 25 | Line D - Latex / BDSM Premium / Power Dynamic Premium |

## 3. 권장 사용 순서

1. CSV 또는 queue payload로 Phase 1 300장을 한 번에 발주한다.
2. Pack별로 `favorite_rate`, `strong_pick_rate`, `character_seed_rate`를 기록한다.
3. 상위 4 packs만 남겨서 Phase 2로 넘긴다.
4. Phase 2에서는 각 winning pack의 25-row 블록을 두 번 복제하고 checkpoint만 교체한다.
5. Phase 3에서는 최종 2 packs만 남기고 `character_lock`, `environment_drift`, `intensity_ladder` 세 트랙으로 복제한다.

## 4. CSV 사용

Batch Import 페이지 헤더는 아래 형식을 기대한다.

```text
Set_No|Checkpoint|LoRA_1|Strength_1|LoRA_2|Strength_2|LoRA_3|Strength_3|LoRA_4|Strength_4|Sampler|Steps|CFG|Clip_Skip|Resolution|Positive_Prompt|Negative_Prompt
```

이번 CSV는 LoRA를 비워 둔 baseline 버전이다. 콘텐츠 축 반응을 먼저 보고, 이후 winning lane에만 LoRA를 얹는 것이 맞다.

## 5. JSON Queue 사용

예시:

```bash
curl -X POST http://127.0.0.1:8000/api/tools/prompt-factory/queue \
  -H 'Content-Type: application/json' \
  --data @docs/HOLLOWFORGE_MARKET_VALIDATION_PHASE1_QUEUE_PAYLOAD_20260313.json
```

## 5.1 Local Still-Image Smoke

대량 발주 전에는 실제 still-image lane이 살아 있는지 먼저 확인한다.

```bash
cd hollowforge/backend
./.venv/bin/python scripts/launch_generation_smoke.py --no-wait
```

위 명령은 `generation_id` 를 출력한다. 같은 ID로 완료까지 감시한다.

```bash
cd hollowforge/backend
./.venv/bin/python scripts/launch_generation_smoke.py --generation-id <generation_id>
```

운영 체크 포인트:

- checkpoint를 명시하지 않으면 `/api/v1/system/models` 의 첫 checkpoint를 사용한다.
- 성공 기준은 최종 상태가 `completed` 이고 `image_path` 가 채워지는 것이다.
- 생성 중에는 `/api/v1/generations/queue/summary` 로 running/queued 카운트를 함께 본다.
- smoke 태그는 기본값으로 `["smoke", "still-image"]` 가 들어간다.

## 6. 운영 메모

- 이번 버전은 `prefectIllustriousXL_v70.safetensors` 고정 baseline이다.
- negative prompt는 현재 HollowForge 기본값과 동일하다.
- `adult woman`, `original character`, `non-IP` 축을 유지하도록 직접 작성했다.
- `latex / bdsm`는 Phase 1 안에서 `Line D`로 검증하되, 코어 전체를 그 방향으로 몰지 않는다.
