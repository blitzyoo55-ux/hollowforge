# Story Planner Support Anchoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize freeform support identity in the Story Planner anchor path and make smoke evaluation follow the planner-recommended anchor shot instead of a misleading first-completed establishing frame.

**Architecture:** Keep the existing Story Planner request and response contract, but synthesize a deterministic identity pack for `source_type="freeform"` support entries inside the planner service. Then align `launch_story_planner_smoke.py` with the same intended operator path by removing hardcoded support mismatch, surfacing planner recommendation explicitly, and printing the recommended-shot generations as the primary review target.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, pytest, existing HollowForge Story Planner service and CLI scripts

---

## Implementation Notes

- Primary target subtree: `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge`
- Existing unrelated dirtiness is expected in:
  - `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-brief.md`
  - `data/`
- Do not revert or include those files in feature commits.
- Backend tests should use:
  - `/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python`
- Do not change:
  - checkpoint selection
  - workflow lane
  - CFG/steps/sampler defaults
  - publishing or caption flows
- Freeform support synthesis must stay deterministic:
  - same `story_prompt + freeform_description + lane + location + lead` inputs produce the same metadata
- Registry characters remain authoritative:
  - only `source_type="freeform"` support entries get synthesized metadata
- If `--support-description` is omitted in smoke, do not inject a replacement string
- Smoke output should make this obvious:
  - planner recommendation
  - recommendation reason
  - generation ids for the recommended shot
  - full queued shot list as secondary detail

## File Map

- Modify: `backend/app/services/story_planner_service.py`
  - add deterministic freeform support identity synthesis and wire it into planner resolution
- Modify: `backend/tests/test_story_planner_service.py`
  - lock freeform support synthesis behavior and lead/support separation guarantees
- Create: `backend/tests/test_launch_story_planner_smoke.py`
  - cover prompt-derived support behavior and recommended-shot-first CLI output
- Modify: `backend/scripts/launch_story_planner_smoke.py`
  - remove mismatched hardcoded support default, surface planner recommendation, and print recommended-shot generations first
- Optional modify: `backend/tests/test_run_ops_pilot_baseline.py`
  - only if smoke output labels change enough to require baseline parser updates

## Task 1: Add Failing Planner Tests For Freeform Support Synthesis

**Files:**
- Modify: `backend/tests/test_story_planner_service.py`
- Modify: `backend/app/services/story_planner_service.py`

- [ ] **Step 1: Add a failing test that freeform support metadata is no longer blank**

Append a focused test to `backend/tests/test_story_planner_service.py` like:

```python
def test_plan_story_episode_synthesizes_metadata_for_freeform_support() -> None:
    request = StoryPlannerPlanRequest(
        story_prompt=(
            "Hana Seo pauses in a locked corridor while a quiet attendant "
            "watches for her next move."
        ),
        lane="adult_nsfw",
        cast=[
            StoryPlannerCastInput(
                role="lead",
                source_type="registry",
                character_id="hana_seo",
            ),
            StoryPlannerCastInput(
                role="support",
                source_type="freeform",
                freeform_description="quiet bathhouse attendant in a dark robe with damp hair",
            ),
        ],
    )

    preview = plan_story_episode(request)
    support = next(member for member in preview.resolved_cast if member.role == "support")

    assert support.canonical_anchor
    assert support.anti_drift
    assert support.wardrobe_notes
    assert support.personality_notes
```

- [ ] **Step 2: Add a failing test that support anti-drift explicitly separates it from the lead**

Add another test like:

```python
def test_plan_story_episode_freeform_support_anti_drift_separates_support_from_lead() -> None:
    preview = plan_story_episode(_build_request_with_freeform_support())

    lead = next(member for member in preview.resolved_cast if member.role == "lead")
    support = next(member for member in preview.resolved_cast if member.role == "support")

    assert lead.anti_drift
    assert "do not mirror the lead" in support.anti_drift.lower()
```

- [ ] **Step 3: Add a failing test for vague freeform support fallback**

Add a minimal-input test like:

```python
def test_plan_story_episode_vague_freeform_support_still_gets_minimal_identity_pack() -> None:
    request = StoryPlannerPlanRequest(
        story_prompt="Hana Seo waits while someone lingers near the door.",
        lane="adult_nsfw",
        cast=[
            StoryPlannerCastInput(role="lead", source_type="registry", character_id="hana_seo"),
            StoryPlannerCastInput(role="support", source_type="freeform", freeform_description="attendant"),
        ],
    )

    preview = plan_story_episode(request)
    support = next(member for member in preview.resolved_cast if member.role == "support")

    assert support.canonical_anchor
    assert support.anti_drift
```

- [ ] **Step 4: Run the targeted planner tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_story_planner_service.py -q
```

Expected: FAIL because freeform support metadata is still `none`.

- [ ] **Step 5: Implement deterministic support synthesis in the planner service**

In `backend/app/services/story_planner_service.py`, add small helpers rather than one large block:

```python
def _synthesize_freeform_support_identity(
    *,
    support_description: str,
    story_prompt: str,
    lane: str,
    location: StoryPlannerResolvedLocationEntry,
    lead: StoryPlannerResolvedCastEntry | None,
) -> dict[str, str]:
    ...


def _apply_freeform_support_identity(
    *,
    resolved_cast: list[StoryPlannerResolvedCastEntry],
    story_prompt: str,
    lane: str,
    location: StoryPlannerResolvedLocationEntry,
) -> list[StoryPlannerResolvedCastEntry]:
    ...
```

Implementation rules:

- only run for support entries where:
  - `role == "support"`
  - `source_type == "freeform"`
- preserve existing `freeform_description`
- generate:
  - `canonical_anchor`
  - `anti_drift`
  - `wardrobe_notes`
  - `personality_notes`
- if a lead is present, `anti_drift` must explicitly separate support from the lead
- if the freeform description is sparse, fall back to:
  - a minimal adult secondary figure anchor
  - non-empty anti-drift
- keep the implementation deterministic and string-template-based

- [ ] **Step 6: Wire the synthesized metadata into the planner response**

Apply the helper inside the planner flow after cast resolution and before response assembly, so:

- `resolved_cast` already includes any prompt merge behavior
- synthesized freeform support metadata appears in:
  - planner preview
  - route output
  - anchor prompt compilation

- [ ] **Step 7: Run the targeted planner tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_story_planner_service.py -q
```

Expected: PASS for the new support synthesis tests.

- [ ] **Step 8: Commit the planner synthesis work**

```bash
git add backend/app/services/story_planner_service.py backend/tests/test_story_planner_service.py
git commit -m "feat(hollowforge): anchor freeform support identities"
```

## Task 2: Add Failing Smoke CLI Tests For Evaluation Alignment

**Files:**
- Create: `backend/tests/test_launch_story_planner_smoke.py`
- Modify: `backend/scripts/launch_story_planner_smoke.py`
- Optional modify: `backend/tests/test_run_ops_pilot_baseline.py`

- [ ] **Step 1: Create a failing smoke CLI test file**

Create `backend/tests/test_launch_story_planner_smoke.py` with focused tests like:

```python
def test_smoke_omits_support_cast_when_support_description_is_not_provided(monkeypatch, capsys) -> None:
    ...
    assert payload["cast"] == [
        {"role": "lead", "source_type": "registry", "character_id": "hana_seo"},
    ]


def test_smoke_prints_recommended_shot_section_before_full_queue(monkeypatch, capsys) -> None:
    ...
    assert "recommended_anchor_shot_no: 3" in stdout
    assert "recommended_shot_generations:" in stdout
    assert "shot_03:" in stdout


def test_smoke_keeps_explicit_support_description_when_operator_provides_one(monkeypatch, capsys) -> None:
    ...
    assert support_payload["freeform_description"] == "quiet attendant in a dark robe"
```

Keep these tests near the script boundary:

- patch `_request_json`
- invoke `main()`
- inspect captured stdout and the payloads sent to the planner route

- [ ] **Step 2: Run the new smoke CLI tests to verify they fail**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_launch_story_planner_smoke.py -q
```

Expected: FAIL because the script still injects a hardcoded support default and does not emit a recommended-shot section.

- [ ] **Step 3: Remove the hardcoded support mismatch from `launch_story_planner_smoke.py`**

Change CLI parsing so `--support-description` is optional:

```python
parser.add_argument("--support-description", default=None)
```

Then build `cast` like:

```python
cast = [
    {
        "role": "lead",
        "source_type": "registry",
        "character_id": args.lead_character_id,
    }
]

if args.support_description:
    cast.append(
        {
            "role": "support",
            "source_type": "freeform",
            "freeform_description": args.support_description,
        }
    )
```

Do not inject any substitute support string when the operator omitted one.

- [ ] **Step 4: Add explicit recommended-shot output**

Extend `launch_story_planner_smoke.py` to print:

```python
print("recommended_anchor:")
print(f"recommended_anchor_shot_no: {plan.get('recommended_anchor_shot_no')}")
print(f"recommended_anchor_reason: {plan.get('recommended_anchor_reason')}")
print("recommended_shot_generations:")
print(f"shot_{recommended_shot:02d}: {recommended_generation_ids}")
```

Implementation rules:

- `recommended_shot_generations` must be derived from `queue_result["queued_shots"]`
- if the planner recommendation is missing or invalid, raise a `RuntimeError`
- keep the full queued shot list output, but print it after the recommended-shot section

- [ ] **Step 5: Update baseline parser tests only if output labels changed**

Inspect `backend/tests/test_run_ops_pilot_baseline.py`.

- If existing smoke summary parsing still works unchanged, leave it alone.
- If parsing depends on moved labels, add the minimum failing test and update the parser.

- [ ] **Step 6: Run the smoke CLI tests again**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest tests/test_launch_story_planner_smoke.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit the smoke alignment work**

```bash
git add backend/scripts/launch_story_planner_smoke.py backend/tests/test_launch_story_planner_smoke.py backend/tests/test_run_ops_pilot_baseline.py
git commit -m "fix(hollowforge): align story planner smoke evaluation"
```

If `test_run_ops_pilot_baseline.py` was untouched, omit it from `git add`.

## Task 3: Verify End-To-End Planner And Smoke Behavior

**Files:**
- Modify: none unless verification exposes a real bug
- Test: `backend/tests/test_story_planner_service.py`
- Test: `backend/tests/test_launch_story_planner_smoke.py`
- Test: `backend/tests/test_story_planner_routes.py`

- [ ] **Step 1: Run the targeted backend verification suite**

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python -m pytest \
  tests/test_story_planner_service.py \
  tests/test_story_planner_routes.py \
  tests/test_launch_story_planner_smoke.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run a live smoke against the branch backend**

If the branch backend is not already running, start it separately first.

Run:

```bash
cd /Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/.worktrees/hollowforge-adult-grok-default-provider-local-20260331/hollowforge/backend
/Users/mori_arty/AI_Projects/04_AI_Creative/nsfw-market-research/hollowforge/backend/.venv/bin/python scripts/launch_story_planner_smoke.py \
  --base-url http://127.0.0.1:8010 \
  --lane adult_nsfw \
  --story-prompt "Hana Seo pauses in a locked corridor while a quiet attendant watches for her next move, steam catching the tiled wall."
```

Expected:

- `recommended_anchor:` section is printed
- `recommended_shot_generations:` is printed
- no hardcoded support mismatch is introduced when `--support-description` is omitted

- [ ] **Step 3: Inspect one planner response or workflow snapshot for support metadata**

Confirm that the selected plan or queued generation now carries non-empty support
metadata in the planner response or prompt context, especially:

- `support_canonical_anchor`
- `support_anti_drift`
- `support_wardrobe_notes`
- `support_personality_notes`

- [ ] **Step 4: Commit any final verification-driven fix**

If no additional code change was needed, skip this commit.

If a small verification fix was required:

```bash
git add <exact files>
git commit -m "fix(hollowforge): tighten support anchoring verification"
```

## Final Verification Checklist

- [ ] Freeform support entries no longer return all-`none` identity metadata
- [ ] Support anti-drift explicitly separates support from the lead
- [ ] Smoke no longer injects a mismatched hardcoded support description by default
- [ ] Smoke prints the planner-recommended review path explicitly
- [ ] Targeted backend tests pass
- [ ] Live smoke output is legible enough that operators review the intended recommended shot first
