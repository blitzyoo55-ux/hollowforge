# HollowForge Comic Operator SOP

Date: 2026-04-08

Last verified update: 2026-04-17

## Goal

This SOP defines the bounded operator flow for the current HollowForge comic
MVP:

- import one approved story plan
- produce or inspect selected panel renders
- review a layered Japanese handoff package
- export a Japanese handoff ZIP only after handoff review clears
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

### 4. Assemble pages

Once every panel in the episode has a selected materialized render:

1. confirm `Layout Template`
2. confirm `Manuscript Profile`
3. click `Assemble Pages`

Expected outputs:

- preview pages under the `Pages` surface
- page assembly manifest family under `data/comics/manifests/`

### 5. Handoff review

After page assembly succeeds, switch to the `Handoff` surface.

Review:

1. per-page art / frame / balloon / text draft readiness
2. hard block count and soft warning count
3. layered artifact paths
4. export checklist

Expected layered artifacts:

- root `manifest.json`
- root `handoff_validation.json`
- `pages/page_###/page_manifest.json`
- `pages/page_###/frame_layer.json`
- `pages/page_###/balloon_layer.json`
- `pages/page_###/text_draft_layer.json`
- `panels/panel_<panel_id>/panel_manifest.json`

Export rule:

- if `hard_block_count > 0`, do not export
- warning-only state is exportable
- if selected renders, layout template, or manuscript profile change, re-assemble
  and re-review before export

### 6. Export the comic handoff

Only after `Handoff Review` shows zero hard blocks:

1. confirm `Layered manifest` path is present
2. confirm `Validation artifact` path is present
3. confirm export checklist is fully `Ready`
4. click `Export Handoff ZIP`

Expected outputs:

- handoff ZIP
- layered manifest
- handoff validation artifact
- production report

Canonical export-family artifacts live under:

- `data/comics/exports/`
- `data/comics/reports/`

### 7. Derive one teaser animation

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

### 8. Recover a stale teaser job

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

Canonical comic verification path:

1. run remote still preflight
2. run the comic verification suite
3. rerun a single stage only if the suite has already narrowed the failing lane

Canonical comic verification suite:

```bash
cd backend
./.venv/bin/python scripts/check_comic_remote_render_preflight.py \
  --backend-url http://127.0.0.1:8000

./.venv/bin/python scripts/run_comic_verification_suite.py \
  --base-url http://127.0.0.1:8000
```

The suite runner is the default operator entry for:

- `smoke -> full -> remote`
- fail-fast by default
- `--smoke-only`, `--full-only`, `--remote-only` for isolated reruns
- `--continue-on-failure` when a full failure map is more useful than fail-fast

The shared `full` remote-worker poll budget is now `360 * 2s`. This was raised
after real worker completions exceeded the older 480-second window while still
finishing successfully through callback materialization.

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

Bounded Camila V2 pilot path:

```bash
cd backend
./.venv/bin/python scripts/launch_camila_v2_comic_pilot.py \
  --base-url http://127.0.0.1:8000

./.venv/bin/python scripts/launch_camila_v2_teaser_pilot.py \
  --base-url http://127.0.0.1:8000 \
  --episode-id 09854884-5d52-4c94-9d5b-61800bfec677 \
  --selected-scene-panel-id df540260-b759-4d42-b384-637bf60661ed \
  --selected-render-asset-id d5866d4b-a4cd-4463-a01d-a1f2da43be43 \
  --selected-render-generation-id c7a2075b-f76c-4caf-85b5-406ed026db5f \
  --selected-render-asset-storage-path outputs/051d5939-1216-4561-ad11-b9696da5cfb3.png \
  --timeout-sec 1800
```

The comic helper is intentionally bounded for live validation. It now defaults
to one panel, one remote candidate, and a longer materialization poll so the
pilot lane proves the V2 render contract before a broader one-shot run.

Layered handoff dry-run success criteria:

- `layered_manifest_path` exists
- `handoff_validation_path` exists
- `hard_block_count` is zero
- export ZIP contains root layered files plus at least one page layer subtree

Stale reconcile fallback:

```bash
cd backend
./.venv/bin/python scripts/reconcile_stale_animation_jobs.py \
  --base-url http://127.0.0.1:8000
```

Isolated full-lane rerun:

```bash
cd backend
./.venv/bin/python scripts/launch_comic_one_panel_verification.py \
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
- one reviewed layered handoff package with zero hard blocks
- one exported handoff ZIP
- one production report
- one successful teaser mp4

If those five outputs exist, the current comic MVP lane has completed
successfully.
