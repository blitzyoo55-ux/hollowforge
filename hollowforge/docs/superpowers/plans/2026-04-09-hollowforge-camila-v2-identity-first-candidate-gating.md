# HollowForge Camila V2 Identity-First Candidate Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent Camila V2 still acceptance from auto-selecting readable-but-wrong-person candidates by introducing an identity-first gate ahead of helper selection.

**Architecture:** Keep the current V2 layering intact. Reuse the existing worker callback `request_json`, backend structured assessment extraction, and bounded pilot helpers. Do not widen scope to UI or full identity embeddings. The fix is: structured identity assessment support -> backend identity gate scorer -> helper best-passing-candidate selection -> live Camila V2 still re-acceptance.

**Tech Stack:** FastAPI backend services, existing comic render job callback path, existing bounded pilot helpers, pytest, live remote still pipeline on `8011`.

---

## File Map

### Existing files to modify

- `backend/app/services/comic_render_service.py`
  - add structured identity assessment extraction/scoring and helper-facing best-candidate selection support
- `backend/scripts/launch_camila_v2_comic_pilot.py`
  - stop selecting the first materialized asset; wait for all candidates and choose the best identity-passing candidate
- `backend/tests/test_comic_render_service.py`
  - cover identity assessment extraction, identity score computation, and fail-closed selection behavior
- `backend/tests/test_launch_camila_v2_comic_pilot.py`
  - cover best-passing-candidate selection and fail-closed helper behavior
- `README.md`
- `STATE.md`
- `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

### Scope Guardrails

- Camila V2 lane only
- no frontend work
- no schema expansion unless absolutely required during implementation
- no full similarity model
- no docs update unless live still acceptance passes

## Task 1: Extend backend scoring tests for identity-first assessment

**Files:**
- Modify: `backend/tests/test_comic_render_service.py`

- [ ] Add failing tests for:
  - extracting `identity_positive_signals` / `identity_negative_signals` from structured request_json
  - computing an `identity_score` separately from readability-oriented quality scoring
  - enforcing panel-role aware identity thresholds
  - rejecting a candidate set when no candidate clears the identity gate

- [ ] Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_comic_render_service.py
```

Expected: FAIL.

## Task 2: Implement identity-first scoring in comic render service

**Files:**
- Modify: `backend/app/services/comic_render_service.py`
- Verify: `backend/tests/test_comic_render_service.py`

- [ ] Add structured helpers for:
  - identity signal extraction from request_json
  - identity score calculation
  - panel-role identity threshold resolution
  - best-passing-candidate selection among completed jobs/assets

- [ ] Rules:
  - identity gate runs before readability ranking
  - `quality_score` alone cannot rescue a low-identity candidate
  - if no candidate passes the identity threshold, selection must fail closed

- [ ] Re-run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_comic_render_service.py
```

Expected: PASS.

- [ ] Commit:

```bash
git add \
  backend/app/services/comic_render_service.py \
  backend/tests/test_comic_render_service.py
git commit -m "feat(hollowforge): add camila v2 identity-first candidate gating"
```

## Task 3: Replace helper first-materialized selection with best-passing selection

**Files:**
- Modify: `backend/scripts/launch_camila_v2_comic_pilot.py`
- Modify: `backend/tests/test_launch_camila_v2_comic_pilot.py`

- [ ] Add failing tests for:
  - waiting for all candidates for a panel during quality-pass mode
  - choosing the best candidate that clears the identity threshold
  - failing the helper when every candidate fails the identity gate

- [ ] Implement helper changes:
  - do not select the first materialized asset
  - inspect all candidate jobs/assets for a panel
  - pick the highest-ranked identity-passing candidate
  - emit a clear failure when no candidate passes

- [ ] Re-run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_launch_camila_v2_comic_pilot.py
```

Expected: PASS.

- [ ] Commit:

```bash
git add \
  backend/scripts/launch_camila_v2_comic_pilot.py \
  backend/tests/test_launch_camila_v2_comic_pilot.py
git commit -m "fix(hollowforge): gate camila v2 helper selection by identity"
```

## Task 4: Re-run focused regression and live Camila still acceptance

**Files:**
- Modify only if acceptance passes:
  - `README.md`
  - `STATE.md`
  - `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] Run focused regression:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest -q \
  tests/test_comic_render_service.py \
  tests/test_launch_camila_v2_comic_pilot.py \
  tests/test_launch_camila_v2_teaser_pilot.py
```

Expected: PASS.

- [ ] Run live four-panel acceptance:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python \
  scripts/launch_camila_v2_comic_pilot.py \
  --base-url http://127.0.0.1:8011 \
  --panel-limit 4 \
  --candidate-count 2 \
  --render-poll-attempts 420
```

Expected:
- helper returns `overall_success: true`
- selected four panels hold same-person Camila
- establish readability remains acceptable
- docs remain untouched unless this passes

- [ ] Only if still acceptance passes, run teaser verification:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-character-canon-v2-pilot/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python \
  scripts/launch_camila_v2_teaser_pilot.py \
  --base-url http://127.0.0.1:8011 \
  --episode-id <episode_id> \
  --selected-scene-panel-id <panel_id> \
  --selected-render-asset-id <asset_id> \
  --selected-render-generation-id <generation_id> \
  --selected-render-asset-storage-path <storage_path> \
  --timeout-sec 1800
```

- [ ] Only if both pass, update docs and run:

```bash
git diff --check
```

Then commit docs:

```bash
git add \
  README.md \
  STATE.md \
  docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md
git commit -m "docs(hollowforge): record camila v2 identity-gated still pass"
```

## Final Verification Gate

- [ ] Confirm `git status --short` only shows runtime `data/` or intentional doc edits
- [ ] Report explicitly:
  - whether identity-first gating prevented wrong-person auto-selection
  - whether Camila same-person hold passed on four selected panels
  - whether teaser verification was run
  - whether the V2 lane is ready for one more quality pass or stable promotion
