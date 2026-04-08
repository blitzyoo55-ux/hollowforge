# AGENTS.md

## Repo Layout

- `backend/`
  - FastAPI app, SQLite schema, migrations, and orchestration or smoke scripts
- `frontend/`
  - React operator UI, tests, and production build surface
- `lab451-animation-worker/`
  - animation executor and callback-compatible worker runtime
- `deploy/`
  - Cloudflare Tunnel, nginx, oauth2-proxy, and launchd runtime assets
- `docs/`
  - dated runbooks, validation notes, roadmap support, and operating evidence
- `README.md`, `STATE.md`, `ROADMAP.md`
  - canonical re-entry and status surfaces

## Key Commands

- `backend/run_local_backend.sh`
  - canonical local backend entrypoint
- `npm --prefix frontend run lint`
  - frontend static checks
- `npm --prefix frontend run test`
  - frontend Vitest suite
- `npm --prefix frontend run build`
  - required frontend deploy build
- `lab451-animation-worker/run_local_animation_worker.sh`
  - canonical local animation preview worker
- `backend/.venv/bin/python scripts/check_local_animation_preflight.py`
  - animation contract preflight

## Constraints

- Treat `backend/` and `frontend/` as the operator-facing system of record.
- Frontend work is not deploy-complete until the `frontend/` build has been
  regenerated.
- Preserve the HollowForge to worker `request_json` and callback contract when
  changing animation execution paths.
- Do not commit secrets, Cloudflare tunnel tokens, OAuth client credentials, or
  copied local `.env` values into tracked files.
- When runtime assumptions change, update `README.md` or `STATE.md` so the next
  session can re-enter cleanly.

## Review guidelines

- Treat missing frontend build verification after runtime UI changes as `P1`.
- Treat broken backend or worker entrypoints, callback-contract regressions, or
  stale deploy instructions as `P1`.
- Treat secret exposure, public binding mistakes, or incorrect Zero Trust
  assumptions as `P0` or `P1` depending on impact.
- Require explicit verification notes for the relevant frontend, backend, or
  animation-worker commands when those surfaces change.
- Treat drift between runtime truth and `README.md`, `STATE.md`, or `ROADMAP.md`
  as a review issue, not a documentation nicety.
