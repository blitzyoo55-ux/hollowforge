# HollowForge Publishing Runtime Readiness Design

## Goal

Make HollowForge publishing caption generation operational in a repeatable way by:

- treating the runtime `backend/.env` as the canonical source for publishing secrets
- mirroring only the required publishing keys into the current worktree backend env
- proving branch-local publishing readiness returns `full`
- generating at least one real `caption_variant` against the branch backend

## Why This Branch Exists

The `adult_nsfw` pilot already proved the path from story planning to anchor generation to ready queue to draft publish job. The first real operator failure was caption generation, which stopped at missing `OPENROUTER_API_KEY`. The readiness and degrade work is now in place, so the next highest-value gap is runtime secret readiness rather than more UI or planner work.

## Current Context

- The production/runtime backend already loads `backend/.env` automatically in `backend/app/config.py`.
- The current runtime repo path has a real `OPENROUTER_API_KEY` entry in `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.env`.
- The current worktree does not yet have its own `backend/.env`.
- The publishing domain now exposes `GET /api/v1/publishing/readiness` and cleanly degrades caption generation when readiness is not available.
- The remaining missing proof is a repeatable path from runtime secret source to branch-local caption success.

## Non-Goals

- Keychain integration
- key rotation workflows
- external publisher integration
- animation executor changes
- broader provider abstraction beyond the current OpenRouter-based publishing caption path

## Approaches Considered

### 1. Manual Mirror And Manual Rerun

Read the runtime `backend/.env`, copy values by hand into the worktree, then manually rerun readiness and caption generation.

This is the fastest path once, but it is too easy to drift and does not create a dependable operator workflow.

### 2. Canonical Runtime `.env` Plus Sync, Preflight, And Live Caption Smoke

Use the runtime `backend/.env` as the canonical source, mirror only an allowlisted subset into the worktree backend env, then run explicit readiness and caption smoke checks.

This is the recommended approach. It keeps the secret model simple, aligns with the current backend configuration behavior, and creates a repeatable path for future pilot reruns.

### 3. Launchd Or External Env Injection Rework

Move canonical secret handling into launchd plist configuration or another external env source.

This may become useful later, but it is too large for the current goal and would delay proving the first live caption success.

## Recommendation

Use approach 2.

The canonical source remains the runtime backend env file at:

- `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.env`

The current worktree backend env becomes a branch-local mirror only:

- `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend/.env`

## Scope

This branch will do four things:

1. Add an env sync path that copies only publishing-related allowlisted keys from the runtime backend env into the current worktree backend env.
2. Extend ops baseline verification so publishing readiness is explicitly checked and recorded as `full` or `draft_only`.
3. Add a live caption smoke path that fails fast when readiness is not `full` and otherwise attempts one real caption generation against the branch backend.
4. Record the resulting evidence in the existing ops pilot log and retro so the next operator can tell whether the loop is truly closed.

This branch will not:

- store real secret values in tracked files
- change the canonical provider choice away from the current OpenRouter publishing path
- redesign the ready queue or publishing UI again

## Components

### 1. Runtime Env Sync

Add a backend script that:

- reads the canonical runtime env file
- writes only an allowlisted subset into the current worktree backend env file
- supports a dry-run or status mode that reports `present` or `missing` without printing values

The initial allowlist should be narrowly scoped to the publishing path:

- `OPENROUTER_API_KEY`
- `MARKETING_PROVIDER_NAME`
- `MARKETING_MODEL`
- `MARKETING_PROMPT_VERSION`
- `HOLLOWFORGE_PUBLIC_API_BASE_URL` only if needed for local verification consistency

The script must not blindly copy the entire runtime env file.

### 2. Publishing Readiness Baseline

Extend the existing baseline runner so it explicitly checks:

- `GET /api/v1/publishing/readiness`
- whether the returned mode is `full`
- whether the current provider and model are visible in the response

This check belongs in the same operator baseline flow as the existing backend tests, adult provider resolution, story planner smoke, and frontend tests.

### 3. Live Caption Smoke

Add a backend script that:

- calls `/api/v1/publishing/readiness`
- exits immediately if readiness is not `full`
- targets one selected ready generation id
- calls `POST /api/v1/publishing/generations/{generation_id}/captions/generate`
- reports the created caption id, provider, model, and approval state without dumping the full secret environment

This script is the operational proof that publishing caption generation works end-to-end on the branch backend.

### 4. Ops Documentation

Update the existing ops pilot log and retro so they show:

- the env sync status
- publishing readiness `full`
- the first successful `caption_variant` id
- whether the caption was later approved or merely generated

If any rerun step still fails, the retro should identify whether the problem is env sync, runtime readiness, provider behavior, or data selection.

## Execution Flow

The intended branch-local operator flow is:

1. Sync allowlisted env keys from the runtime backend env into the current worktree backend env.
2. Start the branch backend on a separate local port.
3. Run the ops baseline and confirm publishing readiness returns `full`.
4. Run the live caption smoke against a ready generation id.
5. Record the created caption id and result summary in the ops pilot log and retro.

## CLI Shape

Two scripts are sufficient.

### `sync_runtime_env.py`

Responsibilities:

- sync allowlisted keys from canonical runtime `backend/.env`
- support `--dry-run`
- support `--print-status`

Output should be state-only, for example:

- `OPENROUTER_API_KEY=present`
- `MARKETING_MODEL=present`

### `run_publishing_caption_smoke.py`

Responsibilities:

- verify publishing readiness first
- require `full` mode before attempting caption generation
- run one live caption generation against a specific ready generation id
- summarize the result in a stable human-readable form

The generation id should be overridable by flag, even if the script has a convenient default for the current pilot dataset.

## Success Criteria

This branch is successful only if all of the following are true:

1. The worktree backend env can be recreated from the runtime backend env without manual secret copying.
2. The branch backend reports `full` from `/api/v1/publishing/readiness`.
3. The baseline runner records the publishing readiness check in the ops pilot log.
4. The live caption smoke successfully creates at least one real `caption_variant`.
5. The ops pilot log and retro record enough evidence for a future operator to confirm the loop was closed.

## Failure Conditions

The branch is not complete if any of the following remain true:

- the env sync path requires manual secret editing each time
- publishing readiness still returns `draft_only`
- caption generation still fails with `503`, provider refusal, or other runtime errors before one real caption is stored
- the live success occurs once but leaves no durable operator evidence in the ops docs

## Testing Strategy

### Targeted Tests

- env sync script tests for allowlist behavior, dry-run behavior, and missing-source handling
- caption smoke parsing and readiness-gate tests
- existing publishing route tests remain green

### Live Verification

Run the branch backend on a dedicated local port and execute:

- env sync status check
- baseline runner with publishing readiness verification
- live caption smoke for one ready generation id

The live caption smoke is the required acceptance proof for this branch.

### Documentation Verification

Confirm the ops pilot log and retro contain:

- readiness result
- caption generation result
- concrete ids and statuses

## Safety Rules

- Never write real secret values into tracked files.
- Never print secret values in test output, logs, or docs.
- Only copy allowlisted keys from the runtime env file.
- Treat the runtime backend env as canonical and the worktree backend env as disposable branch-local state.
- Record presence, readiness, ids, and statuses only.

## Planning Notes

The implementation plan for this spec should stay focused on three bounded work areas:

1. env sync and status reporting
2. publishing readiness baseline integration
3. live caption smoke plus ops evidence capture

Anything beyond those three areas is scope drift for this branch.
