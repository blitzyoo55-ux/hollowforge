# HollowForge Sequence Stage 1 Runbook

Date: 2026-03-25

This runbook covers the Stage 1 sequence orchestration slice inside HollowForge only. It is intended for operators validating preflight state, running local-first smoke tests, and assembling rough cuts without mixing the safe and adult execution lanes.

## Required Environment Variables

Core sequence settings:

- `DATA_DIR`
  - Backend data root. The sequence DB and rough-cut outputs are created here.
- `HOLLOWFORGE_SEQUENCE_FFMPEG_BIN`
  - `ffmpeg` binary name or absolute path. Required for rough-cut assembly.
- `HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE`
  - Default safe prompt profile. Expected Stage 1 default: `safe_hosted_grok`.
- `HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE`
  - Default adult prompt profile. Expected Stage 1 default: `adult_local_llm`.

Prompt-provider settings:

- `XAI_API_KEY`
  - Required when the safe prompt profile uses `safe_hosted_grok`.
- `OPENROUTER_API_KEY`
  - Required only when switching the safe lane to `safe_openrouter_fallback`.
- `HOLLOWFORGE_SEQUENCE_LOCAL_LLM_BASE_URL`
  - Required when the adult prompt profile uses `adult_local_llm` or `adult_local_llm_strict_json`.
- `HOLLOWFORGE_SEQUENCE_LOCAL_LLM_MODEL`
  - Local LLM model name for the adult lane.

Remote worker settings:

- `HOLLOWFORGE_ANIMATION_REMOTE_BASE_URL`
  - Required when using `safe_remote_prod` or `adult_remote_prod`.
- `HOLLOWFORGE_ANIMATION_WORKER_API_TOKEN`
  - Required if the remote worker expects bearer auth.
- `HOLLOWFORGE_PUBLIC_API_BASE_URL`
  - Required so the remote worker can fetch HollowForge-hosted inputs and call back correctly.
- `HOLLOWFORGE_ANIMATION_CALLBACK_TOKEN`
  - Required when the backend callback route is protected.

## Local-First Workflow

Default operating mode for Stage 1:

1. Start from the safe local preview path first.
2. Run backend tests and the sequence preflight locally.
3. Validate a blueprint and run creation flow before sending anything to a remote worker.
4. Use remote execution only after the local-safe path is clean.

Recommended preflight commands:

```bash
cd hollowforge/backend
./.venv/bin/python -m pytest tests/test_sequence_run_service.py -q
./.venv/bin/python scripts/check_sequence_pipeline_preflight.py
./.venv/bin/python scripts/check_sequence_pipeline_preflight.py --executor-profile-id safe_local_preview
./.venv/bin/python -m compileall app
```

When validating the remote safe lane:

```bash
cd hollowforge/backend
./.venv/bin/python scripts/check_sequence_pipeline_preflight.py --executor-profile-id safe_remote_prod
```

When validating the remote adult lane:

```bash
cd hollowforge/backend
./.venv/bin/python scripts/check_sequence_pipeline_preflight.py --executor-profile-id adult_remote_prod
```

Use `--worker-check skip` only for local development when remote health would create a false failure and you are not trying to launch remote jobs in that session.

## Safe vs Adult Lane Separation

Do not mix lanes inside a single blueprint, run, or rough cut.

Safe lane:

- `content_mode`: `all_ages`
- Prompt profiles: `safe_hosted_grok`, `safe_openrouter_fallback`
- Executor profiles: `safe_local_preview`, `safe_remote_prod`

Adult lane:

- `content_mode`: `adult_nsfw`
- Prompt profiles: `adult_local_llm`, `adult_local_llm_strict_json`
- Executor profiles: `adult_local_preview`, `adult_remote_prod`

Operator rules:

- Do not reuse adult prompt profiles for safe runs.
- Do not reuse safe executor profiles for adult runs.
- Keep review, exports, and operator notes lane-specific.
- Treat remote worker credentials and output paths as lane-specific operational state.

## Smoke-Test Commands

Backend verification:

```bash
cd hollowforge/backend
./.venv/bin/python -m pytest tests -q
./.venv/bin/python scripts/check_sequence_pipeline_preflight.py
./.venv/bin/python -m compileall app
```

Frontend verification:

```bash
cd hollowforge/frontend
npm run test
npm run lint
npm run build
```

Minimal API smoke checks after the backend is running on `127.0.0.1:8000`:

```bash
curl -s http://127.0.0.1:8000/api/v1/sequences/blueprints | jq 'length'
curl -s http://127.0.0.1:8000/api/v1/sequences/runs | jq 'length'
```

Optional rough-cut smoke trigger for an existing run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/sequences/runs/<run_id>/start | jq '.run.id'
```

## Rough-Cut Operator Checklist

Before running rough-cut assembly:

- Confirm `scripts/check_sequence_pipeline_preflight.py` passes for the lane you intend to use.
- Confirm `HOLLOWFORGE_SEQUENCE_FFMPEG_BIN` resolves on the machine that will assemble the cut.
- Confirm the target run has clips for every planned shot.
- Confirm shot order is correct and no clip path points across lanes.
- Confirm the run is using the intended prompt profile and executor profile for its `content_mode`.
- Confirm remote worker health if the selected executor is `safe_remote_prod` or `adult_remote_prod`.

After running rough-cut assembly:

- Verify `data/sequence_runs/<run_id>/rough_cut.mp4` exists.
- Verify `data/sequence_runs/<run_id>/rough_cut_manifest.txt` contains every shot in order.
- Verify the selected rough cut is recorded on the sequence run.
- Review the cut for continuity gaps before broader sharing.
