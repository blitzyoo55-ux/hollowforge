# HollowForge State

Last updated: 2026-04-05

## Snapshot

- HollowForge is the active Lab451 image generation and orchestration console.
- Production access is routed through Cloudflare Zero Trust at
  `https://sec.hlfglll.com`.
- The runtime stack is FastAPI + React 19 + Tailwind v4 + SQLite + ComfyUI.
- The backend local entrypoint is `backend/run_local_backend.sh` and binds to
  `127.0.0.1:8000`.
- The current phase is production dry run + Japanese handoff hardening.
- The comic MVP scope is currently one character, one one-shot comic episode,
  and one teaser derivative path from that same source material.
- `/comic` now carries manuscript profile selection, backed by
  `GET /api/v1/comic/manuscript-profiles`.
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
- The frontend must be rebuilt explicitly with `npm run build` before deploy.
- The current local animation preview lane is `sdxl_ipadapter_microanim_v2`.
- The latest validated comic teaser episode id is
  `2d696b08-4899-4a3b-b499-adc37dbaa9f5`.
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

## Resume Here

1. Use `README.md` for the repo map and `ROADMAP.md` for full phase history.
2. If a change touches frontend runtime behavior, run the relevant `frontend/`
   checks and do not treat the work as deploy-complete before `npm run build`.
3. If a change touches animation execution, preserve the existing
   `request_json` and callback contract, then use the canonical preflight or
   smoke scripts from `docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`.
4. Comic MVP operator entry is `/comic`, with `/comic-studio` retained as a
   compatibility route for existing bookmarks, and manuscript profile selection
   is now part of the `/comic` workspace.
5. Use `backend/.venv/bin/python scripts/launch_comic_mvp_smoke.py --base-url
   http://127.0.0.1:8000` when you need a bounded end-to-end comic backend
   check against a running local API.
6. Use `backend/.venv/bin/python scripts/launch_comic_one_panel_verification.py
   --base-url http://127.0.0.1:8000` when you need a reproducible real-asset
   local verification before attempting a full one-shot.
7. Use `backend/.venv/bin/python scripts/launch_comic_four_panel_benchmark.py
   --base-url http://127.0.0.1:8000` when you need a measured local 4-panel
   throughput report, a fail-fast slow-panel cutoff, and a concrete
   `stay_local` vs `remote_worker_recommended` recommendation.
8. Use `backend/.venv/bin/python scripts/check_comic_remote_render_preflight.py
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
9. Use `backend/.venv/bin/python scripts/launch_comic_remote_render_smoke.py
   --base-url http://127.0.0.1:8000` when you need a bounded callback-driven
   proof that the remote still lane can materialize and select one real panel
   asset through `execution_mode=remote_worker`. This helper stays inside the
   local backend URL boundary.
10. Use `backend/.venv/bin/python scripts/launch_comic_production_dry_run.py`
   when you need the production handoff validation path with a selected layout
   template and manuscript profile.
11. Use `backend/.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py
   --base-url http://127.0.0.1:8000 --episode-id
   2d696b08-4899-4a3b-b499-adc37dbaa9f5 --panel-index 0 --preset-id
   sdxl_ipadapter_microanim_v2 --poll-sec 5 --timeout-sec 1800` when you need
   the canonical teaser derivative validation path. This helper stays inside
   the local backend URL boundary and assumes the stable launchd backend plus
   stable launchd animation worker are already healthy.
12. If a teaser animation job is stuck non-terminal (`queued`, `submitted`, or
   `processing`), use `backend/.venv/bin/python scripts/reconcile_stale_animation_jobs.py
   --base-url http://127.0.0.1:8000` to mark it `failed / Worker restarted`.
   Once it is failed, rerun the existing teaser helper. Recovery is `fail then
   rerun`, not resume.
13. Record meaningful checkpoints in `00_Collaboration/project-hub` so the hub,
   this file, and the roadmap do not drift.

## Active Priorities

- keep the production deploy path explicit, especially the frontend build step
- keep the production dry-run and handoff export path explicit, including the
  manuscript profile selection and ZIP/report verification steps
- continue the shift from random image generation toward character, episode,
  and shot-oriented production
- keep the comic MVP bounded around import, per-panel selected renders,
  dialogue drafting, page assembly, and handoff export before broadening the
  surface
- keep the local preview lane stable while preparing stronger remote worker
  execution underneath the same contract
- keep the remote still lane operationally explicit with the dedicated comic
  preflight and smoke helpers instead of treating it as an implicit extension of
  the local verification path

## Canonical Entry Points

- backend runtime: `backend/run_local_backend.sh`
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
- frontend comic route: `/comic`
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
  well as the page assembly and ZIP verification steps
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
- latest session: HollowForge review visibility fix
- latest summary: Recorded the HollowForge git-visibility fix for collaboration docs.

### Open Issues
- none

### Next Actions
- Run the next HollowForge runtime review against the new code_review baseline.

### Verification Snapshot
- none
<!-- project-hub:status:end -->
