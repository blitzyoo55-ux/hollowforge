# HollowForge

Production image generation and orchestration console for Lab451.

## Current Runtime

- stack: FastAPI + React 19 + Tailwind v4 + SQLite + ComfyUI
- primary access: `https://sec.hlfglll.com` behind Cloudflare Zero Trust
- local backend entrypoint: `backend/run_local_backend.sh`
- operator UI workspace: `frontend/`
- animation execution worker: `lab451-animation-worker/`
- deploy/runtime assets: `deploy/`

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
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend
./run_local_backend.sh

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/frontend
npm run lint
npm run test
npm run build

cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/lab451-animation-worker
./run_local_animation_worker.sh
```

## Important Runbooks

- `docs/LAB451_EXECUTION_ROADMAP_20260310.md`
  - product direction and operating split between HollowForge and external workers
- `docs/ANIMATION_WORKFLOW_PLAYBOOK_20260313.md`
  - canonical animation contract, preview lane, preflight, and smoke commands
- `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md`
  - sequence-stage workflow specifics
- `docs/cloudflare_zero_trust_setup.md`
  - access and tunnel setup context
- `docs/remote_access_google_oauth.md`
  - Google OAuth remote access reference

## Operating Rules

- frontend changes are not deploy-ready until `frontend/` has been rebuilt with
  `npm run build`
- keep the HollowForge to animation-worker `request_json` and callback contract
  stable even when the executor backend changes
- treat local preview animation as contract validation, not final production
  quality proof
- keep secrets in local `.env` files or secret stores only; do not move real
  tokens or OAuth credentials into tracked docs
