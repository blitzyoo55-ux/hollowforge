# HollowForge Legacy Verification Artifact Backfill Design

Date: 2026-04-19

## Goal

Reclassify only legacy smoke-created top-level production records that were created before
`record_origin` and `verification_run_id` existed, without deleting anything and without
guessing missing lineage ids.

The desired outcome is narrow:

- old smoke-created `works`, `series`, and `production_episodes` stop polluting default `/production`
- the backfill remains non-destructive
- ambiguous legacy records are reported, not modified
- future cleanup can be handled in a separate explicit slice

## Current State

The repo now has two different generations of production verification data.

New production verification smoke runs behave correctly:

- `record_origin='verification_smoke'`
- `verification_run_id` is attached through the smoke and suite lineage
- default `/production` list endpoints exclude those records unless
  `include_verification_artifacts=true`

Older smoke-created records were generated before that classification existed.
Those legacy rows still look like normal operator data:

- `record_origin='operator'`
- `verification_run_id IS NULL`
- titles such as `Smoke Work ...`, `Smoke Series ...`, and `Smoke Production Episode`

So the current operator surface is cleaner for new runs, but still polluted by old runs.

## Problem Statement

The system now has the correct ongoing behavior, but the historical data still violates the
same operator-visibility rule the new flow enforces.

The backfill has to solve two constraints at once:

1. Hide obvious legacy smoke artifacts from default operator views.
2. Avoid reclassifying legitimate operator-created records by mistake.

Because the historical rows predate `verification_run_id`, there is no reliable run-level
grouping key to reconstruct after the fact. That means this slice should prefer precision over
coverage.

If a record is clearly legacy smoke data, reclassify it.
If there is doubt, leave it unchanged and report it.

## Considered Approaches

### 1. Title-Only Backfill

Mark any `operator` production record whose title starts with `Smoke`.

Pros:

- simple implementation
- high coverage

Cons:

- too risky
- an operator could legitimately create a work or episode with a smoke-like title
- no cross-checking against linked records or the known smoke creation pattern

### 2. Strict Multi-Signal Cluster Backfill

Mark only record clusters that match the known production-hub smoke shape across work,
series, episode, and downstream linked content.

Pros:

- safer
- aligns with the actual smoke script structure
- makes accidental reclassification much less likely

Cons:

- lower coverage
- some partial or atypical legacy smoke data may remain untouched

### 3. Manual Report Only

Generate a candidate report and require hand edits or ad hoc SQL updates.

Pros:

- safest for the database

Cons:

- slow
- easy to postpone
- does not solve the current operator-noise problem without more manual work

## Recommended Direction

Choose approach 2.

This slice should optimize for correctness, not maximum automatic cleanup coverage. The
operator surface only needs the obvious legacy smoke artifacts removed from default visibility.
It does not need aggressive historical inference.

That means:

- use strict matching rules
- update only rows that match the known smoke production pattern
- leave `verification_run_id` empty for historical rows
- report ambiguous candidates instead of modifying them

## Proposed Design

## Backfill Scope

The backfill only targets top-level production records:

- `works`
- `series`
- `production_episodes`

It does not directly modify:

- `comic_episodes`
- `sequence_blueprints`
- `production_verification_runs`

Those downstream records already link through `production_episode_id`, so reclassifying the
top-level production records is enough to clean the default operator listings.

## Candidate Preconditions

A row is eligible for legacy-smoke evaluation only if all of the following are true:

- `record_origin = 'operator'`
- `verification_run_id IS NULL`

Rows already marked as `verification_smoke` are ignored.
Rows that already carry a `verification_run_id` are ignored.

This keeps the backfill idempotent and prevents it from rewriting the new correct data.

## Detection Model

The backfill should operate on linked production clusters, not isolated rows.

A cluster is anchored by a `production_episode`, then evaluated through its parent `series`,
its parent `work`, and its linked downstream comic and animation tracks.

The cluster qualifies as legacy smoke data only when it matches the known smoke script pattern:

- `work.title` starts with `Smoke Work`
- `series.title` starts with `Smoke Series`
- `production_episode.title` equals `Smoke Production Episode`
- at least one linked `comic_episode` exists with title `Smoke Comic Track`
- the top-level production records are closely time-aligned from the same creation burst

The time-alignment rule should be conservative. For example, the work, series, and episode
creation timestamps should fall within a short bounded window such as ten minutes.

Sequence blueprint linkage can be used as a supporting signal, but not as a sole classifier.
Its shape is less unique than the comic import title.

## Classification Outcomes

Each evaluated cluster ends in one of three states:

### Matched

The cluster satisfies the strict smoke signature.

Action:

- update `works.record_origin` to `verification_smoke`
- update `series.record_origin` to `verification_smoke`
- update `production_episodes.record_origin` to `verification_smoke`
- leave `verification_run_id` as `NULL`

### Ambiguous

Some but not all smoke signals are present, or the linked structure is incomplete in a way that
prevents confident classification.

Action:

- do not modify any row
- print the candidate ids and the reason it was skipped

### Non-Match

The cluster does not look like the known smoke signature.

Action:

- do nothing

## Execution Model

Add a dedicated operator script for this slice.

Proposed path:

- `backend/scripts/backfill_legacy_production_verification_artifacts.py`

The command should support two modes:

### Dry Run (default)

Read-only analysis that prints:

- matched clusters
- ambiguous clusters
- skipped counts
- the exact ids that would change

### Apply

Only when `--apply` is provided:

- execute the `record_origin` updates inside a transaction
- print the final changed ids and counts

There should be no automatic write mode by default.

## Data Rules

This slice intentionally does not fabricate missing lineage.

Do not assign a synthetic `verification_run_id` to historical rows.

Reasons:

- there is no trustworthy source for the original run id
- inventing lineage would blur the difference between real historical provenance and inferred cleanup state
- later cleanup tooling can still operate on `record_origin='verification_smoke'` for legacy clusters without pretending the original run metadata existed

## Safety Rules

The backfill must be conservative.

Required safeguards:

- default to dry-run
- `--apply` required for writes
- ignore rows already corrected
- update only rows that still satisfy the candidate preconditions at write time
- wrap all writes in one transaction
- print a clear summary before and after mutation

This is not a deletion tool.

It must not:

- delete rows
- archive rows
- rewrite titles
- patch downstream comic or animation records

## Verification Strategy

The implementation should prove two things:

1. matched legacy smoke clusters are reclassified
2. legitimate operator records remain untouched

Minimum verification coverage:

- unit tests for detection logic
- repository or script tests for dry-run reporting and apply mode
- route-level regression proving that reclassified legacy smoke records disappear from default
  `/production` lists
- live operator verification using dry-run first, then apply, then default `/production`
  endpoint checks

## Non-Goals

This slice does not include:

- destructive cleanup
- archival export
- synthetic `verification_run_id` reconstruction
- a UI for running backfills
- a general-purpose artifact browser

Those belong to later explicit operator workflows.

## Result

After this slice:

- new smoke runs remain correctly classified at creation time
- old obvious smoke records are reclassified safely
- default operator `/production` views become cleaner
- the database keeps all historical rows intact
- ambiguous history remains visible for manual review rather than being changed blindly
