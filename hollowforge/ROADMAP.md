# HollowForge Roadmap

## Phase 1: Backend Core — COMPLETED (2026-02-17)
- [x] FastAPI app scaffold, SQLite schema, migration
- [x] ComfyUI async client (httpx, benchmark_runner_v2 기반)
- [x] Generation API (POST → background worker → polling → complete)
- [x] System/health endpoints
- [x] Checkpoint/sampler/scheduler 목록 ComfyUI에서 동적 로드
- [x] Python 3.12 venv + dependencies

## Phase 2: React Frontend Scaffold + Basic Generation — COMPLETED (2026-02-17)
- [x] Vite + React + TypeScript + Tailwind CSS
- [x] Dark theme UI (gray-950 + violet accent)
- [x] Dashboard (recent generations, ComfyUI status, stats)
- [x] Generate page (form → API → progress polling)
- [x] Preset auto-load from query param (?preset=id)
- [x] LoRA selector with category grouping + strength slider
- [x] Mood chips → smart LoRA auto-select
- [x] Tags/Notes usage guide in GenerateForm + Settings page

## Phase 3: Gallery + Image Detail + Metadata — COMPLETED (2026-02-17)
- [x] Gallery grid with filter (checkpoint, tags, date, search)
- [x] Image Detail page (full metadata, workflow JSON)
- [x] Thumbnail auto-generation (512px, Pillow)
- [x] Delete functionality (DB + files)
- [x] Reproduce (exact/variation) endpoints

## Phase 4: Presets + Smart LoRA Engine — COMPLETED (2026-02-17)
- [x] Preset CRUD
- [x] Checkpoint dropdown (ComfyUI models) in preset form
- [x] Series A-E seed presets
- [x] Mood→LoRA mapping + /loras/select API
- [x] Category slots (style:1, eyes:1, material:0-1, fetish:0-2)
- [x] Strength cap 2.4 with proportional reduction

## Phase 4b: E2E Validation + CivitAI Reproduction — COMPLETED (2026-02-17)
- [x] CivitAI 이미지 메타데이터 추출 (API /api/v1/images)
- [x] LoRA 리소스 ID → 파일명 매핑 (CivitAI /api/v1/model-versions)
- [x] 누락 LoRA 다운로드 (iranon.safetensors 수동, auth 필요)
- [x] WAI Illustrious v14.0 + 4 LoRA 전체 재현 성공
- [x] v14 vs v16 체크포인트 버전 차이 검증

## Phase 5: UX Enhancement + Advanced Generation — COMPLETED (2026-02-17)
- [x] Models/LoRA 동기화 기능 (ComfyUI → DB 자동 등록)
  - Settings 페이지 "Sync from ComfyUI" 버튼
  - 새 LoRA 파일 자동 DB 등록 (display_name 자동 생성)
  - 체크포인트/LoRA/샘플러/스케줄러 목록 실시간 갱신
- [x] 생성 중 예상 시간(ETA) 표시
  - 동일 steps 기록 기반 평균 시간 계산 (3건 미만 시 전체 평균 fallback)
  - ProgressCard에 경과/예상 시간 + 프로그레스 바
- [x] 글로벌 생성 상태 인디케이터
  - 사이드바 하단에 활성 생성 표시 (어떤 페이지에서든 확인 가능)
  - 클릭 시 Generate 페이지 이동
  - 30분 이상 stale 항목 자동 필터링
- [x] 서버 재시작 시 stale generation 자동 정리 (queued/running → failed)
- [x] Generate 고급 파라미터 (Advanced Settings 토글)
  - CFG Scale, Steps, Sampler, Scheduler, Seed (주사위 랜덤), Clip Skip
  - Clip Skip → ComfyUI CLIPSetLastLayer 노드 자동 삽입
- [x] 이전 생성 설정 불러오기 + 재생성
  - ImageDetail: "Exact Regenerate" + "Edit & Regenerate" 버튼
  - Gallery/Dashboard 카드: hover 시 regenerate 아이콘
  - Generate 페이지 ?from={id}로 전체 설정 자동 채우기
  - source_id로 원본-재생성 관계 추적

---

## Phase 6: Upscaler Pipeline — IN PROGRESS
- [x] 업스케일 API 엔드포인트
  - POST /api/v1/generations/{id}/upscale
  - GET /api/v1/system/upscale-models (ComfyUI 모델 목록)
- [x] DB 스키마 확장 (upscaled_image_path, upscaled_preview_path, upscale_model)
- [x] ImageDetail 업스케일 UI (모델 선택 + 버튼 + 원본/업스케일 비교 뷰)
- [x] Gallery 카드에 업스케일 배지 표시
- [x] 업스케일 결과 별도 저장 (원본 유지, images/upscaled/{id}.png)
- [x] 브라우저용 프리뷰 (1920px JPEG) + 원본 PNG 다운로드 분리
- [x] CPU 타일 기반 업스케일러 구현 (spandrel, 백업용)
- [x] ComfyUI Ultimate SD Upscale 커스텀 노드 설치
- [ ] **NEXT**: Ultimate SD Upscale 워크플로우 통합
  - build_upscale_workflow() → 타일 기반 GPU 업스케일 노드로 교체
  - MPS(Apple Silicon) 아티팩트 없는 대형 이미지 업스케일
- [ ] Generate 폼에 업스케일 옵션 토글 (생성 시 자동 업스케일)
- **이슈**: ComfyUI 기본 ImageUpscaleWithModel → MPS에서 수평선 아티팩트 발생
- **해결**: Ultimate SD Upscale (타일 분할 GPU 처리)로 전환 예정

## Infra: Auto-Start Stack (ComfyUI + Backend + Frontend) — COMPLETED (2026-02-18)
- [x] macOS launchd 자동 시작 구성 완료 (로그인 시 전체 스택 부팅)
  - `~/Library/LaunchAgents/com.mori.hollowforge.comfyui.pinokio.plist`
    - 실행: Pinokio ComfyUI (`/Users/mori_arty/AI_Projects/pinokio/api/comfy.git/app/env/bin/python main.py`)
    - 포트: `127.0.0.1:8188`
    - 로그: `pinokio/api/comfy.git/logs/launchd_stdout.log`, `pinokio/api/comfy.git/logs/launchd_stderr.log`
  - `~/Library/LaunchAgents/com.mori.hollowforge.backend.plist`
    - 실행: HollowForge FastAPI (`uvicorn app.main:app --host 0.0.0.0 --port 8000`)
    - 포트: `0.0.0.0:8000`
    - 로그: `hollowforge/backend/logs/launchd_stdout.log`, `hollowforge/backend/logs/launchd_stderr.log`
  - `~/Library/LaunchAgents/com.mori.hollowforge.frontend.plist`
    - 실행: Vite dev server (`npm run dev -- --host 127.0.0.1 --port 5173`)
    - 포트: `127.0.0.1:5173`
    - 로그: `hollowforge/frontend/logs/launchd_stdout.log`, `hollowforge/frontend/logs/launchd_stderr.log`
- [x] `RunAtLoad` + `KeepAlive` 적용으로 터미널 종료와 무관하게 상시 유지
- [x] HollowForge health 기준 ComfyUI 연결 정상 검증 완료 (`comfyui_connected: true`)
- [x] 운영 이슈 대응 (2026-02-18): backend 재시작 루프 해결
  - 증상: 생성 실패 `Generation failed / Server restarted`
  - 원인: 중복 LaunchAgent (`com.hollowforge.backend` + `com.mori.hollowforge.backend`)가 동일 포트 `8000` 충돌
  - 조치: 구버전 라벨 `com.hollowforge.backend` bootout + plist 제거, 신버전 `com.mori.hollowforge.backend` 단일화
  - 검증: `launchctl` 상태 `running`, 단일 PID 리스닝, `/api/v1/system/health` = `healthy`

## Infra: Cloudflare Zero Trust Remote Access — COMPLETED (2026-02-18)
- [x] Cloudflare Tunnel + local nginx reverse proxy 구성 완료
  - public hostname: `https://sec.hlfglll.com`
  - tunnel ingress: `sec.hlfglll.com` -> `http://localhost:8080`
  - nginx upstream: `/api` + `/data` -> `127.0.0.1:8000`
- [x] launchd 상시 실행 구성
  - `~/Library/LaunchAgents/com.mori.hollowforge.nginx.cloudflare.plist`
  - `~/Library/LaunchAgents/com.mori.hollowforge.cloudflared.plist`
- [x] Cloudflare Access(Self-hosted) 로그인 보호 적용
  - 앱: `HollowForge`
  - 정책: owner email allow + Google login
  - 상태: Google 로그인 후 정상 접근 확인
- [x] 보안 정리
  - 실토큰 파일 git 제외 (`deploy/cloudflared/.env.cloudflared`)
  - 토큰 로테이션 후 터널 재연결 검증 (`Registered tunnel connection`)

---

## Phase 7: Polish + Production Readiness — FUTURE
- [ ] 에러 처리 UX 개선 (toast notifications, retry buttons)
- [ ] 빈 상태(empty state) 일러스트 개선
- [ ] Gallery 무한 스크롤 (현재는 Load More 버튼)
- [ ] 이미지 라이트박스 (Gallery에서 클릭 시 오버레이)
- [ ] 메타데이터 내보내기 (CSV/JSON bulk export)
- [ ] favicon + PWA manifest

## Phase 8: Advanced Features — FUTURE
- [ ] 배치 생성 (한 번에 N장, 시드 자동 증가)
- [ ] 프롬프트 템플릿 변수 ({quality}, {character_name} 등)
- [ ] LoRA 프로필 CRUD (현재 DB seed만, UI 편집 없음)
- [ ] Mood mapping CRUD (현재 DB seed만)
- [ ] 이미지 비교 뷰 (A/B side-by-side)
- [ ] 생성 히스토리 타임라인
- [ ] ComfyUI 워크플로우 시각화 (JSON → 그래프)
- [ ] 다중 체크포인트 벤치마크 모드

## Phase 9: Agency Handover — FUTURE
- [ ] README + 운영 가이드 (비개발자용)
- [ ] Docker Compose (backend + frontend 원클릭 배포)
- [ ] 환경변수 설정 가이드 (.env.example)
- [ ] 백업/복원 스크립트 (DB + images)

---

## Architecture

```
React + Vite + Tailwind (localhost:5173)
        |
        v
FastAPI Backend (localhost:8000)
        |
        +→ SQLite (metadata, presets, LoRA mappings)
        +→ Local Storage (images/, thumbs/, workflows/)
        +→ ComfyUI HTTP API (localhost:8188)
```

## Quick Start

```bash
# Backend
cd hollowforge/backend
source .venv/bin/activate
uvicorn app.main:app --port 8000 --reload

# Frontend
cd hollowforge/frontend
npm run dev

# Open http://localhost:5173
```

## Operations (Auto-Start)

```bash
# 상태 확인
launchctl list | rg com.mori.hollowforge

# 전체 재시작
launchctl kickstart -k gui/$(id -u)/com.mori.hollowforge.comfyui.pinokio
launchctl kickstart -k gui/$(id -u)/com.mori.hollowforge.backend
launchctl kickstart -k gui/$(id -u)/com.mori.hollowforge.frontend
```
