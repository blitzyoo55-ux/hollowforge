# HollowForge State

Last updated: 2026-04-15

## Snapshot

- HollowForge is the active Lab451 image generation and orchestration console.
- Production access is routed through Cloudflare Zero Trust at
  `https://sec.hlfglll.com`.
- The runtime stack is FastAPI + React 19 + Tailwind v4 + SQLite + ComfyUI.
- The backend local entrypoint is `backend/run_local_backend.sh` and binds to
  `127.0.0.1:8000`.
- The current phase is production hub core + boundary-first UI for comic and
  animation tracks.
- `/production` now owns shared-core creation plus episode-aware resume for
  work, series, and episode orchestration state.
- `/comic` should now be read as Comic Handoff, not the final manga editor.
- `/comic` now splits the comic handoff path into `Pages` and `Handoff`
  surfaces so operators assemble previews first, then review layered export
  readiness before ZIP export.
- `/sequences` should now be read as Animation Track, not the final animation
  editor.
- `/comic` and `/sequences` now accept query-based production context passed
  from `/production` so operators can land on a specific linked episode state.
- Route fallback behavior is now explicit: `create_from_production` and
  `open_current` are only honored when `production_episode_id` is paired with
  an explicit `mode`; otherwise the route stays in manual operator mode.
- The bounded shared-core smoke helper entry point is
  `backend/scripts/launch_production_hub_smoke.py`.
- The comic MVP scope is currently one character, one one-shot comic episode,
  and one teaser derivative path from that same source material.
- `/comic` now carries manuscript profile selection, backed by
  `GET /api/v1/comic/manuscript-profiles`.
- layered comic handoff packaging is now live in the backend and remains
  additive to the legacy manifest and ZIP outputs.
- the canonical handoff package now writes `manifest.json`,
  `handoff_validation.json`, page layer files, and panel manifests alongside
  the legacy artifact family.
- the comic production dry-run and remote one-shot dry-run helpers now verify
  layered package artifacts and fail when `hard_block_count > 0`.
- `/comic` now also exposes selected-render teaser ops for `Current Teaser
  Shot` plus recent variants, stale reconcile, and one-click rerun against the
  canonical teaser preset.
- The local four-panel benchmark helper entry point is
  `backend/scripts/launch_comic_four_panel_benchmark.py`.
- The local one-panel verification helper entry point is
  `backend/scripts/launch_comic_one_panel_verification.py`.
- The comic remote render preflight helper entry point is
  `backend/scripts/check_comic_remote_render_preflight.py`.
- The comic remote render smoke helper entry point is
  `backend/scripts/launch_comic_remote_render_smoke.py`.
- The stable one-shot remote dry-run helper entry point is
  `backend/scripts/launch_comic_remote_one_shot_dry_run.py`.
- The production dry-run helper entry point is
  `backend/scripts/launch_comic_production_dry_run.py`.
- The comic teaser animation smoke helper entry point is
  `backend/scripts/launch_comic_teaser_animation_smoke.py`.
- The bounded Camila V2 comic pilot helper entry point is
  `backend/scripts/launch_camila_v2_comic_pilot.py`.
- The bounded Camila V2 teaser pilot helper entry point is
  `backend/scripts/launch_camila_v2_teaser_pilot.py`.
- The current `/comic` operator runbook is
  `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`.
- The frontend must be rebuilt explicitly with `npm run build` before deploy.
- The current local animation preview lane is `sdxl_ipadapter_microanim_v2`.
- The latest validated comic teaser episode id is
  `2d696b08-4899-4a3b-b499-adc37dbaa9f5`.
- Character Canon V2 plus Series Style Canon layering is now landed for the
  Camila-only pilot lane under `render_lane=character_canon_v2`.
- The latest validated Camila V2 episode id is
  `09854884-5d52-4c94-9d5b-61800bfec677`.
- The latest validated Camila V2 teaser animation job id is
  `e609ca82-ff84-4d7d-b199-469e7bab5325`.
- The latest validated Camila V2 teaser output is
  `data/outputs/15d0003c-99c5-48b3-991f-eff9a95e8f24.mp4`.
- The stable launchd labels are `com.mori.hollowforge.backend` and
  `com.mori.hollowforge.animation-worker`.
- The canonical teaser validation path expects the stable launchd backend and
  stable launchd animation worker to already be healthy.
- The comic teaser animation smoke helper is local-backend-only for
  `--base-url`, even when the backend is driving callback-based animation
  validation.
- The stable animation worker launchd lane runs `executor_backend=comfyui_pipeline`,
  so the remote comic smoke should use an extended render poll budget such as
  `--render-poll-attempts 360 --render-poll-sec 1.0`.
- The stable one-shot remote dry-run helper should currently be run with
  `--candidate-count 2` to keep the live production validation bounded.
- Comic panel roles now resolve different render profiles; `establish` and
  `insert` intentionally suppress glamour bias, and `establish` now uses a
  scene-first prompt recipe that prioritizes room readability over glamour.
- The next bounded comic-quality issue is establish candidate quality spread:
  some candidates still drift back toward portrait-heavy or awkward framing, so
  further tuning should stay in panel render profile values before story import
  or broader pipeline changes.

## Resume Here

1. Use `README.md` for the repo map and `ROADMAP.md` for full phase history.
2. Use `/production` first when checking shared work, series, and episode
   linkage state before dropping into `/comic` or `/sequences`. `/production`
   is now the owner for shared-core creation and episode-aware resume.
3. `/comic` and `/sequences` now accept query-based production context; when
   `production_episode_id` is paired with an explicit `mode`, follow that
   downstream handoff. Without both values, stay in manual operator mode.
4. Use `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md` for the current
   operator path across import, remote render, selected render, `Pages`,
   `Handoff Review`, handoff export, teaser rerun, and stale recovery.
5. If a change touches frontend runtime behavior, run the relevant `frontend/`
   checks and do not treat the work as deploy-complete before `npm run build`.
6. If a change touches animation execution, preserve the existing
   `request_json` and callback contract, then use the canonical preflight or
   smoke scripts from `docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`.
7. Use `backend/.venv/bin/python scripts/launch_production_hub_smoke.py` when
   you need a bounded proof that the shared production core can create or reuse
   a work, series, production episode, comic track, and animation track from
   one script.
8. Comic MVP operator entry is `/comic`, with `/comic-studio` retained as a
   compatibility route for existing bookmarks, and manuscript profile selection
   is now part of the `/comic` workspace. The page handoff path is split into
   `Pages` and `Handoff`, where `Handoff` owns layer readiness, export
   checklist review, and export gating on `hard_block_count == 0`. Selected-
   render teaser ops also live there, so operators can inspect the current
   teaser shot and recent variants without dropping to shell-only stale
   reconcile or rerun steps for the bounded teaser flow.
9. Use `backend/.venv/bin/python scripts/launch_comic_mvp_smoke.py --base-url
   http://127.0.0.1:8000` when you need a bounded end-to-end comic backend
   check against a running local API.
10. Use `backend/.venv/bin/python scripts/launch_comic_one_panel_verification.py
   --base-url http://127.0.0.1:8000` when you need a reproducible real-asset
   local verification before attempting a full one-shot.
11. Use `backend/.venv/bin/python scripts/launch_comic_four_panel_benchmark.py
   --base-url http://127.0.0.1:8000` when you need a measured local 4-panel
   throughput report, a fail-fast slow-panel cutoff, and a concrete
   `stay_local` vs `remote_worker_recommended` recommendation.
12. Use `backend/.venv/bin/python scripts/check_comic_remote_render_preflight.py
   --backend-url http://127.0.0.1:8000` before the remote still lane so the
   local backend, worker reachability, callback base URL, and auth-gated worker
   token state are checked in one place. This helper enforces the local backend
   URL boundary for `--backend-url`, requires
   `HOLLOWFORGE_PUBLIC_API_BASE_URL` to be a worker-facing `http(s)` callback
   base that resolves back to HollowForge through `/api/v1/system/health`, and
   can report `SKIP` for auth probing when the worker does not expose the
   undocumented `GET /api/v1/jobs` probe. If that callback hostname is wrapped
   in Cloudflare Access, the worker still needs either an Access bypass on the
   callback path or service-token headers; otherwise remote callbacks get
   redirected to the login flow.
13. Use `backend/.venv/bin/python scripts/launch_comic_remote_render_smoke.py
   --base-url http://127.0.0.1:8000` when you need a bounded callback-driven
   proof that the remote still lane can materialize and select one real panel
   asset through `execution_mode=remote_worker`. This helper stays inside the
   local backend URL boundary.
14. Use `backend/.venv/bin/python scripts/launch_comic_production_dry_run.py`
   when you need the production handoff validation path with a selected layout
   template and manuscript profile. Success now requires a real
   `layered_manifest_path`, a real `handoff_validation_path`, zero hard blocks,
   and layered ZIP contents for every exported page.
15. Use `backend/.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py
   --base-url http://127.0.0.1:8000 --episode-id
   2d696b08-4899-4a3b-b499-adc37dbaa9f5 --panel-index 0 --preset-id
   sdxl_ipadapter_microanim_v2 --poll-sec 5 --timeout-sec 1800` when you need
   the canonical teaser derivative validation path. This helper stays inside
   the local backend URL boundary, emits `animation_shot_id` and
   `animation_shot_variant_id` markers, and assumes the stable launchd backend
   plus stable launchd animation worker are already healthy.
16. If a teaser animation job is stuck non-terminal (`queued`, `submitted`, or
   `processing`), use `backend/.venv/bin/python scripts/reconcile_stale_animation_jobs.py
   --base-url http://127.0.0.1:8000` to mark it `failed / Worker restarted`.
   Once it is failed, rerun the existing teaser helper. Recovery is `fail then
   rerun`, not resume.
17. Use `backend/.venv/bin/python scripts/launch_camila_v2_comic_pilot.py
   --base-url http://127.0.0.1:8000` for the bounded Camila V2 still lane. The
   helper now defaults to `--panel-limit 1`, `--candidate-count 1`, and
   `--execution-mode remote_worker`, and emits explicit selected-render markers
   for the paired teaser helper.
18. Use `backend/.venv/bin/python scripts/launch_camila_v2_teaser_pilot.py
   --base-url http://127.0.0.1:8000 --episode-id
   09854884-5d52-4c94-9d5b-61800bfec677 --selected-scene-panel-id
   df540260-b759-4d42-b384-637bf60661ed --selected-render-asset-id
   d5866d4b-a4cd-4463-a01d-a1f2da43be43 --selected-render-generation-id
   c7a2075b-f76c-4caf-85b5-406ed026db5f --selected-render-asset-storage-path
   outputs/051d5939-1216-4561-ad11-b9696da5cfb3.png --timeout-sec 1800` for the
   bounded Camila V2 teaser validation path.
19. Record meaningful checkpoints in `00_Collaboration/project-hub` so the hub,
   this file, and the roadmap do not drift.

## Active Priorities

- keep the production deploy path explicit, especially the frontend build step
- keep `/production` as the source-of-truth surface for episode linkage and
  content-mode normalization
- keep the production dry-run and handoff export path explicit, including the
  manuscript profile selection, `Pages -> Handoff -> Export` review sequence,
  and ZIP/report verification steps
- continue the shift from random image generation toward character, episode,
  and shot-oriented production
- keep Character Canon V2 layered separately from legacy favorite still
  recipes, with Camila as the first pilot lane before broader migration
- keep the comic MVP bounded around import, per-panel selected renders,
  dialogue drafting, page assembly, and handoff export before broadening the
  surface
- keep the local preview lane stable while preparing stronger remote worker
  execution underneath the same contract
- keep the remote still lane operationally explicit with the dedicated comic
  preflight and smoke helpers instead of treating it as an implicit extension of
  the local verification path
- refresh the current-state docs so `STATE.md`, `ROADMAP.md`, and operator SOP
  no longer drift from the actual April comic/teaser baseline

## Canonical Entry Points

- backend runtime: `backend/run_local_backend.sh`
- backend production hub smoke:
  `backend/.venv/bin/python scripts/launch_production_hub_smoke.py`
- backend animation preflight:
  `backend/.venv/bin/python scripts/check_local_animation_preflight.py`
- backend animation smoke:
  `backend/.venv/bin/python scripts/launch_animation_preset_smoke.py`
- backend comic routes: `backend/app/routes/comic.py`
- backend comic smoke:
  `backend/.venv/bin/python scripts/launch_comic_mvp_smoke.py`
- backend comic one-panel verification:
  `backend/.venv/bin/python scripts/launch_comic_one_panel_verification.py`
- backend comic four-panel benchmark:
  `backend/.venv/bin/python scripts/launch_comic_four_panel_benchmark.py`
- backend comic remote render preflight:
  `backend/.venv/bin/python scripts/check_comic_remote_render_preflight.py`
- backend comic remote render smoke:
  `backend/.venv/bin/python scripts/launch_comic_remote_render_smoke.py`
- backend comic remote one-shot dry run:
  `backend/.venv/bin/python scripts/launch_comic_remote_one_shot_dry_run.py`
- backend comic production dry run:
  `backend/.venv/bin/python scripts/launch_comic_production_dry_run.py`
- backend comic teaser animation smoke:
  `backend/.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py`
- backend Camila V2 comic pilot:
  `backend/.venv/bin/python scripts/launch_camila_v2_comic_pilot.py`
- backend Camila V2 teaser pilot:
  `backend/.venv/bin/python scripts/launch_camila_v2_teaser_pilot.py`
- frontend production route: `/production`
- frontend comic route: `/comic`
- frontend animation track route: `/sequences`
- frontend checks: `frontend/package.json`
- animation worker runtime: `lab451-animation-worker/run_local_animation_worker.sh`
- animation worker launchd:
  `deploy/launchd/com.mori.hollowforge.animation-worker.plist`
- deployment assets: `deploy/cloudflared/`, `deploy/nginx/`,
  `deploy/oauth2-proxy/`, `deploy/launchd/`

## Current Risks

- deploy correctness still depends on humans remembering the frontend build step
- publish automation exists in the data model and UI pathing, but real operator
  usage is still incomplete
- handoff export correctness now depends on the selected manuscript profile as
  well as the page assembly, handoff review state, and ZIP verification steps
- animation quality beyond preview grade will likely require stronger remote GPU
  execution rather than more local tuning
- remote still render correctness now depends on callback reachability and worker
  token configuration, not just queue submission
- the comic remote preflight and smoke helpers intentionally assume a local
  backend boundary for the ops script itself, while the worker-facing callback
  base must resolve back to HollowForge and be reachable from the remote worker
  when the worker is not co-located

<!-- project-hub:status:start -->
- current phase: active
- latest session: Layered comic handoff package plus `/comic` handoff review UI
- latest summary: Landed additive layered comic handoff artifacts, upgraded the
  bounded dry-run helpers to verify layered package validity, and split `/comic`
  into `Pages` and `Handoff` surfaces with export checklist review and stale
  handoff invalidation before ZIP export.

### Open Issues
- none

### Next Actions
- Decide whether the next bounded fix stays on Camila V2 quality tuning or
  starts broadening the Character Canon V2 migration to additional characters.
- Keep `STATE.md`, `ROADMAP.md`, and the status checkpoint aligned when the next
  phase starts.

### Verification Snapshot
- backend `tests/test_animation_shot_registry.py` passes
- backend `tests/test_animation_reconciliation.py` passes
- backend `tests/test_launch_camila_v2_comic_pilot.py` passes
- backend `tests/test_launch_camila_v2_teaser_pilot.py` passes
- frontend `src/pages/ComicStudio.test.tsx` passes
- `npm run build` passes
- live `POST /api/v1/animation/reconcile-stale` responds normally
- fresh Camila V2 teaser output verified at
  `data/outputs/15d0003c-99c5-48b3-991f-eff9a95e8f24.mp4`
<!-- project-hub:status:end -->
