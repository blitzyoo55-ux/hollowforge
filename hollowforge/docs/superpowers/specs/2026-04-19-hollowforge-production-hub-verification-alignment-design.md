# HollowForge Production Hub Verification Alignment Design

Date: 2026-04-19

## Goal

Align the `/production` operator surface with the actual canonical verification path that now exists for the shared production core.

This design does not add a new creative workflow. It fixes an operations mismatch:

- the canonical runtime check is now `launch_production_hub_smoke.py`
- the canonical verification suite is now `run_production_hub_verification_suite.py`
- but the `/production` page still exposes comic-only commands and comic-only verification history

The outcome of this slice should be simple:

- `/production` shows production-hub verification commands
- `/production` reads production-hub verification history
- the persisted verification contract uses production-hub terminology instead of comic-only terminology

## Current State

The current repo state is split in two directions.

What is already correct:

- `backend/scripts/launch_production_hub_smoke.py` verifies linked production/comic/animation records against a live backend
- `backend/scripts/run_production_hub_verification_suite.py` runs the canonical `smoke -> ui` suite
- `frontend/scripts/run-worktree-handoff-stack.sh` is the bounded alternate-port stack used for worktree validation
- `/production` is already positioned as the shared production-core route

What is still misaligned:

- `frontend/src/components/production/VerificationOpsCard.tsx` still shows comic verification commands
- `frontend/src/components/production/VerificationHistoryPanel.tsx` still loads `getProductionComicVerificationSummary()`
- `backend/app/routes/production.py` still exposes `/production/comic-verification/*`
- `backend/app/services/production_comic_verification_repository.py` and related response models are comic-only in naming and intent

So the UI shell says "Production Hub" while the verification data contract still says "Comic Verification".

## Problem Statement

This mismatch creates three operator problems.

### 1. The wrong command path is promoted

The production page currently teaches the operator to run the comic verification suite even though the canonical production-core verification path is now different.

### 2. The history panel is semantically wrong

The history card labels and run modes are based on comic verification concepts like `preflight`, `full_only`, and `remote_only`, which do not describe the production-hub suite.

### 3. The contract is coupled to the wrong boundary

The shared production-core route should be the source of truth for shared verification state. As long as the persistence and API contract are comic-only, the route boundary is misleading.

## Considered Approaches

### 1. UI Text Swap Only

Replace the command strings and labels in the `/production` page, but keep the current comic verification history API and storage model.

Pros:

- smallest code change
- quick visual alignment

Cons:

- history remains semantically wrong
- operators can still misread stored verification results
- the route contract stays tied to the wrong production boundary

### 2. Dedicated Production Hub Verification Surface

Introduce production-hub-specific verification storage and API responses, then point `/production` to that surface.

Pros:

- `/production` becomes operationally truthful
- commands, persisted history, and labels all refer to the same workflow
- preserves room to keep comic-only verification as a separate lane if needed later

Cons:

- requires backend and frontend changes together
- duplicates some structure already used by comic verification

### 3. Fully Generic Multi-Surface Verification Framework

Generalize verification history into one abstract framework shared by comic, production, and future surfaces.

Pros:

- maximally reusable

Cons:

- too much abstraction for the current gap
- slows down the immediate production-hub fix
- risks over-design before a second real consumer exists

## Recommended Direction

Choose approach 2: dedicated production-hub verification surface.

The current need is accuracy, not abstraction. The production page should describe and persist production-hub verification data directly. If a later phase proves that comic and production verification histories need to share one generic backend, that refactor can happen with real usage in hand.

## Proposed Design

## Backend Contract

Add a production-hub-specific verification contract beside the existing comic one.

New persisted concepts:

- `ProductionVerificationRunCreate`
- `ProductionVerificationRunResponse`
- `ProductionVerificationSummaryResponse`
- `ProductionVerificationStageStatusResponse`

Recommended run modes:

- `suite`
- `smoke_only`
- `ui_only`

Recommended summary shape:

- `latest_smoke_only`
- `latest_suite`
- `recent_runs`

Reasoning:

- the production-hub suite currently has two operator-visible execution shapes: full suite and isolated reruns
- the current script does not expose a separate production preflight concept, so the summary should not invent one

Persist these runs in a production-hub-specific table rather than reusing the comic verification table. The production page is the shared-core surface and should not depend on comic-lane naming.

## Backend Routes

Under `backend/app/routes/production.py`, add production-hub verification endpoints such as:

- `POST /api/v1/production/verification/runs`
- `GET /api/v1/production/verification/summary`

Keep the existing comic verification endpoints untouched for now. This avoids mixing meanings and keeps migration risk low.

## Frontend API And UI

Update the production-only UI to use production-hub verification terminology.

### Verification Ops

Replace comic verification commands with production-hub commands:

- worktree stack launcher
- canonical production-hub verification suite
- smoke-only rerun
- ui-only rerun

The SOP path should also point at a production-hub-specific runbook, not the comic operator SOP.

### Verification History

Change the data source from comic verification summary to production verification summary.

Update labels so the cards reflect the actual workflow:

- `Latest Smoke Only`
- `Latest Suite`
- `Recent Runs`

The run-mode label mapper should understand `suite`, `smoke_only`, and `ui_only`.

## Testing Strategy

The change should be covered at the same three boundaries already used by the current stack.

### Backend repository tests

Add tests for:

- latest smoke-only selection
- latest suite selection
- recent run ordering
- stage-status JSON round-trip

### Backend route tests

Add tests for:

- creating a production verification run
- fetching production verification summary

### Frontend tests

Update `/production` tests to assert:

- the ops panel shows production-hub commands
- the history panel renders production-hub summary cards
- the route no longer promotes comic verification terminology on the production page

## Non-Goals

This slice does not:

- replace the comic verification suite
- merge all verification systems into one generic framework
- add browser-triggered verification execution from the UI
- change the underlying `smoke -> ui` production-hub suite logic

## Success Criteria

This slice is complete when all of the following are true:

- `/production` promotes only production-hub verification commands
- `/production` history reflects persisted production-hub runs
- route and model names no longer describe production verification as comic verification
- the existing production-hub suite remains green after the refactor
