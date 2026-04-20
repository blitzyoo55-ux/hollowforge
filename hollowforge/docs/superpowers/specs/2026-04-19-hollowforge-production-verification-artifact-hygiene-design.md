# HollowForge Production Verification Artifact Hygiene Design

Date: 2026-04-19

## Goal

Keep production verification evidence available without letting smoke-created records pollute the normal `/production` operator workflow.

This slice does not change the production-hub verification flow itself. It changes how smoke-generated records are classified and how default production listings treat them.

The outcome should be simple:

- production verification smoke runs can still create real linked records
- those records are explicitly marked as verification artifacts
- default `/production` lists and counts hide them
- operators can still retrieve them deliberately when debugging
- cleanup stays as a later explicit step, not an automatic side effect

## Current State

The repo now has a working production verification path:

- `backend/scripts/launch_production_hub_smoke.py` creates a real work, series, production episode, comic episode, and sequence blueprint
- `backend/scripts/run_production_hub_verification_suite.py` persists `suite`, `smoke_only`, and `ui_only` runs to production verification history
- `/production` now reads production verification history correctly

The remaining problem is data hygiene.

Every smoke run currently creates production-hub records that look identical to operator-created records:

- new `works`
- new `series`
- new `production_episodes`

Those records remain in the same default lists used by:

- production counts
- work and series dropdowns
- episode registry cards
- downstream handoff navigation

So every smoke run gradually contaminates the default operator surface.

## Problem Statement

The system needs two things at the same time:

1. Verification evidence must remain inspectable.
2. The production operator UI must remain focused on real operator-managed records.

If smoke records are deleted immediately, debugging and regression analysis become harder and cleanup logic becomes risky because linked comic and animation artifacts are involved.

If smoke records remain unclassified, the operator UI becomes noisier and eventually misleading.

The design therefore needs to separate:

- record visibility in normal operations
- record existence for debugging and later cleanup

## Considered Approaches

### 1. Immediate Deletion

Delete smoke-created records as soon as verification completes.

Pros:

- operator views stay clean automatically

Cons:

- cleanup must correctly remove linked `works`, `series`, `production_episodes`, `comic_episodes`, and `sequence_blueprints`
- mistakes would be destructive
- verification evidence disappears too early
- repeated failures become harder to inspect

### 2. Permanent Retention Without Classification

Leave smoke-created records in place and treat them like normal data.

Pros:

- simplest implementation
- all evidence stays available

Cons:

- `/production` becomes steadily noisier
- work and series dropdowns become polluted
- counts stop meaning what operators think they mean

### 3. Explicit Artifact Marking Plus Default Hiding

Persist smoke-created records, mark them clearly as verification artifacts, and exclude them from default production lists unless explicitly requested.

Pros:

- safe
- preserves debugging evidence
- keeps normal operator UI clean
- creates a reliable foundation for later cleanup

Cons:

- requires schema, repository, route, and UI filtering changes
- adds one more record classification concept

## Recommended Direction

Choose approach 3.

The current need is operational hygiene with low risk. The system should preserve smoke-generated data long enough to be inspected, but it should not allow those records to masquerade as normal operator-owned production state.

This means:

- mark verification artifacts explicitly
- hide them by default
- expose them only through deliberate debug retrieval
- defer deletion to a separate, explicit cleanup phase

## Proposed Design

## Record Classification

Add an explicit origin field to the top-level production records:

- `works.record_origin`
- `series.record_origin`
- `production_episodes.record_origin`

Recommended values:

- `operator`
- `verification_smoke`

The default for normal creation paths is `operator`.

The production smoke path writes `verification_smoke`.

This is more future-proof than a boolean like `is_smoke` because it leaves room for additional machine-generated or imported record types later.

## Verification Lineage

Add an optional `verification_run_id` field to the same production records:

- `works.verification_run_id`
- `series.verification_run_id`
- `production_episodes.verification_run_id`

For operator-owned records this remains `NULL`.

For smoke-created records this is set to the persisted production verification run id when available, or to the smoke execution lineage that the suite can associate with the run.

The key requirement is that a smoke-created work, series, and production episode can be traced back to one verification run.

This gives later cleanup logic a safe grouping key.

## Scope Of Marking

This slice marks only the top-level production records directly.

Linked downstream records do not need their own new origin field yet:

- `comic_episodes`
- `sequence_blueprints`

They are already linked through `production_episode_id`, so later tooling can infer that they belong to a smoke artifact by walking that relationship from a marked production episode.

That keeps the first implementation smaller while still preserving full cleanup traceability.

## Repository And API Behavior

Default production listing endpoints should exclude verification artifacts:

- `GET /api/v1/production/works`
- `GET /api/v1/production/series`
- `GET /api/v1/production/episodes`

Add a query flag:

- `include_verification_artifacts=true`

Default behavior when the flag is absent:

- return only `record_origin = 'operator'`

Behavior when the flag is true:

- return both operator records and verification artifacts

This preserves a clean operator default while still allowing explicit retrieval for debug and admin use.

## Production UI Behavior

The `/production` route should continue to behave like an operator surface, not a debug surface.

So the default UI should:

- compute top-level counts from non-artifact records only
- populate work and series dropdowns from non-artifact records only
- render the episode registry from non-artifact records only
- keep newly created operator records classified as `operator`

The initial implementation should not add a visible UI toggle for smoke artifacts.

Reasoning:

- the normal operator path should stay simple
- smoke artifact browsing is exceptional, not routine
- a backend retrieval flag is enough for the first phase

If a later phase needs a debug view, it can be added intentionally rather than leaking into the operator default.

## Smoke Script Behavior

`backend/scripts/launch_production_hub_smoke.py` should create production records with:

- `record_origin = 'verification_smoke'`
- `verification_run_id` set once the enclosing production verification run id is known

If the smoke launcher still runs independently from the suite, the implementation can stage the lineage in one of two ways:

1. create the smoke records first, then patch `verification_run_id` after the run is persisted
2. create a lightweight run lineage id first and persist that consistently through both stages

The preferred implementation is the simplest one that keeps lineage correct without changing the operator-visible verification contract.

## Cleanup Strategy

Automatic deletion is explicitly out of scope for this slice.

Instead, this design prepares cleanup for a later phase by ensuring each smoke-generated record set is:

- clearly marked
- grouped by lineage
- hidden from default operator views

The later cleanup phase should operate on `verification_run_id` groups, not on ad hoc title matching or timestamps.

That makes deletion safer and auditable.

## Migration Notes

Schema migration should:

- add `record_origin TEXT NOT NULL DEFAULT 'operator'` to `works`
- add `record_origin TEXT NOT NULL DEFAULT 'operator'` to `series`
- add `record_origin TEXT NOT NULL DEFAULT 'operator'` to `production_episodes`
- add nullable `verification_run_id TEXT` to all three tables

Existing production records will therefore remain visible by default with no manual backfill required.

## Testing Strategy

Coverage should prove both hygiene and traceability.

### Backend repository tests

Add tests for:

- listing works excludes `verification_smoke` by default
- listing series excludes `verification_smoke` by default
- listing production episodes excludes `verification_smoke` by default
- `include_verification_artifacts=true` returns both classes
- create paths persist `record_origin = 'operator'` by default

### Backend route tests

Add tests for:

- list endpoints hide smoke artifacts by default
- list endpoints include them when the query flag is present

### Smoke and suite tests

Add tests for:

- smoke-created work, series, and production episode are marked as `verification_smoke`
- verification lineage is persisted consistently enough to group smoke artifacts later

### Frontend tests

Update `/production` page tests so counts and dropdowns are calculated from the default filtered endpoints and are not inflated by verification artifacts.

## Non-Goals

This slice does not:

- automatically delete smoke-created records
- add a debug toggle to the `/production` UI
- add new origin fields to `comic_episodes` or `sequence_blueprints`
- change how production verification runs are persisted
- change the smoke story or asset generation contract

## Success Criteria

This slice is complete when all of the following are true:

- smoke-created production records are explicitly marked as verification artifacts
- normal `/production` API responses exclude those artifacts by default
- `/production` counts, dropdowns, and registry no longer drift upward from smoke runs
- verification artifacts can still be retrieved deliberately through the API
- a later cleanup phase can identify smoke-created record groups safely by lineage
