# Pilot Rerun Close Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a script-reproducible `adult_nsfw` pilot rerun that creates one fresh asset, marks it ready, generates and approves one caption, creates one linked draft publish job, and writes dedicated rerun ops evidence.

**Architecture:** Build one thin Python orchestration script that talks directly to existing HollowForge HTTP routes instead of shelling out to the earlier smoke scripts. Reuse the current route contracts for story planning, generation polling, ready toggling, caption generation, caption approval, and draft publish creation; keep evidence writing in dedicated rerun log and retro files so the earlier runtime-readiness proof stays intact.

**Tech Stack:** Python 3.12, FastAPI HTTP routes, urllib, pytest, Markdown ops docs, existing HollowForge backend scripts

---

## File Map

- Create: `backend/scripts/run_pilot_rerun_close_loop.py`
  - orchestrate the fresh `adult_nsfw` rerun from planning through draft publish creation
- Create: `backend/tests/test_run_pilot_rerun_close_loop.py`
  - lock sequencing, deterministic selection, failure short-circuiting, and rerun doc rendering
- Create: `docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-log.md`
  - record the fresh rerun fixture, selected generation, caption, approval, and publish-job evidence
- Create: `docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-retro.md`
  - capture the outcome, remaining friction, and next branch recommendation after the fresh rerun
- Modify: `backend/tests/test_publishing_routes.py`
  - add focused route coverage only for any approval or linked draft contract the orchestrator depends on and that is not already explicitly locked

## Existing Route And Script Contracts To Reuse

- `GET /api/v1/publishing/readiness`
- `POST /api/v1/tools/story-planner/plan`
- `POST /api/v1/tools/story-planner/generate-anchors`
- `GET /api/v1/generations/{generation_id}/status`
- `GET /api/v1/generations/{generation_id}`
- `POST /api/v1/generations/{generation_id}/ready`
- `POST /api/v1/publishing/generations/{generation_id}/captions/generate`
- `POST /api/v1/publishing/captions/{caption_id}/approve`
- `POST /api/v1/publishing/posts`
- Reference patterns only:
  - `backend/scripts/launch_story_planner_smoke.py`
  - `backend/scripts/run_publishing_caption_smoke.py`

## Implementation Notes

- Use `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python` for backend commands.
- Keep the default fixture stable:
  - `lane=adult_nsfw`
  - `lead_character_id=hana_seo`
  - fixed freeform support description
  - fixed bathhouse/corridor-aligned story prompt
  - `candidate_count=2`
  - `select_shot=1`
  - `select_candidate=1`
  - `platform=pixiv`
  - `tone=teaser`
  - `channel=social_short`
- The happy path must use a fresh rerun. Do not default to reusing an old ready generation.
- Poll generation completion at a fixed interval of `2s` with a hard timeout of `300s`.
- Treat a generation that does not reach `completed` within `300s` as a hard failure.
- The runner should print labeled sections:
  - `readiness_result`
  - `plan_result`
  - `queue_result`
  - `selected_generation`
  - `ready_result`
  - `caption_result`
  - `approval_result`
  - `publish_job_result`
- The runner should stop at the first failed state transition, but print every prior id and summary it already obtained.
- Do not print secrets. Do not commit anything under `data/`.

### Task 1: Add Failing Tests For The Closed-Loop Orchestrator

**Files:**
- Create: `backend/tests/test_run_pilot_rerun_close_loop.py`

- [ ] **Step 1: Write the failing orchestrator tests**

Create `backend/tests/test_run_pilot_rerun_close_loop.py` with focused tests for:

```python
def test_runner_selects_requested_shot_and_candidate_deterministically() -> None:
    ...
    assert selected_generation_id == "gen-shot1-cand1"


def test_runner_stops_when_selected_generation_never_reaches_completed() -> None:
    ...
    assert exit_code == 1
    assert "selected_generation" in stdout
    assert "caption_result" not in stdout


def test_runner_calls_ready_caption_approve_and_publish_in_order() -> None:
    ...
    assert calls == [
        ("POST", "/api/v1/tools/story-planner/plan"),
        ("POST", "/api/v1/tools/story-planner/generate-anchors"),
        ("GET", "/api/v1/generations/gen-shot1-cand1/status"),
        ("GET", "/api/v1/generations/gen-shot1-cand1"),
        ("POST", "/api/v1/generations/gen-shot1-cand1/ready"),
        ("POST", "/api/v1/publishing/generations/gen-shot1-cand1/captions/generate"),
        ("POST", "/api/v1/publishing/captions/caption-123/approve"),
        ("POST", "/api/v1/publishing/posts"),
    ]


def test_runner_renders_rerun_log_and_retro_with_ids() -> None:
    ...
    assert "caption variant id: caption-123" in log_text
    assert "publish job id: publish-job-123" in log_text
    assert "closed-loop success" in retro_text
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_pilot_rerun_close_loop.py -q
```

Expected: FAIL because `run_pilot_rerun_close_loop.py` does not exist yet.

- [ ] **Step 3: Commit only after the implementation task below passes**

Do not commit in this task. The new tests should be committed together with the first working orchestrator implementation.

### Task 2: Implement The Closed-Loop Orchestrator

**Files:**
- Create: `backend/scripts/run_pilot_rerun_close_loop.py`
- Create: `backend/tests/test_run_pilot_rerun_close_loop.py`
- Modify: `backend/tests/test_publishing_routes.py`

- [ ] **Step 1: Implement the runner skeleton with fixed defaults and labeled output**

Create `backend/scripts/run_pilot_rerun_close_loop.py` with:

```python
parser.add_argument("--base-url", default="http://127.0.0.1:8000")
parser.add_argument("--ui-base-url", default="http://127.0.0.1:5173")
parser.add_argument("--story-prompt", default="...")
parser.add_argument("--lane", default="adult_nsfw")
parser.add_argument("--candidate-count", type=int, default=2)
parser.add_argument("--lead-character-id", default="hana_seo")
parser.add_argument("--support-description", default="...")
parser.add_argument("--select-shot", type=int, default=1)
parser.add_argument("--select-candidate", type=int, default=1)
parser.add_argument("--platform", default="pixiv")
parser.add_argument("--tone", default="teaser")
parser.add_argument("--channel", default="social_short")
parser.add_argument("--log-path")
parser.add_argument("--retro-path")
```

Implement small helpers inside the script for:

- `_request_json(...)`
- `_wait_for_generation_completion(...)`
- `_select_generation_id(...)`
- `_render_rerun_log(...)`
- `_render_rerun_retro(...)`

The runner should call routes directly rather than shelling out to existing scripts.

- [ ] **Step 2: Wire the route flow in order**

Implement this exact flow:

1. `GET /api/v1/publishing/readiness` and fail unless `degraded_mode == "full"`
2. `POST /api/v1/tools/story-planner/plan`
3. `POST /api/v1/tools/story-planner/generate-anchors`
4. deterministically select the requested shot/candidate generation id
5. poll `GET /api/v1/generations/{generation_id}/status` until `completed`
   - use a `2s` polling cadence
   - fail after `300s` instead of waiting indefinitely
6. confirm `GET /api/v1/generations/{generation_id}` returns a source image path
7. `POST /api/v1/generations/{generation_id}/ready`
8. `POST /api/v1/publishing/generations/{generation_id}/captions/generate`
9. `POST /api/v1/publishing/captions/{caption_id}/approve`
10. `POST /api/v1/publishing/posts` with `status="draft"` and the approved caption id

- [ ] **Step 3: Add any missing focused route tests only if they are truly needed**

If the orchestrator depends on publish approval or linked draft behavior not already
explicitly locked, add focused route tests such as:

```python
async def test_approve_caption_route_marks_selected_caption_approved(...):
    ...


async def test_create_draft_publish_job_accepts_approved_caption_variant_id(...):
    ...
```

Keep this bounded. Do not expand publishing coverage beyond the contracts the runner uses.

- [ ] **Step 4: Run the targeted tests**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_pilot_rerun_close_loop.py tests/test_publishing_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/scripts/run_pilot_rerun_close_loop.py backend/tests/test_run_pilot_rerun_close_loop.py backend/tests/test_publishing_routes.py
git commit -m "feat(hollowforge): add pilot rerun close loop runner"
```

### Task 3: Run One Fresh Live Rerun And Capture Dedicated Ops Evidence

**Files:**
- Create: `docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-log.md`
- Create: `docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-retro.md`

- [ ] **Step 1: Prepare the branch backend runtime**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/sync_runtime_env.py --print-status
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/sync_runtime_env.py
HOLLOWFORGE_PUBLIC_API_BASE_URL=http://127.0.0.1:8010 /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Expected:

- `OPENROUTER_API_KEY=present`
- branch backend reachable on `127.0.0.1:8010`

Execution note:

- start the `uvicorn` command in a dedicated terminal session or background job
  and keep it running while Step 2 and Step 3 execute

- [ ] **Step 2: Verify readiness before the rerun**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/run_publishing_caption_smoke.py --base-url http://127.0.0.1:8010 --readiness-only
```

Expected:

```text
readiness_mode: full
provider: openrouter
model: ...
```

- [ ] **Step 3: Execute the fresh rerun**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/run_pilot_rerun_close_loop.py --base-url http://127.0.0.1:8010 --ui-base-url http://127.0.0.1:5173
```

Expected labeled output includes fresh ids:

```text
selected_generation:
generation_id: ...
caption_result:
caption_id: ...
approval_result:
approved_caption_id: ...
publish_job_result:
publish_job_id: ...
```

- [ ] **Step 4: Write dedicated rerun ops docs from the live result**

Create `docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-log.md` with:

- fixture summary
- queued generation ids
- selected generation id
- caption variant id
- approved caption id
- draft publish job id
- confirmation that the path completed without manual UI intervention

Create `docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-retro.md` with:

- outcome
- what still hurt
- evidence
- recommended next branch

- [ ] **Step 5: Stop the temporary backend and commit only the rerun evidence docs**

Stop the `8010` backend, then:

```bash
git add docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-log.md docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-retro.md
git commit -m "docs(hollowforge): capture fresh pilot rerun proof"
```

Important:

- do not add `data/`
- do not modify the earlier runtime-readiness pilot docs in this task

### Task 4: Run Final Targeted Verification

**Files:**
- No new files

- [ ] **Step 1: Run the targeted backend suite**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_pilot_rerun_close_loop.py tests/test_publishing_routes.py tests/test_run_publishing_caption_smoke.py tests/test_run_ops_pilot_baseline.py -q
```

Expected: PASS.

- [ ] **Step 2: Re-check publishing readiness on the branch backend**

With the temporary backend running again if needed, run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/run_publishing_caption_smoke.py --base-url http://127.0.0.1:8010 --readiness-only
```

Expected: `readiness_mode: full`

- [ ] **Step 3: Verify the rerun evidence docs exist and contain the essential ids**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge
rg -n "generation id|caption variant id|approved caption id|publish job id" docs/superpowers/ops/2026-04-02-hollowforge-pilot-rerun-log.md
```

Expected: all four evidence lines are present.

- [ ] **Step 4: Inspect worktree status before handing off**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge
git status --short
```

Expected:

- only intentional tracked changes are present
- `data/` remains untracked and uncommitted if it changed during the live rerun

- [ ] **Step 5: Do not create an extra verification commit**

If Task 2 and Task 3 commits already exist and verification passes, stop here and hand off to branch-finishing choice.
