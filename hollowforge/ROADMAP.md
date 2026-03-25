# HollowForge Roadmap

## 현황 스냅샷 (2026-03-25 기준)

| 항목 | 상태 |
|------|------|
| **완료/진행 페이즈** | Phase 1~8 완료, character canonical stack 운영 반영, Prompt Factory/Animation workflow 유지, publish automation은 아직 미착수 |
| **생성 누계** | **2,108건 생성 / 2,097건 완료 / 11건 실패** |
| **Favorites** | **1,140건 즐겨찾기** |
| **Quality AI 분석** | 748건 분석 완료 (`quality_score`, `quality_ai_score`, `hand_count`) |
| **스택** | FastAPI + React 19 + Tailwind v4 + SQLite + ComfyUI |
| **체크포인트** | WAI Illustrious 계열, illustrij, hassaku, prefect, LTX 계열 실험 자산 외 |
| **LoRA / 프로필** | LoRA 프로필 45개 |
| **ADetailer** | YOLO face_yolov8n.pt (ultralytics 8.4.14) |
| **접근** | `https://sec.hlfglll.com` (Cloudflare Zero Trust) |
| **전략 문서** | `docs/LAB451_EXECUTION_ROADMAP_20260310.md`, `docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`, `docs/HOLLOWFORGE_NATURAL_LANE_20260322.md` |
| **Prompt Factory** | direction pack + creative autonomy + checkpoint preference + preview reuse queue + timeout hardening 반영 |
| **Animation** | animation jobs 7건 / completed 6건 / failed 1건, 마지막 실행 2026-03-13, 로컬 preview lane `sdxl_ipadapter_microanim_v2` 유지 |
| **Marketing AI** | OpenRouter 기반 caption/publishing route는 준비됨. 실제 `caption_variants`/`publish_jobs` 실행 데이터는 아직 0건 |
| **Character Stack** | 12 characters / 48 version recipes (`still_default`, `canonical_still`, `canonical_natural`, `animation_anchor`) |
| **Ready Queue** | `publish_approved=1` 71건 / rejected 4건 / active queue 0건 |
| **현재 운영 배치** | 최근 실행은 `canonical_natural` 계열 benchmark 잔여분이며, 현재 `queued/running` generation은 없음 |

### 다음 우선순위 (여기서부터 재개)

#### [즉시] 애니메이션/운영 계약 유지
1. **로컬 preview lane 유지** — `sdxl_ipadapter_microanim_v2`를 contract validation과 rough review에만 사용
2. **서버 worker 이행 준비** — 같은 `request_json`/callback 계약으로 stronger GPU worker 배치
3. **Animation smoke 운영화** — preflight + smoke script를 서버 base URL 기준으로 그대로 재사용

#### [다음] 캐릭터 중심 생산 구조 전환
4. **Character / Episode schema 추가** — `characters`, `character_versions`, `episodes`, `storyboard_shots`
5. **Prompt Factory lineage 연결** — character-linked batch, direction pack 재사용, shot-pack mode
6. **Ready Queue Ops UI** — `publish_jobs` 생성, 캡션 승인, platform fit 메타데이터 부여

#### [이후] 런치/배포 고도화
7. **플랫폼 운영 재개** — SubscribeStar / Pixiv / Reddit 운영 플로우를 실제 발행기로 연결
8. **운영 가이드 + 백업 스크립트** — README, DB+이미지 백업 자동화
9. **Quality AI 개선** — WD14 한계 극복 위해 LAION Aesthetic Predictor 계열 검토

---

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

## Phase 6: Upscaler Pipeline — COMPLETED (2026-02-23)
- [x] 업스케일 API 엔드포인트
- [x] DB 스키마 확장 (upscaled_image_path, upscaled_preview_path, upscale_model)
- [x] ImageDetail 업스케일 UI (모델 선택 + 버튼 + 원본/업스케일 비교 뷰)
- [x] Gallery 카드에 업스케일 배지 표시
- [x] 업스케일 결과 별도 저장 (원본 유지, images/upscaled/{id}.png)
- [x] 브라우저용 프리뷰 (1920px JPEG) + 원본 PNG 다운로드 분리
- [x] CPU 타일 기반 업스케일러 구현 (spandrel, 백업용)
- [x] **Ultimate SD Upscale 워크플로우 통합** (2026-02-23)
  - build_upscale_workflow() → UltimateSDUpscale 타일 기반 GPU 노드로 교체
  - ComfyUI 미지원 시 CPU spandrel fallback 유지
  - denoise/steps 파라미터 API로 노출
  - 디렉토리 자동 생성 (StaticFiles 마운트 전 즉시 생성)
- [ ] Generate 폼에 업스케일 옵션 토글 (생성 시 자동 업스케일) → Phase 8으로 이동

## Infra: Auto-Start Stack (ComfyUI + Backend + Frontend) — COMPLETED (2026-02-18)
- [x] macOS launchd 자동 시작 구성 완료 (로그인 시 전체 스택 부팅)
  - `~/Library/LaunchAgents/com.mori.hollowforge.comfyui.pinokio.plist`
    - 실행: Pinokio ComfyUI (`$PINOKIO_COMFY_APP_DIR/env/bin/python main.py`)
    - 기본 해석: `PINOKIO_COMFY_APP_DIR`가 없으면 `PINOKIO_ROOT_DIR/api/comfy.git/app`, 그마저 없으면 워크스페이스 `pinokio/`를 자동 탐지
    - 포트: `127.0.0.1:8188`
    - 로그: `pinokio/api/comfy.git/logs/launchd_stdout.log`, `pinokio/api/comfy.git/logs/launchd_stderr.log`
  - `~/Library/LaunchAgents/com.mori.hollowforge.backend.plist`
    - 실행: HollowForge FastAPI (`uvicorn app.main:app --host 127.0.0.1 --port 8000`)
    - 포트: `127.0.0.1:8000` (로컬 전용 바인딩)
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
- [x] 보안 하드닝 (2026-02-18)
  - backend 바인딩을 `127.0.0.1:8000`로 제한 (직접 LAN 접근 차단)
  - FastAPI 정적 파일 공개 경로를 `/data/images|thumbs|workflows`로 제한
  - 생성 API 서버측 파라미터 상한 검증 추가 (steps/cfg/dimensions/clip_skip/LoRA strength)
  - nginx 보안 헤더(CSP 포함) + `/api` 요청 레이트리밋 적용

## Phase 5c: LoRA Guide & Data-Driven Tuning UX — COMPLETED (2026-02-18)
- [x] `GET /api/v1/loras/guide` 추가
  - 체크포인트-로라 아키텍처 정합 근거 + 로컬 생성 이력 기반 fit score 계산
  - LoRA별 권장 strength 구간(+low/base/high) 및 reverse(-start/-limit) 안내값 제공
  - LoRA 강도 상/하향 시 예상 변화 설명(`raise_effect`, `lower_effect`) 제공
- [x] `LoRA Guide` 프론트 페이지 추가 (`/lora-guide`)
  - 체크포인트 선택 시 호환 LoRA만 정렬 노출 + 근거(reason) 표시
  - 음수 strength 사용 가이드(카테고리별 시작값/한계값) 섹션 추가
  - `Total |strength|` 구간별 실제 썸네일 예시 자동 매핑 + Gallery 상세 이동 연결
- [x] Guide 성능/가시성 최적화 (2026-02-18)
  - `/api/v1/loras/guide` 120초 TTL 캐시 + `refresh=true` 강제 재계산 지원
  - 가이드 계산 대상 generations 스캔 상한 최적화 (`LIMIT 500`)
  - UI 필터 확장: category / sort / history-only / reason detail 토글
  - 헤더에 cache hit/ttl 및 마지막 갱신 시각 표시
- [x] 체크포인트 안전 필터링 (2026-02-18)
  - `/api/v1/system/models`가 video/non-image 체크포인트(WAN-I2V/SVD)를 자동 분리
  - Generate/Presets는 image-checkpoint만 노출, Gallery/Settings는 전체 목록 유지

---

## Phase 5d: Batch Generation + Quality Profile Automation — COMPLETED (2026-02-18)
- [x] 배치 생성 API 추가
  - `POST /api/v1/generations/batch`
  - `count`(2~24) 기준으로 seed 자동 증가(+1 기본) 큐잉
  - seed 범위 초과/호환성 오류 사전 검증
- [x] Generate UI 배치 실행 지원
  - Batch Count 입력 시 N장 연속 큐 처리
  - 우측 패널에 진행 수/실패 수/대기 수/seed 범위 표시
- [x] 체크포인트별 품질 프로필 자동 적용
  - `GET /api/v1/system/quality-profiles`
  - 체크포인트 선택 시 권장 steps/cfg/해상도/sampler/scheduler 자동 주입
  - 수동 모드에서 `Apply profile now` 지원
- [x] 프로덕션 프리셋 확장 (benchmark 기반)
  - `HF Main - Series E Hood Signature`
  - `HF Main - Series C Silent Neon`
  - `HF Main - Series B Gaze Focus`
  - 마이그레이션: `backend/migrations/005_popular_presets.sql`
- [x] 글로벌 큐 인디케이터 확장 (2026-02-18)
  - 좌측 하단 `Generating...` 클릭 시 현재 큐를 펼침 리스트로 표시
  - 항목별 상태/체크포인트/seed/steps/해상도/elapsed/id 노출
  - 동일 영역에서 즉시 `Cancel` 실행 가능
  - 상단 Quick Cancel(running 우선) + 리스트 행 단위 개별 Cancel 지원

---

## Phase 5e: Model-Aware Prompt Template System — COMPLETED (2026-02-18)
- [x] 모델별 프롬프트 템플릿 API 추가
  - `GET /api/v1/system/prompt-templates`
  - 체크포인트 아키텍처(SDXL/SD1.5/FLUX) 기반으로 positive/negative 템플릿 분리 제공
  - checkpoint별 기본 템플릿 ID + `{subject}`, `{scene}`, `{pose}` 등 변수 가이드 제공
- [x] Generate 페이지 템플릿 적용 UX 추가
  - 체크포인트 선택 시 해당 모델 템플릿 자동 로드
  - Positive/Negative 각각 선택 적용 + `Replace`/`Append` 모드 지원
  - 적용 후 기존 Prompt/Negative Prompt textarea에서 바로 편집 가능한 워크플로우 유지
- [x] LoRA Guide 페이지에 모델별 프롬프트 전략 섹션 추가
  - 모델별 프롬프트 구분이 결과(재현성/안정성)에 미치는 영향 설명
  - 올바른 사용 순서(체크포인트 → 템플릿 → LoRA 튜닝 → 미세 편집) 안내
  - 활성 체크포인트 기준 추천 Positive/Negative 템플릿 실시간 노출

## Phase 6b: Export Pipeline — COMPLETED (2026-02-23)
- [x] `POST /api/v1/export` 엔드포인트 (플랫폼별 리사이즈 + 워터마크 + ZIP 스트리밍)
  - 플랫폼 규격: Fanbox 1200px / Fansly 1080px / Twitter 1280px / Pixiv 2048px / Custom 원본
  - JPEG 변환 (RGBA→RGB), LANCZOS 리사이즈, 플랫폼별 quality 설정
  - apply_watermark: watermark_service 연동, asyncio.to_thread 비동기 처리
  - include_originals: 원본 PNG도 zip에 포함 옵션
  - Content-Disposition: `export_{platform}_{timestamp}.zip`
- [x] `ExportRequest` Pydantic 모델 추가 (1~100개, platform Literal, apply_watermark, include_originals)
- [x] Gallery 다중 선택 모드 (Select 버튼 토글, 체크박스 오버레이, 선택 수 표시)
- [x] ExportModal 컴포넌트 (플랫폼/규격 선택, 워터마크/원본 토글, blob 다운로드, 로딩 스피너)

## Phase 7: Polish + Production Readiness — COMPLETED (2026-02-24)
- [x] Gallery 무한 스크롤 (useInfiniteQuery + IntersectionObserver) — 2026-02-23 완료
- [x] 이미지 라이트박스 (Portal 기반 오버레이, ESC/화살표 키 내비게이션) — 2026-02-23 완료
- [x] Toast 알림 시스템 (sonner, dark/richColors) — 2026-02-24 완료
  - Gallery 삭제, Generate 큐잉, ImageDetail 후처리(Upscale/ADetail/Hires.fix), Export 각 toast 연동
- [x] 빈 상태(empty state) 컴포넌트 — 2026-02-24 완료
  - Gallery, Collections, Scheduler, Presets 각 페이지 적용
- [x] 메타데이터 내보내기 (CSV/JSON bulk export) — 2026-02-24 완료
  - `GET /api/v1/export/metadata?format=csv|json&limit=500`
  - UTF-8 BOM CSV (Excel 호환), JSON `{count, generated_at, items}`
  - Settings 페이지 내보내기 UI (blob 다운로드, toast 연동)
- [x] favicon + PWA manifest — 2026-02-24 완료
  - `public/favicon.svg` (violet hexagon), `public/manifest.json`, index.html 메타 태그

## Phase 6d: Hires.fix — COMPLETED (2026-02-23)
- [x] `build_hiresfix_workflow()`: LoadImage → VAEEncode → LatentUpscaleBy → KSampler(denoise) → VAEDecode → SaveImage
- [x] `POST /api/v1/generations/{id}/hiresfix` (queue 기반, upscaled 우선 source)
- [x] DB 마이그레이션 `009_hiresfix.sql` (hiresfix_path 컬럼)
- [x] HiresFixRequest 모델 (scale_factor 1.1~2.0, denoise 0.2~0.85)
- [x] ImageDetail 페이지 "Hires.fix" 버튼 + Scale/Denoise 고급 옵션 + 결과 표시
- [x] gallery/collections 응답 및 삭제 연동

## Phase 6c: ADetailer (Face Fix) — COMPLETED (2026-02-24, upgraded)
- [x] YOLO face detection (face_yolov8n.pt, ultralytics 8.4.14) 우선, haarcascade fallback — 2026-02-24 업그레이드
- [x] OpenCV haarcascade face detection (frontal + profile, IOU dedupe, 30% bbox 확장)
- [x] 얼굴 마스크 생성 + ComfyUI `/upload/image`로 원본+마스크 업로드
- [x] `build_adetail_workflow()`: LoadImageMask → VAEEncodeForInpaint → KSampler(denoise=0.4) → VAEDecode → SaveImage
- [x] `run_adetail()` 비동기 서비스 (asyncio.to_thread 오프로드)
- [x] `POST /api/v1/generations/{id}/adetail` 엔드포인트 (queue 기반)
- [x] DB 마이그레이션 `008_adetail.sql` (adetailed_path 컬럼)
- [x] ImageDetail 페이지 "Fix Faces" 버튼 + 결과 표시 섹션
- [x] opencv-python-headless 4.13.0 backend venv 설치
- **Note**: Impact Pack(FaceDetailer) 없이 구현. 얼굴 정면 탐지 한계 있음. Impact Pack 설치 시 품질 대폭 향상 가능.

## Phase 6e: Night Batch Scheduler — COMPLETED (2026-02-23)
- [x] `scheduled_jobs` DB 테이블 (마이그레이션 `010_scheduler.sql`)
- [x] `SchedulerService`: APScheduler 3.x AsyncIOScheduler + CronTrigger
  - FastAPI lifespan 통합 (startup start / shutdown stop)
  - DB의 enabled job 자동 로드 + CronTrigger 등록
  - `_run_job`: preset 파싱 → GenerationCreate → queue_generation 반복
  - `last_run_at`, `last_run_status` DB 업데이트
  - APScheduler 미설치 시 graceful fallback
- [x] REST API: `GET/POST/PUT/DELETE /api/v1/scheduler/jobs` + `POST /{id}/run` (즉시 실행)
- [x] `ScheduledJobCreate/Update/Response` Pydantic 모델
- [x] Scheduler 페이지 (`/scheduler`): 작업 목록, Add Job 모달, 활성 토글, Run Now
- [x] 사이드바에 "Scheduler" 메뉴 (시계 아이콘) 추가
- [x] `apscheduler<4` backend venv 설치

## Phase 8: Advanced Features — COMPLETED (2026-02-24)
- [x] 배치 생성 (한 번에 N장, 시드 자동 증가) — 2026-02-18 완료
- [x] 모델별 프롬프트 템플릿(positive/negative 분리 + 변수 가이드) — 2026-02-18 완료
- [x] 이미지 비교 뷰 (A/B 슬라이더) — 2026-02-24 완료
  - `CompareView.tsx`: Portal 전체화면, clipPath 슬라이더 드래그(마우스/터치), ESC 닫기
  - ImageDetail: upscaled/adetailed/hiresfix 결과 존재 시 "비교 보기" 버튼 + 드롭다운
- [x] LoRA 프로필 CRUD — 2026-02-24 완료
  - Backend: `POST/GET/PUT/DELETE /api/v1/loras/{id}` (UUID 생성, 삭제 시 mood_mappings 정리)
  - Frontend: `LoraManager.tsx` (카테고리 그룹, Add/Edit/Delete 모달, strength 슬라이더, checkpoint 다중선택)
- [x] Mood mapping CRUD — 2026-02-24 완료
  - Backend: `backend/app/routes/moods.py` (`GET/POST/PUT/DELETE /api/v1/moods`)
  - Frontend: `MoodManager.tsx` (테이블, LoRA 다중선택, prompt additions)
- [x] 생성 히스토리 타임라인 — 2026-02-24 완료
  - Backend: `GET /api/v1/gallery/timeline` (일별/체크포인트/시간대/streak 통계)
  - Frontend: `Timeline.tsx` (히트맵, SVG 일별 차트, 체크포인트 분포, 24시간 분포, 7/30/90일 선택)
- [x] 다중 체크포인트 벤치마크 모드 — 2026-02-24 완료
  - Backend: `backend/app/routes/benchmark.py` + `migrations/011_benchmark.sql`
  - API: `POST /api/v1/benchmark/run`, `GET/DELETE /api/v1/benchmark/jobs/{id}`
  - Frontend: `Benchmark.tsx` (폼, 체크포인트 다중선택, 결과 비교 그리드)
- [ ] ComfyUI 워크플로우 시각화 (JSON → 그래프) — Phase 9으로 이동

## Phase 9: BytePlus Video Integration — IN PROGRESS (2026-02-24)
- [x] BytePlus API 클라이언트 (`byteplus_client.py`) — DUMMY/REAL 자동 전환, AK/SK 환경변수로 라이브 전환
- [x] **DreamActor M2.0** — 정적 이미지 + 템플릿 영상 → 모션 합성 (720P 25FPS MP4)
  - Backend: `POST /api/v1/generations/{id}/dreamactor` + `GET .../dreamactor/status`
  - 폴링 기반 비동기 처리 (RTF 18 기준 ~3분/10초 영상)
  - DB 마이그레이션 `012_dreamactor.sql`
  - Frontend: `DreamActorPanel.tsx` — ImageDetail 내 "Animate Character" 패널 + 5초 폴링 + 진행바
- [x] **Seedance 2.0** — 멀티모달 (이미지×9 + 영상×3 + 오디오×3 + 텍스트) → 영상 생성
  - Backend: `POST /api/v1/seedance/jobs` + `GET/DELETE /api/v1/seedance/jobs/{id}` + `GET /api/v1/seedance/jobs` (목록)
  - DB 마이그레이션 `013_seedance.sql`
  - Frontend: `SeedanceStudio.tsx` — 독립 페이지, @ 멘션 시스템, 파일 유효성 검사, 폴링, 결과 플레이어
  - 사이드바 "Seedance Studio" 메뉴 추가
- [x] 공유 `VideoPlayer.tsx` 컴포넌트
- [ ] BytePlus AK/SK 발급 후 BYTEPLUS_AK/BYTEPLUS_SK 환경변수 설정 → 라이브 전환
- [ ] DreamActor 결과 Gallery 통합 (영상 썸네일 + 배지)
- [ ] Seedance 결과 Gallery 통합

### Phase 9b: Local/Remote Animation Worker Contract — IN PROGRESS (2026-03-13)
- [x] `animation_jobs` 기반 HollowForge ↔ worker dispatch/callback 계약 정리
- [x] `lab451-animation-worker` canonical runtime 정리
  - 로컬: `run_local_animation_worker.sh`
  - 서버: `run_server_animation_worker.sh`
  - 레거시: `run_local_ltxv_worker.sh`는 호환 alias로 유지
- [x] 로컬 검증 도구 추가
  - `backend/scripts/check_local_animation_preflight.py`
  - `backend/scripts/launch_animation_preset_smoke.py`
- [x] `LTX` 계열 로컬 실험 완료
  - `ltxv_2b_fast`, `ltxv_portrait_locked`, `ltxv_character_lock_v2`
  - 결론: 모션 프로브로는 유효하지만 캐릭터 동일성 유지용 메인 lane으로는 부적합
- [x] identity-first preview lane 검증 완료
  - `sdxl_ipadapter_microanim_v1`: 동일성 양호, 모션 약함
  - `sdxl_ipadapter_microanim_v2`: 현재 권장 로컬 preview lane, 동일성 양호, 모션은 preview-grade
- [x] 서버 이행 원칙 문서화
  - 같은 preset / `request_json` / callback 계약 유지
  - 더 강한 GPU worker나 다른 model family는 worker backend 아래에서 교체
- [ ] 서버 GPU worker에 canonical workflow 이행
- [ ] release-grade motion / fidelity backend 확정
- [ ] animation result gallery integration 및 운영 지표 연결

### API 키 연결 방법 (BytePlus 발급 후)
```bash
# backend/.env 또는 launchd plist EnvironmentVariables에 추가
BYTEPLUS_AK=your_access_key
BYTEPLUS_SK=your_secret_key
# 재시작하면 자동으로 REAL 모드로 전환됨
```

---

## 외부 API 키 레퍼런스 (전체)

> 어떤 기능에 어떤 API 키가 필요한지 빠르게 확인하는 섹션.
> 키는 `hollowforge/backend/.env`에 설정. launchd plist `EnvironmentVariables`에도 추가 필요.

| 기능 | 환경변수 | 발급처 | 필수 여부 | 비고 |
|------|----------|--------|-----------|------|
| **Caption AI** (이미지→SNS 캡션) | `OPENROUTER_API_KEY` | https://openrouter.ai | **필수** | 미설정 시 `/api/tools/generate-caption*` 엔드포인트 오류 |
| Caption AI 모델 선택 | `MARKETING_MODEL` | — | 선택 | default: `x-ai/grok-2-vision-1212` |
| 대체 모델 예시 | — | — | — | `anthropic/claude-3.5-sonnet`, `google/gemini-flash-1.5` |
| **DreamActor M2.0** (영상 합성) | `BYTEPLUS_AK` + `BYTEPLUS_SK` | https://www.volcengine.com | 필수 (영상 기능) | 미설정 시 DUMMY 모드 (가짜 응답) |
| **Seedance 2.0** (영상 생성) | `BYTEPLUS_AK` + `BYTEPLUS_SK` | 위와 동일 | 필수 (영상 기능) | 위와 동일 |

### 설정 예시 (`backend/.env`)
```bash
# Marketing Automation (Phase 11)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxx
MARKETING_MODEL=x-ai/grok-2-vision-1212   # 선택 (기본값)

# BytePlus Video (Phase 9)
BYTEPLUS_AK=your_access_key
BYTEPLUS_SK=your_secret_key
```

### launchd plist에 키 추가하는 법
```bash
# com.mori.hollowforge.backend.plist 의 EnvironmentVariables 딕셔너리에 추가 후:
launchctl kickstart -k gui/$(id -u)/com.mori.hollowforge.backend
```

## Quality AI: WD14 + MediaPipe — COMPLETED (2026-02-27)
- [x] WD14 SwinV2 Tagger v3 (ONNX) — 콘텐츠 태그 기반 품질 추정
- [x] MediaPipe HandLandmarker — 손가락 이상 감지 파이프라인 운영
- [x] `POST /api/v1/quality/analyze/{id}` + `analyze-batch` + `GET /api/v1/quality/report`
- [x] Quality AI 페이지 (`/quality`) — 통계 카드, 히스토그램, Top 10 bad tags, 이미지 그리드 + 콜렉션 연동
- [x] **버그 수정 (2026-02-27)**: `_compute_ai_score` 고정 80 반환 문제
  - 원인: WD14는 콘텐츠 태거 (quality 태그를 시각적으로 검출 불가)
  - 수정: 태그 다양성(tag count)을 품질 프록시로 사용 → 점수 범위 73~80 (개선)
  - 현실적 한계: 이 니치(페이스리스 라텍스)는 WD14 검출 태그가 10~15개로 제한적
  - **실용 권고**: blended `quality_score` (수동 40% + AI 60%)가 실질 선별 기준, AI 단독 점수는 보조
- [x] 누적 분석 스냅샷 갱신 (2026-03-13)
  - `quality_score`/`quality_ai_score`/`hand_count` 분석 완료: 2,178건
  - 손가락 이상 검출: 304건
  - 평균 `quality_score`: 84.15
- **현재 포트폴리오 스냅샷 (2026-03-13)**: score≥80 clean 1,461장 / score≥75 clean 1,592장

## 시장 분석 스프린트 — COMPLETED (2026-02-27)
- [x] 플랫폼별 AI 콘텐츠 허용 여부 조사
  - ❌ 차단: Pixiv FANBOX, Fantia, DLsite, Patreon (AI fetish), Gumroad
  - ✅ 허용: SubscribeStar.adult (메인 수익화), Pixiv (발견, 검열 필수), r/AIHentai, Rule34
- [x] 니치 콘텐츠 패턴 분석 (인기 구도, 태그 전략, 게시 빈도)
- [x] 전략 문서 v1.2 업데이트 (`docs/project_strategy_v1.1_20260217.md`)
  - SubscribeStar.adult → 메인 수익화 ★★★
  - 콘텐츠 이중화 전략: Pixiv 검열 버전 / SubscribeStar 무검열 버전
  - 언어 전략: 영어 우선 + 일본어 보조
- [x] 내부 콘텐츠 감사 완료 (모델별 성과 분석)
  - 상위 모델: illustrij_v20(75.4), hassakuXLIllustrious_v34(74.8), prefectIllustriousXL_v70(73.0)
  - WAI v160 (메인 사용): 68.5점 — 비중 줄이기 권장

## Phase 11: Marketing Automation — COMPLETED (2026-03-02)

### Phase 11a: Caption AI (Image → SNS 캡션 생성기)
- [x] **Backend**: `POST /api/tools/generate-caption` — 이미지 업로드 → base64 인코딩 → OpenRouter 비전 모델 호출
- [x] **Backend**: `POST /api/tools/generate-caption-by-id` — `generation_id`로 DB 조회 → 파일시스템에서 이미지 읽기 → OpenRouter 호출 (프론트→백 이미지 전송 불필요)
- [x] **라우터**: `backend/app/routes/marketing.py` — `marketing_router` FastAPI 등록
- [x] **Config**: `OPENROUTER_API_KEY`, `MARKETING_MODEL` 환경변수 추가 (`backend/app/config.py`)
- [x] **AI 페르소나**: "Head Archivist of Lab-451" — 임상적 디스토피아 기록 톤, 15~20개 해시태그, 엄격한 JSON 출력 (`{ story, hashtags }`)
- [x] **Frontend**: `CaptionGenerator.tsx` — 드래그앤드롭 dropzone, 이미지 미리보기, 결과 편집 textarea, "Copy All" 버튼
- [x] **Frontend**: `Marketing.tsx` — `/marketing` 경로 페이지 (사이드바 TOOLS 그룹 추가)

### Phase 11b: Favorites Gallery + Caption Modal
- [x] **Frontend**: `Favorites.tsx` — `/favorites` 경로, `useInfiniteQuery` + `favorites: true` 필터, 하트 오버레이 그리드
- [x] **Frontend**: `CaptionModal.tsx` — 좌: 이미지 미리보기 / 우: 캡션 생성 패널, ESC/외부클릭 닫기
- [x] **API 클라이언트**: `generateCaptionById(generationId)` → `CaptionResponse { story, hashtags }` (`api/client.ts`)
- [x] **App.tsx**: `/marketing`, `/favorites` 라우트 + 사이드바 네비게이션 항목 추가
  - Caption AI: `wand-sparkles` 아이콘
  - Favorites: `heart` 아이콘

### 사용 방법
1. Gallery에서 이미지 하트 표시 → Favorites 탭에서 모아보기
2. Favorites에서 이미지 클릭 → CaptionModal 열림
3. "Generate Caption" → Lab-451 페르소나로 캡션 + 해시태그 자동 생성
4. 편집 후 "Copy All" → SNS 직접 게시

### 필요한 API 키
- **`OPENROUTER_API_KEY`** — OpenRouter (https://openrouter.ai) 발급 필수
- **`MARKETING_MODEL`** — 선택적 (default: `x-ai/grok-2-vision-1212`)

### Phase 11c: Prompt Factory Direction Layer — COMPLETED (2026-03-12)
- [x] `tone`, `heat_level`, `creative_autonomy`, `direction_pass_enabled` 제어 추가
- [x] `direction_pack` preview/edit/reuse 흐름 추가
- [x] `direction_pack_override`로 human-in-the-loop 재사용 지원
- [x] checkpoint preference 시스템 추가
  - per-checkpoint `default / prefer / force / exclude`
  - 설정 UI에서 검색/필터/저장/리셋 가능
- [x] benchmark cue extraction + preview 기반 prompt shaping 강화
- [x] `generate-and-queue` 기반 star-scout 스타일 탐색 흐름 검증
- [x] preview timeout / provider readiness / queue UX 안정화 (2026-03-13)
  - backend benchmark snapshot bug 수정
  - nginx / Vite proxy timeout 300s로 상향
  - preview 결과 재사용 queue 흐름과 상태 표시 강화
- [x] safe glamour audition batch 운영 검증 (2026-03-13)
  - direct generation batch 방식으로 `20 characters x 5 seeds = 100 images` live queue 등록
  - 태그: `audition`, `safe_glamour`, `editorial_seductive`, `20260313`, `AUD001`~`AUD020`
- [ ] 최근 scouting 결과에 대한 hit-rate / 반복도 / benchmark fidelity 운영 검증
- [ ] checkpoint별 production default 확정
- [ ] provider formatting failure / retry recovery 관측 강화

---

## Phase 10: Agency Handover — FUTURE
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
        +→ OpenRouter (Prompt Factory / Caption AI)
        +→ Animation Worker (local or remote)
                |
                +→ ComfyUI / video backend
                +→ callback → HollowForge animation_jobs
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
