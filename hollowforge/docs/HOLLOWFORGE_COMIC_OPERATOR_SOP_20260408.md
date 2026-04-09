# HollowForge Comic Operator SOP

Date: 2026-04-08

## Goal

This SOP defines the bounded operator flow for the current HollowForge comic
MVP:

- import one approved story plan
- produce or inspect selected panel renders
- export a Japanese handoff package
- derive one teaser animation
- recover stale teaser jobs with `fail then rerun`

This is the current operational baseline for `/comic`.

## Preconditions

Before starting:

1. backend is healthy on `127.0.0.1:8000`
2. animation worker is healthy on `127.0.0.1:8600`
3. frontend is available at `/comic`
4. the approved Story Planner JSON is ready
5. the intended character version is a still/comic lane, not an animation-only lane

Quick checks:

```bash
curl -s http://127.0.0.1:8000/api/v1/system/health
curl -s http://127.0.0.1:8600/healthz
```

## Operator Flow

### 1. Open `/comic`

Use:

- local UI: `http://127.0.0.1:5173/comic`
- protected runtime: `https://sec.hlfglll.com/comic`

Choose:

- `Character`
- `Character Version`
- optional `Episode Title`

Paste the approved Story Planner JSON into `Approved Story Plan JSON`.

Then click:

- `Import Story Plan`

Expected result:

- an episode is created
- scenes and panels appear in the panel board
- dialogue, page assembly, and teaser panels remain gated until render truth exists

### 2. Produce panel renders

Current rule:

- use `Queue Local Preview` for narrow validation only
- use `Queue Remote Production` for repeated real still production
- panel roles now use different render profiles, with `establish` and `insert`
  intentionally suppressing glamour bias
- `establish` panels now use a scene-first prompt recipe, so winning renders
  should favor room readability and visible location props before portrait flair
- if a finished page still collapses into repeated portraits, tune profile
  values next instead of reopening story import

For each panel:

1. select the panel
2. queue renders
3. wait for candidates to materialize
4. click `Mark Selected` on the winning render

Downstream operations should not be trusted until the selected render has a real
materialized file.

### 3. Draft dialogue

Once a panel has a selected materialized render:

- use `Generate Dialogues`

Expected result:

- speech / caption / SFX rows appear in `Panel Dialogue Editor`

This is panel-scoped and should be repeated only where needed.

### 4. Assemble and export the comic handoff

Once every panel in the episode has a selected materialized render:

1. confirm `Layout Template`
2. confirm `Manuscript Profile`
3. click `Assemble Pages`
4. inspect page previews
5. click `Export Handoff ZIP`

Expected outputs:

- preview pages
- handoff ZIP
- production report

Canonical export-family artifacts live under:

- `data/comics/exports/`
- `data/comics/reports/`

### 5. Derive one teaser animation

Select the panel whose selected render should drive the teaser.

In `Teaser Ops For Selected Render`:

- inspect current teaser shot and recent variants
- inspect the latest failed reason if present
- inspect the latest successful mp4 if present

To launch a fresh teaser:

- click `Rerun Teaser From Selected Panel`

Current canonical preset:

- `sdxl_ipadapter_microanim_v2`

Expected result:

- a new animation job is created
- current teaser shot stays anchored to the selected render
- recent variants refresh under that current shot
- the newest successful mp4 can be opened from the same panel

### 6. Recover a stale teaser job

If a teaser job remains non-terminal for too long:

- `queued`
- `submitted`
- `processing`

Use:

- `Reconcile Stale Animation Jobs`

Expected result:

- stale jobs are marked failed with `Worker restarted`
- operator then launches a new teaser from the selected panel

Recovery rule is:

- `fail then rerun`
- never `resume`

## Shell Fallbacks

Use these only when UI verification needs a backend-side proof.

Canonical teaser smoke:

```bash
cd backend
./.venv/bin/python scripts/launch_comic_teaser_animation_smoke.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id 2d696b08-4899-4a3b-b499-adc37dbaa9f5 \
  --panel-index 0 \
  --preset-id sdxl_ipadapter_microanim_v2 \
  --poll-sec 5 \
  --timeout-sec 1800
```

Stale reconcile fallback:

```bash
cd backend
./.venv/bin/python scripts/reconcile_stale_animation_jobs.py \
  --base-url http://127.0.0.1:8000
```

Remote still preflight:

```bash
cd backend
./.venv/bin/python scripts/check_comic_remote_render_preflight.py \
  --backend-url http://127.0.0.1:8000
```

## Exit Criteria

For one bounded comic-plus-teaser pass, the operator should finish with:

- one imported episode
- selected materialized renders for every panel
- one exported handoff ZIP
- one production report
- one successful teaser mp4

If those five outputs exist, the current comic MVP lane has completed
successfully.
