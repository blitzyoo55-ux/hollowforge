# Adult Grok Default Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Switch the `adult_nsfw` prompt-facing default in HollowForge to an OpenRouter-backed Grok profile while keeping sequence runtime defaults on the existing local-LLM path.

**Architecture:** Add one new adult prompt-provider profile in the shared registry, split Prompt Factory adult default resolution away from sequence runtime defaults, and align Story Planner adult policy metadata to the same profile id. Keep the runtime boundary explicit: Prompt Factory and Story Planner metadata change, but `sequence_run_service.py` default selection does not.

**Tech Stack:** FastAPI, Pydantic v2, existing Prompt Factory service, Story Planner JSON assets, pytest, local `.venv`

---

## Scope Notes

This is one backend-only slice with one small operator-doc update:

- prompt-provider registry and config resolution
- Prompt Factory default-path behavior
- Story Planner adult policy metadata
- docs note for the new prompt-facing env split

Do **not** widen this plan into sequence runtime changes. `backend/app/services/sequence_run_service.py` and `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md` are verification references, not modification targets.

## File Structure Map

### Backend

- Modify: `backend/app/config.py`
- Modify: `backend/app/services/sequence_registry.py`
- Modify: `backend/app/services/prompt_factory_service.py`
- Modify: `backend/app/story_planner_assets/policy_packs.json`
- Modify: `backend/tests/test_sequence_registry.py`
- Modify: `backend/tests/test_story_planner_catalog.py`
- Modify: `backend/tests/test_story_planner_routes.py`

### Docs

- Modify: `docs/GROK_PROMPT_FACTORY_20260311.md`

### Verify Only

- Check only: `backend/app/services/sequence_run_service.py`
- Check only: `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md`
- Check only: `docs/superpowers/specs/2026-03-31-adult-grok-default-provider-design.md`

## Task 1: Add the Adult Grok Prompt Profile and Split Adult Default Settings

**Files:**
- Modify: `backend/tests/test_sequence_registry.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/sequence_registry.py`

- [ ] **Step 1: Write the failing registry/default tests**

Add these assertions to `backend/tests/test_sequence_registry.py`:

```python
def test_adult_openrouter_grok_profile_is_registered() -> None:
    profile = get_prompt_provider_profile("adult_openrouter_grok", content_mode="adult_nsfw")
    assert profile["provider_kind"] == "openrouter"
    assert profile["structured_json"] is True
    assert profile["strict_json"] is False


def test_prompt_factory_capabilities_use_prompt_facing_adult_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(settings, "XAI_API_KEY", "xai-key")
    monkeypatch.setattr(
        settings,
        "HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE",
        "adult_openrouter_grok",
    )
    monkeypatch.setattr(
        settings,
        "HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL",
        "x-ai/grok-4.1-fast",
    )

    capabilities = prompt_factory_service.get_prompt_factory_capabilities()
    defaults_by_mode = {item.content_mode: item for item in capabilities.content_mode_defaults}

    assert defaults_by_mode["adult_nsfw"].prompt_provider_profile_id == "adult_openrouter_grok"
    assert defaults_by_mode["adult_nsfw"].provider_kind == "openrouter"
    assert defaults_by_mode["adult_nsfw"].model == "x-ai/grok-4.1-fast"
    assert defaults_by_mode["adult_nsfw"].ready is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q
```

Expected: FAIL because the adult Grok profile and prompt-facing adult settings do not exist yet.

- [ ] **Step 3: Add the new config keys and registry profile**

Update `backend/app/config.py` to add:

```python
HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE: str = os.getenv(
    "HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE",
    "adult_openrouter_grok",
).strip() or "adult_openrouter_grok"
HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL: str = os.getenv(
    "HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL",
    "x-ai/grok-4.1-fast",
).strip() or "x-ai/grok-4.1-fast"
```

Update `backend/app/services/sequence_registry.py` to register:

```python
"adult_openrouter_grok": {
    "id": "adult_openrouter_grok",
    "content_mode": "adult_nsfw",
    "provider_kind": "openrouter",
    "structured_json": True,
    "strict_json": False,
},
```

- [ ] **Step 4: Run the tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q
```

Expected: PASS for the new registry/default assertions. Existing sequence-default assertions should still pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/services/sequence_registry.py backend/tests/test_sequence_registry.py
git commit -m "feat(hollowforge): add adult grok prompt profile"
```

## Task 2: Route Prompt Factory Adult Defaults Through the New Grok Profile

**Files:**
- Modify: `backend/tests/test_sequence_registry.py`
- Modify: `backend/app/services/prompt_factory_service.py`

- [ ] **Step 1: Write the failing runtime-default tests**

Extend `backend/tests/test_sequence_registry.py` with:

```python
@pytest.mark.asyncio
async def test_generate_prompt_batch_uses_adult_prompt_facing_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(
        settings,
        "HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE",
        "adult_openrouter_grok",
    )
    monkeypatch.setattr(
        settings,
        "HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL",
        "x-ai/grok-4.1-fast",
    )

    request = PromptBatchGenerateRequest(
        concept_brief="adult pilot concept",
        count=1,
        chunk_size=1,
        content_mode="adult_nsfw",
        provider="default",
        direction_pass_enabled=False,
        dedupe=False,
    )

    runtime = prompt_factory_service._resolve_prompt_provider_profile_runtime_options(request)
    assert runtime == {"structured_json": True, "strict_json": False}
```

Also update the existing `test_prompt_factory_capabilities_follow_profile_default_resolution` to keep asserting:

```python
assert settings.HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE == "adult_local_llm"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q -k "adult_prompt_facing_default or capabilities_follow_profile_default_resolution"
```

Expected: FAIL because Prompt Factory still reads `HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE`.

- [ ] **Step 3: Implement the prompt-facing default split**

Update `backend/app/services/prompt_factory_service.py` so that:

- `_default_prompt_provider_profile_id("adult_nsfw")` returns `settings.HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE`
- `_provider_config_from_profile()` uses `settings.HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL` when `profile_id == "adult_openrouter_grok"`
- safe lane resolution stays on `HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE`
- sequence runtime code is untouched

Minimal shape:

```python
def _default_prompt_provider_profile_id(content_mode: str | None = None) -> str | None:
    if content_mode == "adult_nsfw":
        return settings.HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE
    if content_mode == "all_ages":
        return settings.HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE
    return None
```

- [ ] **Step 4: Run the focused backend tests**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q
```

Expected: PASS. Adult Prompt Factory defaults should resolve to `adult_openrouter_grok`, while sequence-default assertions remain local-LLM based.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/prompt_factory_service.py backend/tests/test_sequence_registry.py
git commit -m "feat(hollowforge): split adult prompt factory defaults"
```

## Task 3: Align Story Planner Adult Policy Metadata Without Changing Route Contracts

**Files:**
- Modify: `backend/tests/test_story_planner_catalog.py`
- Modify: `backend/tests/test_story_planner_routes.py`
- Modify: `backend/app/story_planner_assets/policy_packs.json`

- [ ] **Step 1: Write the failing metadata tests**

Add a focused catalog assertion in `backend/tests/test_story_planner_catalog.py`:

```python
def test_adult_policy_pack_points_to_adult_grok_profile():
    catalog = load_story_planner_catalog()
    adult_pack = next(pack for pack in catalog.policy_packs if pack.id == "canon_adult_nsfw_v1")

    assert adult_pack.prompt_provider_profile_id == "adult_openrouter_grok"
```

Add a route regression in `backend/tests/test_story_planner_routes.py`:

```python
assert body["policy_pack_id"] == "canon_adult_nsfw_v1"
assert body["anchor_render"]["policy_pack_id"] == "canon_adult_nsfw_v1"
```

Keep the existing anchor-render assertions intact so the test proves metadata moved but the preview contract did not.

- [ ] **Step 2: Run the Story Planner tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_story_planner_catalog.py tests/test_story_planner_routes.py -q
```

Expected: FAIL because `canon_adult_nsfw_v1` still points to `adult_local_llm_strict_json`.

- [ ] **Step 3: Update the adult policy pack metadata**

Change `backend/app/story_planner_assets/policy_packs.json`:

```json
{
  "id": "canon_adult_nsfw_v1",
  "lane": "adult_nsfw",
  "prompt_provider_profile_id": "adult_openrouter_grok"
}
```

Do not change:

- `policy_pack_id`
- `negative_prompt_mode`
- `forbidden_defaults`
- `planner_rules`
- render checkpoint defaults

- [ ] **Step 4: Run the Story Planner tests again**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_story_planner_catalog.py tests/test_story_planner_routes.py -q
```

Expected: PASS. Adult policy metadata should point to the new profile id while the preview/anchor contract stays stable.

- [ ] **Step 5: Commit**

```bash
git add backend/app/story_planner_assets/policy_packs.json backend/tests/test_story_planner_catalog.py backend/tests/test_story_planner_routes.py
git commit -m "feat(hollowforge): align adult story planner metadata"
```

## Task 4: Document the Env Split and Run Final Verification

**Files:**
- Modify: `docs/GROK_PROMPT_FACTORY_20260311.md`
- Verify: `backend/app/services/sequence_run_service.py`
- Verify: `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md`

- [ ] **Step 1: Add the operator note**

Update `docs/GROK_PROMPT_FACTORY_20260311.md` with a short section covering:

- `HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE`
- `HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL`
- Prompt Factory adult defaults now use OpenRouter/Grok
- sequence runtime adult defaults remain `adult_local_llm`

Suggested note:

```md
## Adult Lane Default Split

Prompt Factory adult defaults now resolve through `adult_openrouter_grok`.
This does not change `HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE`, which remains the sequence runtime default.
```

- [ ] **Step 2: Run the full targeted verification sweep**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py tests/test_story_planner_catalog.py tests/test_story_planner_routes.py -q
```

Expected: PASS

- [ ] **Step 3: Verify sequence defaults were not widened**

Run:

```bash
cd backend && rg -n "HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE|adult_local_llm" app/services/sequence_run_service.py
cd .. && rg -n "Expected Stage 1 default: `adult_local_llm`" docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md
```

Expected: The runtime code and runbook still point to `adult_local_llm` for sequence-stage adult defaults.

- [ ] **Step 4: Optional local smoke check if backend is already running**

Run:

```bash
curl -s http://127.0.0.1:8000/api/v1/tools/prompt-factory/capabilities | jq '.content_mode_defaults[] | select(.content_mode=="adult_nsfw")'
curl -s -X POST http://127.0.0.1:8000/api/v1/tools/story-planner/plan -H 'Content-Type: application/json' -d '{"story_prompt":"Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing.","lane":"adult_nsfw"}' | jq '{policy_pack_id, anchor_render: .anchor_render.policy_pack_id, resolved_cast}'
```

Expected: capabilities report `adult_openrouter_grok`; Story Planner still returns `policy_pack_id: "canon_adult_nsfw_v1"` and a stable anchor payload.

- [ ] **Step 5: Commit**

```bash
git add docs/GROK_PROMPT_FACTORY_20260311.md
git commit -m "docs(hollowforge): document adult grok default split"
```

