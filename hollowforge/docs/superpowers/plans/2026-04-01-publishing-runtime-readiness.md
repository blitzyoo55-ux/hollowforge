# Publishing Runtime Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make HollowForge publishing caption generation operational on the current worktree by syncing runtime publishing env keys, verifying publishing readiness is `full`, and generating one real caption variant against the branch backend.

**Architecture:** Keep `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.env` as the canonical secret source and mirror only an allowlisted subset into the current worktree `backend/.env`. Build one small env-sync utility, one publishing-caption smoke utility, and thread a publishing-readiness check into the existing ops baseline runner. Capture the live rerun evidence in the existing ops pilot log and retro without committing generated runtime data.

**Tech Stack:** Python 3.12, FastAPI, pytest, urllib, existing HollowForge ops scripts, Markdown ops docs

---

## File Map

- Create: `backend/scripts/sync_runtime_env.py`
  - sync allowlisted publishing env keys from the canonical runtime backend env into the current worktree backend env
- Create: `backend/tests/test_sync_runtime_env.py`
  - lock allowlist, dry-run, and missing-source behavior
- Create: `backend/scripts/run_publishing_caption_smoke.py`
  - check `/api/v1/publishing/readiness`, optionally readiness-only, and run one live caption generation against a selected ready generation id
- Create: `backend/tests/test_run_publishing_caption_smoke.py`
  - lock readiness parsing, fail-fast behavior, and successful caption smoke summaries
- Modify: `backend/scripts/run_ops_pilot_baseline.py`
  - add publishing readiness to the baseline checks and rendered baseline section
- Modify: `backend/tests/test_run_ops_pilot_baseline.py`
  - cover the new publishing-readiness line and new check ordering
- Modify: `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`
  - record the readiness `full` result and first successful caption variant evidence
- Modify: `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-retro.md`
  - update the bottleneck and outcome after the live caption rerun

## Implementation Notes

- Use `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python` for backend test and script commands.
- Treat `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.env` as canonical.
- Treat `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend/.env` as disposable worktree-local state.
- The default live caption smoke target should be generation id `7056ca96-dc29-4421-996d-ca2fc47d7894`, because that id is already recorded as the selected ready generation in the current ops pilot log. Keep `--generation-id` override support.
- Do not commit anything under `data/`.
- The ops pilot docs are already operator-owned files. Extend them carefully; do not rewrite earlier evidence blocks unless the new live result makes an old statement incorrect.

### Task 1: Add Runtime Publishing Env Sync Utility

**Files:**
- Create: `backend/scripts/sync_runtime_env.py`
- Test: `backend/tests/test_sync_runtime_env.py`

- [ ] **Step 1: Write the failing env-sync tests**

Create `backend/tests/test_sync_runtime_env.py` with focused tests for:

```python
def test_sync_runtime_env_copies_only_allowlisted_keys(tmp_path: Path) -> None:
    ...
    assert "OPENROUTER_API_KEY=present" in printed_status
    assert "UNRELATED_SECRET" not in target_contents


def test_sync_runtime_env_dry_run_does_not_write_target(tmp_path: Path) -> None:
    ...
    assert not target_path.exists()


def test_sync_runtime_env_fails_when_source_env_missing(tmp_path: Path) -> None:
    ...
    assert exit_code == 1
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_sync_runtime_env.py -q
```

Expected: FAIL because `sync_runtime_env.py` does not exist yet.

- [ ] **Step 3: Implement the minimal env-sync utility**

Create `backend/scripts/sync_runtime_env.py` with:

```python
ALLOWED_KEYS = (
    "OPENROUTER_API_KEY",
    "MARKETING_PROVIDER_NAME",
    "MARKETING_MODEL",
    "MARKETING_PROMPT_VERSION",
    "HOLLOWFORGE_PUBLIC_API_BASE_URL",
)

DEFAULT_SOURCE_ENV = Path("/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.env")
DEFAULT_TARGET_ENV = Path(__file__).resolve().parents[1] / ".env"
```

Required behavior:

- parse simple `KEY=VALUE` lines
- copy only allowlisted keys from source to target
- preserve no other runtime secrets
- support `--dry-run`
- support `--print-status`
- print `present` or `missing`, never real values

- [ ] **Step 4: Run the env-sync tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_sync_runtime_env.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/scripts/sync_runtime_env.py backend/tests/test_sync_runtime_env.py
git commit -m "feat(hollowforge): add publishing env sync utility"
```

### Task 2: Add Live Publishing Caption Smoke Utility

**Files:**
- Create: `backend/scripts/run_publishing_caption_smoke.py`
- Test: `backend/tests/test_run_publishing_caption_smoke.py`

- [ ] **Step 1: Write the failing caption-smoke tests**

Create `backend/tests/test_run_publishing_caption_smoke.py` with focused tests for:

```python
def test_readiness_only_mode_reports_full_without_generating_caption() -> None:
    ...
    assert "readiness_mode: full" in stdout
    assert "caption_id:" not in stdout


def test_smoke_fails_fast_when_readiness_is_not_full() -> None:
    ...
    assert exit_code == 1
    assert "draft_only" in stdout_or_stderr


def test_smoke_reports_created_caption_metadata() -> None:
    ...
    assert "caption_id: caption-123" in stdout
    assert "provider: openrouter" in stdout
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_publishing_caption_smoke.py -q
```

Expected: FAIL because `run_publishing_caption_smoke.py` does not exist yet.

- [ ] **Step 3: Implement the minimal smoke utility**

Create `backend/scripts/run_publishing_caption_smoke.py` using `urllib.request` like `launch_story_planner_smoke.py`.

Required CLI:

```python
parser.add_argument("--base-url", default="http://127.0.0.1:8000")
parser.add_argument("--generation-id", default="7056ca96-dc29-4421-996d-ca2fc47d7894")
parser.add_argument("--platform", default="pixiv")
parser.add_argument("--tone", default="teaser")
parser.add_argument("--channel", default="social_short")
parser.add_argument("--approved", action="store_true")
parser.add_argument("--readiness-only", action="store_true")
```

Required output labels:

```text
readiness_mode: full
provider: openrouter
model: x-ai/grok-2-vision-1212
generation_id: ...
caption_id: ...
approved: false
```

Behavior:

- call `/api/v1/publishing/readiness`
- fail immediately unless readiness mode is `full`
- in `--readiness-only` mode, stop after printing readiness labels
- otherwise call `POST /api/v1/publishing/generations/{generation_id}/captions/generate`
- when `--approved` is present, send `approved=true` in the caption-generation payload; otherwise leave it false

- [ ] **Step 4: Run the caption-smoke tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_publishing_caption_smoke.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add backend/scripts/run_publishing_caption_smoke.py backend/tests/test_run_publishing_caption_smoke.py
git commit -m "feat(hollowforge): add publishing caption smoke utility"
```

### Task 3: Thread Publishing Readiness Into Ops Baseline

**Files:**
- Modify: `backend/scripts/run_ops_pilot_baseline.py`
- Modify: `backend/tests/test_run_ops_pilot_baseline.py`

- [ ] **Step 1: Extend the baseline tests first**

Update `backend/tests/test_run_ops_pilot_baseline.py` to cover:

```python
def test_render_baseline_section_includes_publishing_readiness_line() -> None:
    ...
    assert "- publishing readiness: PASS - mode=full provider=openrouter model=x-ai/grok-2-vision-1212" in rendered


def test_build_check_specs_includes_readiness_only_caption_smoke() -> None:
    ...
    assert "--readiness-only" in specs[...].command
```

- [ ] **Step 2: Run the baseline tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_ops_pilot_baseline.py -q
```

Expected: FAIL because the baseline runner does not yet know about publishing readiness.

- [ ] **Step 3: Implement the baseline integration**

Update `backend/scripts/run_ops_pilot_baseline.py` to:

- add a new `publishing readiness` check
- invoke `scripts/run_publishing_caption_smoke.py --readiness-only`
- parse labels like:

```text
readiness_mode: full
provider: openrouter
model: x-ai/grok-2-vision-1212
```

- render the baseline section in this order:
  - backend tests
  - frontend tests
  - adult provider resolution
  - publishing readiness
  - story planner smoke

- [ ] **Step 4: Run the baseline tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_run_ops_pilot_baseline.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add backend/scripts/run_ops_pilot_baseline.py backend/tests/test_run_ops_pilot_baseline.py
git commit -m "feat(hollowforge): add publishing readiness baseline check"
```

### Task 4: Prove Live Caption Success And Capture Ops Evidence

**Files:**
- Modify: `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`
- Modify: `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-retro.md`

- [ ] **Step 1: Sync the worktree backend env from the canonical runtime env**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/sync_runtime_env.py --print-status
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/sync_runtime_env.py
```

Expected: allowlisted publishing keys report `present`, especially `OPENROUTER_API_KEY`.

- [ ] **Step 2: Start the branch backend on a separate local port**

Run in a dedicated session:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
HOLLOWFORGE_PUBLIC_API_BASE_URL=http://127.0.0.1:8010 \
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Expected: branch backend listens on `127.0.0.1:8010`.

- [ ] **Step 3: Run the baseline with publishing readiness enabled**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/run_ops_pilot_baseline.py --base-url http://127.0.0.1:8010 --ui-base-url http://127.0.0.1:5173
```

Expected: `publishing readiness: PASS - mode=full ...` appears and the baseline section in the ops pilot log is updated.

- [ ] **Step 4: Run the live caption smoke**

Before running the smoke, confirm the default generation id `7056ca96-dc29-4421-996d-ca2fc47d7894` still exists in the current worktree dataset and is still the intended ready target. If it is not, pick a replacement ready generation id and pass it explicitly with `--generation-id`.

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/run_publishing_caption_smoke.py --base-url http://127.0.0.1:8010 --generation-id 7056ca96-dc29-4421-996d-ca2fc47d7894
```

Expected: PASS with a real `caption_id`, provider, model, and generation id summary.

- [ ] **Step 5: Update the ops pilot log and retro**

In `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`, extend the existing `## Publishing Pilot` section with:

```markdown
- publishing readiness: full
- caption variant id: <real id>
- caption provider/model: <provider> / <model>
- approved caption id: <id or none>
```

In `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-retro.md`, update:

- outcome from partial success to closed-loop success if caption generation really worked
- bottleneck text so it no longer claims the runtime is missing `OPENROUTER_API_KEY`
- next branch recommendation if the runtime bottleneck is actually cleared

- [ ] **Step 6: Stop the temporary backend and commit only intentional doc changes**

Stop the `8010` backend session, then:

```bash
git add docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-retro.md
git commit -m "docs(hollowforge): capture publishing caption runtime proof"
```

Important:

- do not add `data/`
- do not add generated runtime artifacts
- inspect the doc diff carefully so only the intended evidence updates are committed

### Task 5: Run Final Targeted Verification

**Files:**
- No new files

- [ ] **Step 1: Run the targeted backend test suite**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_sync_runtime_env.py tests/test_run_publishing_caption_smoke.py tests/test_run_ops_pilot_baseline.py tests/test_publishing_routes.py tests/test_publishing_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Re-run the env sync status and readiness-only smoke**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/sync_runtime_env.py --print-status
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/run_publishing_caption_smoke.py --base-url http://127.0.0.1:8010 --readiness-only
```

Expected: publishing keys present and readiness mode `full`.

- [ ] **Step 3: Verify working tree scope**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge
git status --short
```

Expected:

- only intended feature files are committed or staged
- `data/` remains untracked or otherwise excluded from commits
- no accidental tracked secret file content is staged

- [ ] **Step 4: Commit verification-only fixups if needed**

If final test or documentation fixups were needed:

```bash
git add <relevant files>
git commit -m "test(hollowforge): verify publishing runtime readiness"
```

If no fixups were needed, skip this commit.
