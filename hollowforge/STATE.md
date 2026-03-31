# HollowForge State

Last updated: 2026-03-30

## Snapshot

- HollowForge is the active Lab451 image generation and orchestration console.
- Production access is routed through Cloudflare Zero Trust at
  `https://sec.hlfglll.com`.
- The runtime stack is FastAPI + React 19 + Tailwind v4 + SQLite + ComfyUI.
- The backend local entrypoint is `backend/run_local_backend.sh` and binds to
  `127.0.0.1:8000`.
- The frontend must be rebuilt explicitly with `npm run build` before deploy.
- The current local animation preview lane is `sdxl_ipadapter_microanim_v2`.

## Resume Here

1. Use `README.md` for the repo map and `ROADMAP.md` for full phase history.
2. If a change touches frontend runtime behavior, run the relevant `frontend/`
   checks and do not treat the work as deploy-complete before `npm run build`.
3. If a change touches animation execution, preserve the existing
   `request_json` and callback contract, then use the canonical preflight or
   smoke scripts from `docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`.
4. Record meaningful checkpoints in `00_Collaboration/project-hub` so the hub,
   this file, and the roadmap do not drift.

## Active Priorities

- keep the production deploy path explicit, especially the frontend build step
- continue the shift from random image generation toward character, episode,
  and shot-oriented production
- keep the local preview lane stable while preparing stronger remote worker
  execution underneath the same contract

## Canonical Entry Points

- backend runtime: `backend/run_local_backend.sh`
- backend animation preflight:
  `backend/.venv/bin/python scripts/check_local_animation_preflight.py`
- backend animation smoke:
  `backend/.venv/bin/python scripts/launch_animation_preset_smoke.py`
- frontend checks: `frontend/package.json`
- animation worker runtime: `lab451-animation-worker/run_local_animation_worker.sh`
- deployment assets: `deploy/cloudflared/`, `deploy/nginx/`,
  `deploy/oauth2-proxy/`, `deploy/launchd/`

## Current Risks

- deploy correctness still depends on humans remembering the frontend build step
- publish automation exists in the data model and UI pathing, but real operator
  usage is still incomplete
- animation quality beyond preview grade will likely require stronger remote GPU
  execution rather than more local tuning
