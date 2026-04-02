# HollowForge Pilot Rerun Close Loop Design

## Goal

Prove HollowForge can rerun one fresh `adult_nsfw` pilot from scripted inputs all the
way through:

- story planning
- anchor still generation
- ready queue selection
- caption generation
- caption approval
- linked draft publish job creation

The result must be reproducible by CLI, not dependent on the operator clicking through
the UI by hand.

## Why This Branch Exists

The previous pilot and runtime-readiness work closed the environment problem:

- publishing readiness now reports `full`
- live caption generation works against the branch backend

What is still missing is a fresh-asset proof. The recent caption success reused an
already-ready generation, which means HollowForge still lacks a repeatable scripted
path from new story prompt to approved caption and linked draft publish evidence.

## Current Context

- `backend/scripts/run_ops_pilot_baseline.py` already verifies backend tests,
  frontend tests, adult provider defaults, publishing readiness, and story planner
  smoke.
- `backend/scripts/launch_story_planner_smoke.py` already exercises story planner
  plan plus anchor queue creation.
- `backend/scripts/run_publishing_caption_smoke.py` already proves caption generation
  against a chosen ready generation.
- The publishing API already supports:
  - `POST /api/v1/generations/{generation_id}/ready`
  - `POST /api/v1/publishing/generations/{generation_id}/captions/generate`
  - `POST /api/v1/publishing/captions/{caption_id}/approve`
  - `POST /api/v1/publishing/posts`
- The current ops retro says the next highest-value branch is a clean rerun that
  carries one fresh asset through the full lane without workaround.

## Non-Goals

- external publisher integration
- animation flow changes
- character or episode schema redesign
- prompt quality tuning as a product goal
- replacing existing UI workbenches

This branch is about operational proof, not expanding product scope.

## Approaches Considered

### 1. Single End-To-End Runner

One large script does every step directly.

This is fast to create, but debugging becomes brittle because one failure hides which
domain broke. It also produces poor reuse for later ops automation.

### 2. Small Step Scripts Plus Thin Orchestrator

Use narrowly-scoped scripts or helper functions for each state transition, then add a
single orchestration runner that wires them together.

This is the recommended approach. It preserves debuggability, fits the current
HollowForge ops-script pattern, and creates reusable primitives for later pilot and
publishing automation.

### 3. UI-First Pilot With CLI Evidence Only

Keep the real pilot manual in the UI and use scripts only for readiness and logging.

This stays close to current operator behavior, but it does not satisfy the explicit
goal of a script-reproducible closed loop.

## Recommendation

Use approach 2.

The branch should add one thin orchestrator:

- `backend/scripts/run_pilot_rerun_close_loop.py`

It should reuse existing scripts where possible and add only the minimum new
step-specific helpers required to close the loop.

## Scope

This branch will do four things:

1. add a script-reproducible rerun path for one fresh `adult_nsfw` pilot using a
   fixed default fixture with CLI overrides
2. move one newly generated asset to `publish_approved=1`
3. generate and approve one caption variant for that asset, then create one linked
   draft publish job
4. record the rerun evidence in dedicated rerun ops log and retro files

This branch will not:

- require UI clicks for the happy path
- overwrite the earlier runtime-readiness pilot docs
- choose assets manually based on taste or visual review

## Default Fixture

The rerun should have stable defaults so it is deterministic enough for ops use.

- `lane`: `adult_nsfw`
- `lead_character_id`: `hana_seo`
- `support_description`: one fixed freeform support description
- `story_prompt`: one fixed adult fixture prompt aligned with the current bathhouse
  / corridor setting language already used in pilot work
- `candidate_count`: a small fixed count
- selection rule: `shot 1`, `candidate 1`
- publishing defaults:
  - `platform=pixiv`
  - `tone=teaser`
  - `channel=social_short`

Every default must remain overridable by CLI flag.

## Components

### 1. Story Planner Pilot Step

Reuse the story planner plan and anchor queue path to create a fresh pilot result.

The runner must capture at minimum:

- selected lane
- policy pack id
- queued generation ids

It must then select one generation deterministically rather than asking a human to
choose visually.

### 2. Ready Queue Step

The selected generation must be moved into ready state through the existing generation
ready route.

The runner must record:

- selected generation id
- resulting `publish_approved` state
- `curated_at` if returned

### 3. Caption Generation Step

The runner must call the publishing caption route for the selected generation only
after readiness is confirmed.

The runner must record:

- `caption_variant_id`
- provider
- model
- approval state returned at creation time

### 4. Caption Approval Step

The runner must explicitly approve the generated caption variant, even if the caption
was initially created unapproved.

The runner must record:

- approved caption id
- final approved state

### 5. Draft Publish Step

The runner must create one draft publish job linked to the selected generation and the
approved caption id.

The runner must record:

- publish job id
- publish job status
- linked caption variant id

### 6. Ops Evidence Writer

This branch should not overwrite the earlier runtime-readiness proof files.

Instead it should write to new rerun-specific docs:

- `docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-log.md`
- `docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-retro.md`

These files should capture:

- fixture summary
- generation ids produced
- selected generation id
- caption variant id
- approved caption id
- publish job id
- whether the rerun closed the loop without manual UI intervention

## Orchestrator Flow

The intended CLI flow is:

1. verify the backend is reachable and publishing readiness is `full`
2. execute the story planner plan request with the default fixture or overrides
3. queue anchor generations
4. select one generation deterministically
5. wait until the selected generation is complete and has a source image
6. toggle that generation into ready state
7. generate one caption variant
8. approve that caption variant
9. create one linked draft publish job
10. write rerun log and retro evidence

The orchestrator should stop at the first failed state transition, but preserve all
previous ids and summaries in console output so reruns are easy to debug.

## CLI Shape

Add one orchestration script:

- `backend/scripts/run_pilot_rerun_close_loop.py`

Recommended flags:

- `--base-url`
- `--ui-base-url`
- `--story-prompt`
- `--lane`
- `--candidate-count`
- `--lead-character-id`
- `--support-description`
- `--select-shot`
- `--select-candidate`
- `--platform`
- `--tone`
- `--channel`
- `--log-path`
- `--retro-path`

The runner should print stable labeled sections such as:

- `plan_result`
- `queue_result`
- `selected_generation`
- `ready_result`
- `caption_result`
- `approval_result`
- `publish_job_result`

The essential end-state ids are:

- `generation_id`
- `caption_variant_id`
- `publish_job_id`

## Failure Policy

Failure handling should be strict and operator-readable.

- If planning fails, stop immediately.
- If queueing returns zero generations, stop immediately.
- If the selected generation never reaches a usable completed state, stop immediately.
- If ready toggle fails, stop immediately.
- If caption generation fails, stop immediately.
- If caption approval fails, stop immediately.
- If draft publish creation fails, stop immediately.

Even on failure, the runner should still print every successful earlier step and every
known id so the operator knows where the loop broke.

## Success Criteria

This branch is successful only if all of the following are true:

1. a fresh `adult_nsfw` pilot run is launched from scripted inputs
2. one newly generated asset is moved into ready state
3. one caption variant is created for that fresh asset
4. that caption variant is explicitly approved
5. one draft publish job is created and linked to the approved caption
6. rerun-specific ops log and retro files capture the full closed-loop evidence

## Failure Conditions

This branch is not complete if any of the following remain true:

- the happy path still requires manual UI clicks
- the selected asset is not fresh from the current scripted rerun
- caption generation works but approval or draft publish creation still has to be done
  manually
- the rerun succeeds once but leaves no durable ops evidence in dedicated rerun docs

## Testing Strategy

### Targeted Tests

Add focused tests for:

- orchestrator step sequencing
- deterministic generation selection
- failure short-circuiting at each major step
- rerun log and retro rendering

HTTP interactions should be stubbed at the helper boundary so the tests cover control
flow rather than the live backend.

### Route Or Service Tests

Only add targeted backend tests if the current publish approval or draft creation
contracts are not already sufficiently covered.

The branch should avoid broad test-suite expansion unless a contract gap appears during
implementation.

### Live Verification

The required acceptance proof is a live rerun against the branch backend that produces:

- a fresh generation id
- a new caption variant id
- a new approved caption id
- a new draft publish job id

Those ids must appear both in CLI output and in the rerun ops docs.

## Safety Rules

- Do not print or persist secrets in tracked files.
- Do not reuse an old generation unless the runner is explicitly invoked in recovery
  mode later; the default path must use a fresh rerun.
- Do not overwrite earlier ops pilot files that serve different purposes.
- Keep the orchestrator thin; reusable step logic should remain independently testable.

## Planning Notes

The implementation plan for this spec should stay bounded to three work areas:

1. add the rerun orchestration and any missing step helpers
2. add targeted tests for sequencing, failure handling, and doc rendering
3. run one live rerun and capture dedicated ops evidence

Anything beyond those three areas is scope drift for this branch.
