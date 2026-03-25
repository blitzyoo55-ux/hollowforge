# HollowForge Git Commit Slicing Guide

기준일: 2026-03-25

## 1. 사실관계

- 실제 Git 저장소 루트는 `04_AI_Creative/nsfw-market-research/` 이다.
- `hollowforge/`는 별도 저장소가 아니라 위 저장소 안의 프로젝트 하위 트리다.
- remote는 아직 없다.
- 현재 작업트리는 "초기 staged 묶음" 위에 "후속 기능 wave"가 unstaged/untracked로 덧입혀진 상태다.

즉 지금 바로 한 번에 커밋하면, 시간축이 다른 작업이 섞인다.

## 2. 현재 구조 요약

### A. 이미 index에 올라가 있는 오래된 묶음

이 묶음은 상대적으로 초반 작업에 가깝다.

- 저장소 루트 benchmark / market research baseline
  - `README.md`
  - `config/target_tags.yaml`
  - `data/benchmark/`
  - `data/benchmark_v2/`
  - `docs/fetish_market_deep_analysis_20260217.md`
  - `docs/market_analysis_20260217.md`
  - `docs/market_analysis_v2_20260217.md`
  - `docs/phase0_*`
  - `requirements.txt`
  - `src/benchmark_runner.py`
  - `src/benchmark_runner_v2.py`
  - `src/full_tag_ranker.py`
  - `src/tag_collector.py`

- HollowForge 초기 app/scaffold + upscale/Vite baseline
  - `hollowforge/backend/app/config.py`
  - `hollowforge/backend/app/db.py`
  - `hollowforge/backend/app/routes/reproduce.py`
  - `hollowforge/backend/app/services/image_service.py`
  - `hollowforge/backend/app/services/upscaler.py`
  - `hollowforge/backend/app/services/workflow_builder.py`
  - `hollowforge/backend/migrations/002_clip_skip.sql`
  - `hollowforge/backend/migrations/003_upscale.sql`
  - `hollowforge/backend/migrations/004_upscaled_preview.sql`
  - `hollowforge/backend/requirements.txt`
  - `hollowforge/frontend/README.md`
  - `hollowforge/frontend/eslint.config.js`
  - `hollowforge/frontend/package*.json`
  - `hollowforge/frontend/src/components/LoraSelector.tsx`
  - `hollowforge/frontend/src/components/PresetCard.tsx`
  - `hollowforge/frontend/src/main.tsx`
  - `hollowforge/frontend/src/pages/Dashboard.tsx`
  - `hollowforge/frontend/src/pages/ImageDetail.tsx`
  - `hollowforge/frontend/src/pages/Presets.tsx`
  - `hollowforge/frontend/vite.config.ts`

주의:

- 위 파일들 중 일부는 이미 `AM` 또는 `MM` 상태다.
- 지금 커밋하면 "staged 버전"만 기록되고, 최신 수정은 작업트리에 남는다.

## 3. 바로 분리해야 하는 덩어리

### B. HollowForge production expansion

tracked 수정 + untracked 신규 파일이 동시에 얹혀 있다.

- backend core integration
  - `hollowforge/backend/app/main.py`
  - `hollowforge/backend/app/models.py`
  - `hollowforge/backend/app/routes/gallery.py`
  - `hollowforge/backend/app/routes/generations.py`
  - `hollowforge/backend/app/routes/loras.py`
  - `hollowforge/backend/app/routes/system.py`
  - `hollowforge/backend/app/services/comfyui_client.py`
  - `hollowforge/backend/app/services/generation_service.py`
  - `hollowforge/backend/app/services/lora_selector.py`

- frontend integration
  - `hollowforge/frontend/src/App.tsx`
  - `hollowforge/frontend/src/api/client.ts`
  - `hollowforge/frontend/src/components/GalleryGrid.tsx`
  - `hollowforge/frontend/src/components/GenerateForm.tsx`
  - `hollowforge/frontend/src/components/GlobalGenerationIndicator.tsx`
  - `hollowforge/frontend/src/pages/BatchImportPage.tsx`
  - `hollowforge/frontend/src/pages/Gallery.tsx`
  - `hollowforge/frontend/src/pages/Generate.tsx`
  - `hollowforge/frontend/src/pages/LoraGuide.tsx`
  - `hollowforge/frontend/src/pages/Settings.tsx`

이 덩어리는 feature별 path add보다 `git add -p`가 먼저 필요하다.

## 4. 추천 커밋 순서

아래 순서는 "가장 덜 위험한 slicing" 기준이다.

### Commit 1. Repo benchmark / market baseline

저장소 루트의 초기 benchmark/market research 자산만 커밋한다.

포함:

- `README.md`
- `config/target_tags.yaml`
- `data/benchmark/`
- `data/benchmark_v2/`
- `docs/fetish_market_deep_analysis_20260217.md`
- `docs/market_analysis_20260217.md`
- `docs/market_analysis_v2_20260217.md`
- `docs/phase0_*`
- `requirements.txt`
- `src/*.py`

보류:

- `.gitignore`
- `docs/project_strategy_v1.1_20260217.md`

이 둘은 staged/unstaged가 겹쳐 있어 별도 확인 후 커밋하는 편이 안전하다.

### Commit 2. HollowForge bootstrap + upscale baseline

초기 HollowForge 앱과 upscale/Vite scaffold만 별도로 커밋한다.

포함:

- `hollowforge/backend/app/config.py`
- `hollowforge/backend/app/db.py`
- `hollowforge/backend/app/routes/reproduce.py`
- `hollowforge/backend/app/services/image_service.py`
- `hollowforge/backend/app/services/upscaler.py`
- `hollowforge/backend/app/services/workflow_builder.py`
- `hollowforge/backend/migrations/002_clip_skip.sql`
- `hollowforge/backend/migrations/003_upscale.sql`
- `hollowforge/backend/migrations/004_upscaled_preview.sql`
- `hollowforge/backend/requirements.txt`
- `hollowforge/frontend/README.md`
- `hollowforge/frontend/eslint.config.js`
- `hollowforge/frontend/package*.json`
- `hollowforge/frontend/src/components/LoraSelector.tsx`
- `hollowforge/frontend/src/components/PresetCard.tsx`
- `hollowforge/frontend/src/main.tsx`
- `hollowforge/frontend/src/pages/Dashboard.tsx`
- `hollowforge/frontend/src/pages/ImageDetail.tsx`
- `hollowforge/frontend/src/pages/Presets.tsx`
- `hollowforge/frontend/vite.config.ts`

주의:

- 이 커밋은 staged snapshot을 쓰는 방식이라, 최신 unstaged 변경을 같은 커밋에 섞지 말아야 한다.

### Commit 3. Content ops / curation / publishing

신규 route/service/page가 가장 선명하게 묶이는 batch다.

포함 권장:

- backend
  - `hollowforge/backend/app/routes/collections.py`
  - `hollowforge/backend/app/routes/curation.py`
  - `hollowforge/backend/app/routes/export.py`
  - `hollowforge/backend/app/routes/favorites.py`
  - `hollowforge/backend/app/routes/marketing.py`
  - `hollowforge/backend/app/routes/publishing.py`
  - `hollowforge/backend/app/routes/quality_ai.py`
  - `hollowforge/backend/app/services/caption_service.py`
  - `hollowforge/backend/app/services/favorite_upscale_service.py`
  - `hollowforge/backend/app/services/quality_service.py`
  - `hollowforge/backend/app/services/safe_upscale_runner.py`
  - `hollowforge/backend/app/services/watermark_service.py`
  - `hollowforge/backend/migrations/006_watermark.sql`
  - `hollowforge/backend/migrations/007_collections.sql`
  - `hollowforge/backend/migrations/008_adetail.sql`
  - `hollowforge/backend/migrations/014_quality_gate.sql`
  - `hollowforge/backend/migrations/015_ai_quality.sql`
  - `hollowforge/backend/migrations/016_all_tags_json.sql`
  - `hollowforge/backend/migrations/017_postprocess_jobs.sql`
  - `hollowforge/backend/migrations/018_favorite_upscale_tracking.sql`
  - `hollowforge/backend/migrations/019_content_pipeline.sql`

- frontend
  - `hollowforge/frontend/src/components/CompareView.tsx`
  - `hollowforge/frontend/src/components/ExportModal.tsx`
  - `hollowforge/frontend/src/components/Lightbox.tsx`
  - `hollowforge/frontend/src/components/EmptyState.tsx`
  - `hollowforge/frontend/src/components/tools/`
  - `hollowforge/frontend/src/pages/Collections.tsx`
  - `hollowforge/frontend/src/pages/CurationPage.tsx`
  - `hollowforge/frontend/src/pages/Favorites.tsx`
  - `hollowforge/frontend/src/pages/Marketing.tsx`
  - `hollowforge/frontend/src/pages/QualityPage.tsx`
  - `hollowforge/frontend/src/pages/ReadyToGo.tsx`

### Commit 4. Animation stack

포함 권장:

- backend
  - `hollowforge/backend/app/routes/animation.py`
  - `hollowforge/backend/app/routes/dreamactor.py`
  - `hollowforge/backend/app/routes/seedance.py`
  - `hollowforge/backend/app/services/animation_dispatch_service.py`
  - `hollowforge/backend/app/services/dreamactor_service.py`
  - `hollowforge/backend/app/services/seedance_service.py`
  - `hollowforge/backend/migrations/012_dreamactor.sql`
  - `hollowforge/backend/migrations/013_seedance.sql`
  - `hollowforge/backend/migrations/020_animation_jobs.sql`
  - `hollowforge/backend/scripts/check_local_animation_preflight.py`
  - `hollowforge/backend/scripts/launch_animation_preset_smoke.py`
  - `hollowforge/backend/scripts/dispatch_ltxv_when_queue_idle.py`

- worker
  - `hollowforge/lab451-animation-worker/`

- frontend
  - `hollowforge/frontend/src/components/DreamActorPanel.tsx`
  - `hollowforge/frontend/src/components/LocalAnimationPanel.tsx`
  - `hollowforge/frontend/src/components/VideoPlayer.tsx`
  - `hollowforge/frontend/src/pages/SeedanceStudio.tsx`

- docs
  - `hollowforge/docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`
  - `hollowforge/docs/LAB451_ANIMATION_WORKER_SETUP_20260310.md`
  - `hollowforge/docs/LOCAL_I2V_PIPELINE_PLAN_20260312.md`

### Commit 5. Prompt Factory + model compatibility

포함 권장:

- backend
  - `hollowforge/backend/app/services/model_compatibility.py`
  - `hollowforge/backend/app/services/prompt_factory_service.py`
  - `hollowforge/backend/app/services/workflow_registry.py`
  - `hollowforge/backend/migrations/021_sdxl_production_defaults.sql`
  - `hollowforge/backend/migrations/022_prompt_factory_checkpoint_preferences.sql`

- frontend
  - `hollowforge/frontend/src/pages/PromptFactory.tsx`
  - `hollowforge/frontend/src/pages/DirectionBoard.tsx`
  - `hollowforge/frontend/src/pages/LoraManager.tsx`
  - `hollowforge/frontend/src/pages/MoodManager.tsx`
  - `hollowforge/frontend/src/pages/QueuePage.tsx`
  - `hollowforge/frontend/src/pages/Scheduler.tsx`
  - `hollowforge/frontend/src/pages/Timeline.tsx`
  - `hollowforge/frontend/src/lib/`

- docs
  - `hollowforge/docs/GROK_PROMPT_FACTORY_20260311.md`
  - `hollowforge/docs/LAB451_EXECUTION_ROADMAP_20260310.md`

### Commit 6. Character canon / natural lane

포함 권장:

- backend migrations
  - `hollowforge/backend/migrations/023_core_characters.sql`
  - `hollowforge/backend/migrations/024_reserve_characters.sql`
  - `hollowforge/backend/migrations/025_lock_canonical_still_recipes.sql`
  - `hollowforge/backend/migrations/026_seed_canonical_natural_versions.sql`
  - `hollowforge/backend/migrations/027_character_natural_scene_profiles.sql`
  - `hollowforge/backend/migrations/028_character_natural_shot_overrides.sql`

- scripts
  - `hollowforge/backend/scripts/queue_core_character_daily_signatures.py`
  - `hollowforge/backend/scripts/queue_character_identity_pack.py`
  - `hollowforge/backend/scripts/queue_character_natural_benchmark.py`
  - `hollowforge/backend/scripts/queue_character_signature_combo_matrix.py`
  - `hollowforge/backend/scripts/qc_single_subject_batch.py`

- docs
  - `hollowforge/docs/HOLLOWFORGE_CANONICAL_RECIPE_LOCK_20260321.md`
  - `hollowforge/docs/HOLLOWFORGE_CORE_CHARACTER_REGISTRY_20260320.md`
  - `hollowforge/docs/HOLLOWFORGE_GOLDEN_COMBO_PLAYBOOK_20260320.md`
  - `hollowforge/docs/HOLLOWFORGE_NATURAL_LANE_20260322.md`
  - `hollowforge/docs/HOLLOWFORGE_RESERVE_CHARACTER_REGISTRY_20260321.md`
  - `hollowforge/docs/LAB451_CHARACTER_SERIES_PIPELINE_20260312.md`
  - `hollowforge/docs/queue_runs/`

### Commit 7. Cross-cutting integration + review follow-ups

이건 마지막에 남겨야 한다.

대상:

- `hollowforge/backend/app/main.py`
- `hollowforge/backend/app/models.py`
- `hollowforge/backend/app/routes/gallery.py`
- `hollowforge/backend/app/routes/generations.py`
- `hollowforge/backend/app/routes/loras.py`
- `hollowforge/backend/app/routes/system.py`
- `hollowforge/backend/app/services/comfyui_client.py`
- `hollowforge/backend/app/services/generation_service.py`
- `hollowforge/backend/app/services/lora_selector.py`
- `hollowforge/frontend/src/App.tsx`
- `hollowforge/frontend/src/api/client.ts`
- `hollowforge/frontend/src/components/GalleryGrid.tsx`
- `hollowforge/frontend/src/components/GenerateForm.tsx`
- `hollowforge/frontend/src/components/GlobalGenerationIndicator.tsx`
- `hollowforge/frontend/src/pages/BatchImportPage.tsx`
- `hollowforge/frontend/src/pages/Gallery.tsx`
- `hollowforge/frontend/src/pages/Generate.tsx`
- `hollowforge/frontend/src/pages/LoraGuide.tsx`
- `hollowforge/frontend/src/pages/Settings.tsx`
- `hollowforge/ROADMAP.md`

현재 내가 넣은 lint 정리와 roadmap 갱신도 이 commit에 합치는 편이 자연스럽다.

## 5. 지금 커밋에서 빼는 게 좋은 것

아래는 코드 리뷰를 어렵게 만들거나 자산/로컬 상태 성격이 강하다.

- `hollowforge/backend/hand_landmarker.task` (`7.5M`)
- `hollowforge/models/` (`22M`)
- `hollowforge/lab451-animation-worker/` (`29M`) 전체를 코드와 섞는 경우
- `hollowforge/frontend/public/figma-board-assets/` (`11M`)
- `hollowforge/docs/queue_runs/` (`2.2M`)

원칙:

- 코드 commit과 대용량 asset commit을 분리한다.
- 가능하면 asset/docs-only commit으로 따로 뺀다.

## 6. 당장 가장 안전한 다음 액션

가장 안전한 순서는 아래다.

1. staged 루트 baseline을 먼저 하나로 정리한다.
2. staged HollowForge bootstrap을 두 번째 commit으로 자른다.
3. 그 다음부터 untracked feature wave를 area별로 새로 `git add` 한다.
4. 마지막에 `main.py`, `models.py`, `api/client.ts`, `App.tsx` 같은 cross-cutting 파일을 `git add -p`로 붙인다.

## 7. 주의사항

- `AM`, `MM` 파일은 staged snapshot과 현재 working tree가 다르다.
- 이런 파일은 "지금 staged된 버전"을 정말 남길지 확인 후 커밋해야 한다.
- 사용자 의도 확인 없이 `git reset --hard`, `git restore --source`, 대량 unstage는 하지 않는 것이 맞다.
