# HollowForge

Production image generation and orchestration console for Lab451.

## Current Runtime

- stack: FastAPI + React 19 + Tailwind v4 + SQLite + ComfyUI
- primary access: `https://sec.hlfglll.com` behind Cloudflare Zero Trust
- current phase: production hub core + boundary-first comic and animation tracks
- local backend entrypoint: `backend/run_local_backend.sh`
- local animation worker entrypoint: `lab451-animation-worker/run_local_animation_worker.sh`
- operator UI workspace: `frontend/`
- production hub frontend route: `/production`
- comic backend routes: `backend/app/routes/comic.py`
- comic manuscript profile API: `GET /api/v1/comic/manuscript-profiles`
- comic frontend route: `/comic` with `/comic-studio` kept as a compatibility alias
  - `/comic` now also exposes selected-render teaser ops for `Current Teaser Shot`
    plus recent variants, stale reconcile, and one-click rerun
  - comic panel roles now resolve different render profiles; `establish` now
    uses a scene-first prompt recipe that biases toward room readability before
    portrait glamour, while `insert` continues to suppress glamour bias
  - Character Canon V2 plus Series Style Canon layering is now landed for the
    Camila-only pilot lane under `render_lane=character_canon_v2`
  - if establish candidates still vary too widely in storytelling quality, tune
    panel profile values before revisiting story import
- animation execution worker: `lab451-animation-worker/`
- deploy/runtime assets: `deploy/`
  - launchd templates now include `com.mori.hollowforge.backend` and
    `com.mori.hollowforge.animation-worker`

## Production Boundary

- `/production` now owns shared-core creation and episode-aware resume for
  work, series, and episode state.
- `/production` is the primary operator entry for creating or resuming
  production context before opening track surfaces.
- `/comic` should be read as `Comic Handoff`, not as the final manga editor.
  HollowForge packages review assets, dialogue drafts, page assembly, and
  export inputs before CLIP STUDIO EX finishing.
- `/sequences` should be read as `Animation Track`, not as the final animation
  editor. HollowForge plans blueprints, launches preview runs, and packages
  review outputs before external editorial finishing.
- `/comic` and `/sequences` accept query-based production context from
  `/production` so operators can open a specific linked work/series/episode
  directly from the shared-core surface.
- Operator fallback behavior is explicit:
  `create_from_production` when query context is present, otherwise
  `open_current`.
- `backend/scripts/launch_production_hub_smoke.py` is the bounded smoke entry
  point for the shared production core plus linked comic and animation tracks.

## Canonical Re-entry Docs

- `STATE.md`
  - current snapshot, resume notes, and active risks
- `ROADMAP.md`
  - full phase history and the next major priorities
- `AGENTS.md`
  - local repo layout, commands, and project-specific review guidance
- `code_review.md`
  - HollowForge-specific review focus and severity rules

## Runtime Surfaces

- `backend/`
  - FastAPI app, SQLite data model, migrations, orchestration, and smoke scripts
- `frontend/`
  - React operator console for generation, curation, quality, and sequence tools
- `lab451-animation-worker/`
  - swappable animation executor that preserves the HollowForge callback contract
- `deploy/`
  - `cloudflared`, `nginx`, `oauth2-proxy`, and `launchd` deployment assets
- `docs/`
  - dated runbooks, execution plans, validation notes, and roadmap support docs

## Canonical Commands

```bash
cd backend
./.venv/bin/python -m pytest -q tests/test_launch_production_hub_smoke.py
./.venv/bin/python scripts/launch_production_hub_smoke.py
./.venv/bin/python -m pytest tests/test_comic_schema.py tests/test_comic_repository.py tests/test_comic_story_bridge_service.py tests/test_comic_render_service.py tests/test_comic_dialogue_service.py tests/test_comic_page_assembly_service.py tests/test_comic_routes.py -q
./.venv/bin/python -m pytest -q tests/test_comic_remote_render_scripts.py
./run_local_backend.sh
./.venv/bin/python -m pytest -q tests/test_launch_comic_mvp_smoke.py
./.venv/bin/python -m pytest -q tests/test_launch_comic_one_panel_verification.py
./.venv/bin/python -m pytest -q tests/test_launch_comic_four_panel_benchmark.py
./.venv/bin/python -m pytest -q tests/test_launch_comic_teaser_animation_smoke.py
./.venv/bin/python -m pytest -q tests/test_launch_camila_v2_comic_pilot.py tests/test_launch_camila_v2_teaser_pilot.py
./.venv/bin/python scripts/check_comic_remote_render_preflight.py --backend-url http://127.0.0.1:8000
./.venv/bin/python scripts/launch_comic_mvp_smoke.py --base-url http://127.0.0.1:8000
./.venv/bin/python scripts/launch_comic_one_panel_verification.py --base-url http://127.0.0.1:8000
./.venv/bin/python scripts/launch_comic_four_panel_benchmark.py --base-url http://127.0.0.1:8000
./.venv/bin/python scripts/launch_camila_v2_comic_pilot.py --base-url http://127.0.0.1:8000
./.venv/bin/python scripts/launch_camila_v2_teaser_pilot.py --base-url http://127.0.0.1:8000 --episode-id 09854884-5d52-4c94-9d5b-61800bfec677 --selected-scene-panel-id df540260-b759-4d42-b384-637bf60661ed --selected-render-asset-id d5866d4b-a4cd-4463-a01d-a1f2da43be43 --selected-render-generation-id c7a2075b-f76c-4caf-85b5-406ed026db5f --selected-render-asset-storage-path outputs/051d5939-1216-4561-ad11-b9696da5cfb3.png --timeout-sec 1800
./.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id 2d696b08-4899-4a3b-b499-adc37dbaa9f5 \
  --panel-index 0 \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --poll-sec 5 \
  --timeout-sec 1800
./.venv/bin/python scripts/reconcile_stale_animation_jobs.py --base-url http://127.0.0.1:8000
./.venv/bin/python scripts/launch_comic_remote_render_smoke.py --base-url http://127.0.0.1:8000

cd frontend
npm run lint
npx vitest run src/pages/ComicStudio.test.tsx
npm run build

cd lab451-animation-worker
./run_local_animation_worker.sh

launchctl print gui/$(id -u)/com.mori.hollowforge.backend
launchctl print gui/$(id -u)/com.mori.hollowforge.animation-worker

cd backend
./.venv/bin/python scripts/launch_comic_remote_render_smoke.py --base-url http://127.0.0.1:8000 --render-poll-attempts 360 --render-poll-sec 1.0
./.venv/bin/python scripts/launch_comic_remote_one_shot_dry_run.py --base-url http://127.0.0.1:8000 --candidate-count 2
```

## Important Runbooks

- `docs/LAB451_EXECUTION_ROADMAP_20260310.md`
  - product direction and operating split between HollowForge and external workers
- `docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`
  - canonical animation contract, preview lane, preflight, and smoke commands
- `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md`
  - sequence-stage workflow specifics
- `docs/HOLLOWFORGE_COMIC_LOCAL_BENCHMARK_20260404.md`
  - local 4-panel throughput benchmark, fail-fast cutoff, and remote-worker recommendation guidance
- `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`
  - current `/comic` operator flow for import, remote render, handoff export,
    current teaser shot and recent variants, teaser rerun, and stale recovery
- `docs/cloudflare_zero_trust_setup.md`
  - access and tunnel setup context
- `docs/remote_access_google_oauth.md`
  - Google OAuth remote access reference

## Comic MVP Entry Points

- backend production hub routes:
  `GET /api/v1/production/episodes`,
  `POST /api/v1/production/works`,
  `POST /api/v1/production/series`,
  `POST /api/v1/production/episodes`
- backend import route: `POST /api/v1/comic/episodes/import-story-plan`
- backend render queue route:
  `POST /api/v1/comic/panels/{panel_id}/queue-renders?candidate_count=3`
- backend dialogue route:
  `POST /api/v1/comic/panels/{panel_id}/dialogues/generate`
- backend assembly route:
  `POST /api/v1/comic/episodes/{episode_id}/pages/assemble?layout_template_id=jp_2x2_v1&manuscript_profile_id=jp_manga_rightbound_v1`
- backend export route:
  `POST /api/v1/comic/episodes/{episode_id}/pages/export?layout_template_id=jp_2x2_v1&manuscript_profile_id=jp_manga_rightbound_v1`
- backend manuscript profile route:
  `GET /api/v1/comic/manuscript-profiles`
- backend detail route: `GET /api/v1/comic/episodes/{episode_id}`
- frontend production route: `/production`
- frontend comic handoff route: `/comic` with manuscript profile selection plus
  selected-render teaser ops
- frontend animation track route: `/sequences`
- bounded Camila V2 comic pilot:
  `backend/scripts/launch_camila_v2_comic_pilot.py`
- bounded Camila V2 teaser pilot:
  `backend/scripts/launch_camila_v2_teaser_pilot.py`

## Production Hand-off Commands

```bash
cd backend
./.venv/bin/python scripts/check_comic_remote_render_preflight.py \
  --backend-url http://127.0.0.1:8000

./.venv/bin/python scripts/launch_comic_remote_render_smoke.py \
  --base-url http://127.0.0.1:8000

./.venv/bin/python scripts/launch_comic_four_panel_benchmark.py \
  --base-url http://127.0.0.1:8000 \
  --layout-template-id jp_2x2_v1 \
  --manuscript-profile-id jp_manga_rightbound_v1

./.venv/bin/python scripts/launch_comic_one_panel_verification.py \
  --base-url http://127.0.0.1:8000 \
  --layout-template-id jp_2x2_v1 \
  --manuscript-profile-id jp_manga_rightbound_v1

./.venv/bin/python scripts/launch_comic_production_dry_run.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id <episode_id> \
  --layout-template-id jp_2x2_v1 \
  --manuscript-profile-id jp_manga_rightbound_v1

./.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id 2d696b08-4899-4a3b-b499-adc37dbaa9f5 \
  --panel-index 0 \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --poll-sec 5 \
  --timeout-sec 1800

unzip -l ../data/comics/exports/<episode_id>_jp_2x2_v1_handoff.zip | rg 'smoke_assets|_handoff_readme.md|_production_checklist.json'
jq '.teaser_handoff_manifest.selected_panel_assets[].storage_path' \
  ../data/comics/reports/<episode_id>_jp_2x2_v1_jp_manga_rightbound_v1_dry_run.json
```

Use `check_comic_remote_render_preflight.py` before the remote still lane, then
use `launch_comic_remote_render_smoke.py` to confirm callback-driven
materialization can produce at least one real selected panel asset through
`execution_mode=remote_worker`. The preflight and smoke helpers only support
local backend URLs for `--backend-url` and `--base-url`. The worker-facing
callback base in `HOLLOWFORGE_PUBLIC_API_BASE_URL` must be a valid `http(s)` URL
that resolves back to HollowForge; for non-local remote workers it must be
worker-reachable via a public or reverse-proxied address, while loopback is
only valid when the worker is co-located. Preflight now proves that callback
base by probing `HOLLOWFORGE_PUBLIC_API_BASE_URL/api/v1/system/health`. Worker
auth probing can also return `SKIP` when the worker does not expose the
undocumented `GET /api/v1/jobs` probe used only to infer whether token auth is
enforced. If the public callback hostname is protected by Cloudflare Access,
plain worker callbacks will be redirected to the Access login flow unless the
callback path is bypassed or the worker is taught to send Cloudflare Access
service-token headers.
The canonical comic teaser helper also stays inside the local backend URL
boundary, uses the default teaser preset `sdxl_ipadapter_microanim_v2`, and is
intended for live validation only after the stable launchd backend plus stable
launchd animation worker are already healthy.

## Operating Rules

- frontend changes are not deploy-ready until `frontend/` has been rebuilt with
  `npm run build`
- keep the HollowForge to animation-worker `request_json` and callback contract
  stable even when the executor backend changes
- treat local preview animation as contract validation, not final production
  quality proof
- keep secrets in local `.env` files or secret stores only; do not move real
  tokens or OAuth credentials into tracked docs
