# HollowForge Production Hub Verification SOP

## When To Use This SOP

Use this flow when you need to validate the shared `/production` hub plus its linked comic and animation handoff surfaces inside the current worktree.

Use the bounded worktree stack when:

- the default `8000/5173` ports are already occupied
- you are validating a non-main checkout
- you want `/production`, `/comic`, and `/sequences` to point at the same alternate backend/frontend pair

## Default Path

1. Launch the bounded worktree stack.

```bash
cd frontend
./scripts/run-worktree-handoff-stack.sh
```

Expected runtime targets:

- backend: `http://127.0.0.1:8014`
- frontend: `http://127.0.0.1:4173`

2. Run the canonical production-hub verification suite.

```bash
cd backend
python3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014
```

3. Confirm success markers in stdout.

Expected markers:

- `stages_requested: smoke,ui`
- `stage_smoke_exit_code: 0`
- `stage_ui_exit_code: 0`
- `overall_success: true`
- `production_verification_run_persisted: true`

4. Open `/production` and confirm the Verification History panel updated.

Expected UI result:

- `Latest Suite` reflects the latest full run
- `Recent Runs` includes a `suite` row

## Fallback Reruns

Only use these after the full suite identifies the failing lane.

### Smoke Only

Use this when the issue is inside the bounded production-hub smoke path.

```bash
cd backend
python3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014 --smoke-only
```

Expected markers:

- `stages_requested: smoke`
- `stage_smoke_exit_code: 0`
- `overall_success: true`
- `production_verification_run_persisted: true`

Expected UI result:

- `Latest Smoke Only` reflects the rerun

### UI Only

Use this when the smoke lane already passed and the failure is isolated to the React test surface.

```bash
cd backend
python3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014 --ui-only
```

Expected markers:

- `stages_requested: ui`
- `stage_ui_exit_code: 0`
- `overall_success: true`
- `production_verification_run_persisted: true`

Expected UI result:

- `Recent Runs` includes a new `ui only` row

## Failure Triage

- If the suite exits non-zero before persistence, check the printed `failed_stage`.
- If `production_verification_run_persisted: false`, the stage result did not reach `/api/v1/production/verification/runs`; inspect backend reachability and API errors first.
- If the stack launcher fails, rerun `./scripts/run-worktree-handoff-stack.sh --dry-run` to confirm the port mapping before opening the browser.

## Legacy Artifact Backfill

Run this only when older smoke-created production rows still appear in the default `/production`
lists even though newer verification smoke runs are already hidden correctly.

The legacy backfill is conservative:

- dry-run is the default mode
- `--apply` is required for writes
- only obvious legacy smoke clusters are reclassified
- ambiguous clusters are reported and left unchanged
- nothing is deleted
- no historical `verification_run_id` values are invented
- Production Hub intentionally does not expose backfill write controls; run this procedure from the terminal only

Recommended operator sequence:

1. Run the dry-run first and review the matched and ambiguous ids.

```bash
cd backend
python3 scripts/backfill_legacy_production_verification_artifacts.py
```

2. If the dry-run output looks correct, run the apply step.

```bash
cd backend
python3 scripts/backfill_legacy_production_verification_artifacts.py --apply
```

3. Re-check the default and explicit artifact list surfaces after apply.

Expected result:

- default `/api/v1/production/works`
- default `/api/v1/production/series`
- default `/api/v1/production/episodes`

should stop showing the matched legacy smoke rows, while explicit artifact retrieval with
`include_verification_artifacts=true` should still return them.

## Canonical References

- suite entrypoint: `backend/scripts/run_production_hub_verification_suite.py`
- smoke stage entrypoint: `backend/scripts/launch_production_hub_smoke.py`
- legacy backfill entrypoint: `backend/scripts/backfill_legacy_production_verification_artifacts.py`
- worktree stack launcher: `frontend/scripts/run-worktree-handoff-stack.sh`
- production verification summary API: `GET /api/v1/production/verification/summary`
- production verification persistence API: `POST /api/v1/production/verification/runs`
