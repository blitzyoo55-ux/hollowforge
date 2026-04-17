# HollowForge Comic Verification Profile Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split one-panel comic verification into a fast `smoke` path and a full `remote_worker` verification path while keeping the verification defaults enforced by tests.

**Architecture:** Introduce a small shared verification-profile resolver that owns the default execution contract, then add a dedicated `launch_comic_one_panel_smoke.py` entrypoint that reuses the one-panel flow with the `smoke` profile. Keep `launch_comic_one_panel_verification.py` as the `full` runtime entrypoint and preserve `launch_comic_remote_render_smoke.py` as the remote-lane-only checker.

**Tech Stack:** Python CLI scripts, pytest, existing HollowForge comic orchestration helpers.

---

## File Structure

### New files

- `backend/scripts/comic_verification_profiles.py`
  Shared profile defaults and resolver helpers for `smoke` and `full`.
- `backend/scripts/launch_comic_one_panel_smoke.py`
  Fast one-panel smoke entrypoint that forces the `smoke` profile.
- `backend/tests/test_launch_comic_one_panel_smoke.py`
  CLI regression test that locks the `smoke` profile defaults and success markers.

### Modified files

- `backend/scripts/launch_comic_one_panel_verification.py`
  Read defaults from the shared profile resolver and remain the `full` entrypoint.
- `backend/scripts/launch_comic_remote_render_smoke.py`
  Keep remote-lane defaults explicit and aligned with the shared `full` runtime budget when appropriate.
- `backend/tests/test_launch_comic_one_panel_verification.py`
  Assert the `full` defaults remain `remote_worker` with the long poll budget.
- `backend/tests/test_launch_comic_remote_render_smoke.py`
  Keep the long remote render budget pinned.

## Task 1: Add Shared Verification Profile Contract

**Files:**
- Create: `backend/scripts/comic_verification_profiles.py`
- Test: `backend/tests/test_launch_comic_one_panel_verification.py`
- Test: `backend/tests/test_launch_comic_one_panel_smoke.py`

- [ ] **Step 1: Write the failing tests for `smoke` vs `full` defaults**

Add assertions that make the current missing profile contract visible.

```python
assert remote_queue_calls[0]["poll_attempts"] == 240
assert remote_queue_calls[0]["poll_sec"] == 2.0
assert local_queue_calls[0]["panel_id"] == "panel-1"
```

For the new smoke script, assert:

```python
assert "execution_mode: local_preview" in captured.out
assert local_queue_calls[0]["candidate_count"] == 1
assert local_queue_calls[0]["poll_attempts"] == 12
assert local_queue_calls[0]["poll_sec"] == 0.5
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python3 -m pytest \
  backend/tests/test_launch_comic_one_panel_verification.py \
  backend/tests/test_launch_comic_one_panel_smoke.py \
  backend/tests/test_launch_comic_remote_render_smoke.py
```

Expected:

- `test_launch_comic_one_panel_smoke.py` fails because the script does not exist yet
- or the default profile assertions fail because the shared contract is not implemented

- [ ] **Step 3: Implement the shared profile resolver**

Create `backend/scripts/comic_verification_profiles.py` with a minimal typed contract.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ComicVerificationProfile:
    name: str
    execution_mode: str
    candidate_count: int
    render_poll_attempts: int
    render_poll_sec: float
    requires_materialized_asset: bool


SMOKE_PROFILE = ComicVerificationProfile(
    name="smoke",
    execution_mode="local_preview",
    candidate_count=1,
    render_poll_attempts=12,
    render_poll_sec=0.5,
    requires_materialized_asset=False,
)

FULL_PROFILE = ComicVerificationProfile(
    name="full",
    execution_mode="remote_worker",
    candidate_count=1,
    render_poll_attempts=240,
    render_poll_sec=2.0,
    requires_materialized_asset=True,
)
```

Also expose a tiny helper:

```python
def get_profile(name: str) -> ComicVerificationProfile:
    ...
```

- [ ] **Step 4: Run the targeted tests to verify the contract layer is usable**

Run:

```bash
python3 -m pytest \
  backend/tests/test_launch_comic_one_panel_verification.py \
  backend/tests/test_launch_comic_remote_render_smoke.py
```

Expected:

- existing tests still fail only where the new smoke entrypoint is not implemented
- no import errors from the new shared resolver

- [ ] **Step 5: Commit the shared contract**

```bash
git add \
  backend/scripts/comic_verification_profiles.py \
  backend/tests/test_launch_comic_one_panel_verification.py \
  backend/tests/test_launch_comic_remote_render_smoke.py
git commit -m "feat: add comic verification profile defaults"
```

## Task 2: Add Dedicated One-Panel Smoke Entrypoint

**Files:**
- Create: `backend/scripts/launch_comic_one_panel_smoke.py`
- Create: `backend/tests/test_launch_comic_one_panel_smoke.py`
- Modify: `backend/scripts/launch_comic_one_panel_verification.py`
- Test: `backend/tests/test_launch_comic_one_panel_verification.py`

- [ ] **Step 1: Write the failing smoke entrypoint test**

Create `backend/tests/test_launch_comic_one_panel_smoke.py` that mirrors the one-panel verification style but asserts `smoke` defaults.

```python
assert module.main() == 0
assert "execution_mode: local_preview" in captured.out
assert "dry_run_success: true" in captured.out
assert local_queue_calls == [{
    "panel_id": "panel-1",
    "candidate_count": 1,
    "poll_attempts": 12,
    "poll_sec": 0.5,
}]
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run:

```bash
python3 -m pytest backend/tests/test_launch_comic_one_panel_smoke.py -v
```

Expected:

- FAIL because `launch_comic_one_panel_smoke.py` does not exist yet

- [ ] **Step 3: Extract or reuse the one-panel flow with a profile-aware entrypoint**

Implement `backend/scripts/launch_comic_one_panel_smoke.py` as a thin wrapper around the existing one-panel flow.

Preferred shape:

```python
from comic_verification_profiles import SMOKE_PROFILE
import launch_comic_one_panel_verification as one_panel_verification


def main() -> int:
    return one_panel_verification.main_with_profile(SMOKE_PROFILE)
```

If a small refactor is needed, add a helper inside `launch_comic_one_panel_verification.py`:

```python
def main_with_profile(profile: ComicVerificationProfile) -> int:
    ...
```

Requirements:

- `launch_comic_one_panel_verification.py` keeps `full` as its default
- `launch_comic_one_panel_smoke.py` forces `smoke`
- smoke path still performs dialogue, assembly, export, and dry-run checks

- [ ] **Step 4: Run smoke and verification tests to verify both profiles behave correctly**

Run:

```bash
python3 -m pytest \
  backend/tests/test_launch_comic_one_panel_smoke.py \
  backend/tests/test_launch_comic_one_panel_verification.py -v
```

Expected:

- both tests PASS
- `smoke` path uses `local_preview`
- `full` path keeps `remote_worker`

- [ ] **Step 5: Commit the new smoke entrypoint**

```bash
git add \
  backend/scripts/launch_comic_one_panel_smoke.py \
  backend/scripts/launch_comic_one_panel_verification.py \
  backend/tests/test_launch_comic_one_panel_smoke.py \
  backend/tests/test_launch_comic_one_panel_verification.py
git commit -m "feat: add one-panel smoke verification entrypoint"
```

## Task 3: Align Remote Render Smoke With Shared Defaults

**Files:**
- Modify: `backend/scripts/launch_comic_remote_render_smoke.py`
- Test: `backend/tests/test_launch_comic_remote_render_smoke.py`

- [ ] **Step 1: Write or tighten the failing regression if the script still hardcodes full defaults**

Pin the shared runtime values in the test:

```python
assert queue_calls[0]["poll_attempts"] == 240
assert queue_calls[0]["poll_sec"] == 2.0
```

If the test already exists, keep it as the red check by temporarily observing the failure before wiring the shared resolver.

- [ ] **Step 2: Run the targeted remote render smoke test to verify the failure mode**

Run:

```bash
python3 -m pytest backend/tests/test_launch_comic_remote_render_smoke.py -v
```

Expected:

- FAIL if the script is still disconnected from the shared profile defaults
- otherwise confirm the regression is already locked and move to implementation

- [ ] **Step 3: Wire the script to the shared `full` profile defaults**

Update the script to import from `comic_verification_profiles.py` and read:

```python
DEFAULT_RENDER_POLL_ATTEMPTS = FULL_PROFILE.render_poll_attempts
DEFAULT_RENDER_POLL_SEC = FULL_PROFILE.render_poll_sec
```

Keep the remote-render-specific behavior otherwise unchanged.

- [ ] **Step 4: Run the remote render smoke test to verify it passes**

Run:

```bash
python3 -m pytest backend/tests/test_launch_comic_remote_render_smoke.py -v
```

Expected:

- PASS

- [ ] **Step 5: Commit the remote render smoke alignment**

```bash
git add \
  backend/scripts/launch_comic_remote_render_smoke.py \
  backend/tests/test_launch_comic_remote_render_smoke.py
git commit -m "refactor: share full comic verification defaults"
```

## Task 4: Final Verification

**Files:**
- Modify: none expected
- Verify: `backend/scripts/launch_comic_one_panel_smoke.py`
- Verify: `backend/scripts/launch_comic_one_panel_verification.py`
- Verify: `backend/scripts/launch_comic_remote_render_smoke.py`

- [ ] **Step 1: Run the focused pytest suite**

Run:

```bash
python3 -m pytest \
  backend/tests/test_launch_comic_one_panel_smoke.py \
  backend/tests/test_launch_comic_one_panel_verification.py \
  backend/tests/test_launch_comic_remote_render_smoke.py
```

Expected:

- all tests PASS

- [ ] **Step 2: Run the fast one-panel smoke against the local backend**

Run:

```bash
python3 backend/scripts/launch_comic_one_panel_smoke.py --base-url http://127.0.0.1:8012
```

Expected markers:

- `execution_mode: local_preview`
- `overall_success: true`
- `dry_run_success: true`

- [ ] **Step 3: Run the full one-panel verification against the local backend**

Run:

```bash
python3 backend/scripts/launch_comic_one_panel_verification.py --base-url http://127.0.0.1:8012
```

Expected markers:

- `execution_mode: remote_worker`
- `materialized_asset_count: 1`
- `overall_success: true`

- [ ] **Step 4: Run the remote render lane smoke against the local backend**

Run:

```bash
python3 backend/scripts/launch_comic_remote_render_smoke.py --base-url http://127.0.0.1:8012
```

Expected markers:

- `execution_mode: remote_worker`
- `queue_renders_success: true`
- `overall_success: true`

- [ ] **Step 5: Commit the final verified state**

```bash
git add \
  backend/scripts/comic_verification_profiles.py \
  backend/scripts/launch_comic_one_panel_smoke.py \
  backend/scripts/launch_comic_one_panel_verification.py \
  backend/scripts/launch_comic_remote_render_smoke.py \
  backend/tests/test_launch_comic_one_panel_smoke.py \
  backend/tests/test_launch_comic_one_panel_verification.py \
  backend/tests/test_launch_comic_remote_render_smoke.py
git commit -m "feat: split comic smoke and full verification flows"
```
