# HollowForge Comic Local Benchmark Runbook

Date: 2026-04-04

This runbook covers the local four-panel benchmark helper. Its purpose is to
measure whether a full one-shot starter pass is still reasonable on the local
workstation or whether the render-heavy stage should move to a remote worker.
The helper now fails fast when a single panel render exceeds the configured
slowest-panel budget, so operators can get an execution-boundary answer without
waiting for all four panels to finish.

## Canonical Operator Order

1. Confirm the local backend is running and points at the intended local ComfyUI.
2. Confirm the intended character version is the still/comic lane, not an animation lane.
3. Run the four-panel benchmark helper with the target layout and manuscript profile.
4. Inspect the emitted benchmark report JSON.
5. Read the recommendation:
   - `stay_local`
   - `remote_worker_recommended`
   - `retry_local`
6. If the recommendation is `remote_worker_recommended`, treat local generation
   as a validation lane and move repeated full-page production renders to the
   remote worker boundary.
7. Before trusting the remote still lane, run the dedicated comic remote
   preflight and one-panel smoke helpers.

Recommended command:

```bash
cd backend
./.venv/bin/python scripts/launch_comic_four_panel_benchmark.py \
  --base-url http://127.0.0.1:8000 \
  --layout-template-id jp_2x2_v1 \
  --manuscript-profile-id jp_manga_rightbound_v1

./.venv/bin/python scripts/check_comic_remote_render_preflight.py \
  --backend-url http://127.0.0.1:8000

./.venv/bin/python scripts/launch_comic_remote_render_smoke.py \
  --base-url http://127.0.0.1:8000
```

## What The Benchmark Measures

- story planning
- story import
- render queue and selected asset materialization for all 4 panels
- dialogue generation for all 4 panels
- page assembly
- page export
- production dry-run validation
- total duration

The helper writes a JSON report under `data/comics/reports/` and includes:

- panel-by-panel render timing
- any fail-fast render-budget breach that stopped the run early
- total benchmark duration
- the selected manuscript profile and layout template ids
- the dry-run report path
- the execution-boundary recommendation and reasons

## Recommendation Meaning

- `stay_local`
  - the measured 4-panel run stayed within the current local timing budgets
- `remote_worker_recommended`
  - the local benchmark either completed over budget or hit the fail-fast panel render budget
- `retry_local`
  - the run failed outside the render-boundary decision path and should be retried after fixing the immediate local issue

Default timing budgets:

- total duration: `900s`
- average panel render duration: `120s`
- slowest panel render duration: `180s`

These can be overridden from the CLI if the workstation budget changes.
If the slowest-panel budget is exceeded during `queue-renders`, the helper exits
immediately, writes the report, and marks the recommendation as
`remote_worker_recommended`.

## Remote Follow-up

When the benchmark points to `remote_worker_recommended`, the next operator step
is no longer another local render retry. Use:

- `scripts/check_comic_remote_render_preflight.py`
  - confirms the local backend is reachable, the worker is reachable, the
    callback base URL is a valid worker-facing `http(s)` HollowForge address,
    verifies that callback base through `/api/v1/system/health`, and confirms
    the worker token is present when the worker enforces auth; auth probing may
    return `SKIP` when the worker does not expose the undocumented
    `GET /api/v1/jobs` probe
- `scripts/launch_comic_remote_render_smoke.py`
  - imports one short comic episode, queues `execution_mode=remote_worker` for a
    single panel, polls callback-driven materialization, and requires at least
    one real selected asset

The remote smoke helper keeps its own backend URL inside the local workstation
boundary. The preflight helper also keeps `--backend-url` local, but
`HOLLOWFORGE_PUBLIC_API_BASE_URL` must remain worker-reachable for real remote
workers; loopback is only valid when the worker is co-located with HollowForge.
