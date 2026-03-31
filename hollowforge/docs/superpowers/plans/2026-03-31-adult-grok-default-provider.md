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
- Modify: `backend/tests/test_marketing_routes.py`
- Modify: `backend/tests/test_sequence_run_service.py`

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q -k adult_openrouter_grok_profile_is_registered
```

Expected: FAIL because the adult Grok profile does not exist yet.

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
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q -k adult_openrouter_grok_profile_is_registered
```

Expected: PASS for the new registry assertion.

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
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE", "adult_local_llm")

    capabilities = prompt_factory_service.get_prompt_factory_capabilities()
    defaults_by_mode = {item.content_mode: item for item in capabilities.content_mode_defaults}

    assert defaults_by_mode["adult_nsfw"].prompt_provider_profile_id == "adult_openrouter_grok"
    assert defaults_by_mode["adult_nsfw"].provider_kind == "openrouter"
    assert defaults_by_mode["adult_nsfw"].model == "x-ai/grok-4.1-fast"
    assert defaults_by_mode["adult_nsfw"].ready is True
    assert settings.HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE == "adult_local_llm"


def test_prompt_factory_capabilities_report_adult_default_not_ready_without_openrouter_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
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
    assert defaults_by_mode["adult_nsfw"].ready is False


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
    monkeypatch.setattr(settings, "PROMPT_FACTORY_PROVIDER", "openrouter")

    benchmark = PromptFactoryBenchmarkResponse(
        favorites_total=0,
        workflow_lane="sdxl_illustrious",
        prompt_dialect="natural_language",
        top_checkpoints=["checkpoint-a"],
        top_loras=["lora-a"],
        avg_lora_strength=0.5,
        cfg_values=[5.0],
        steps_values=[30],
        sampler="euler",
        scheduler="normal",
        clip_skip=2,
        width=832,
        height=1216,
        theme_keywords=["theme"],
        material_cues=["material"],
        control_cues=["control"],
        camera_cues=["camera"],
        environment_cues=["environment"],
        exposure_cues=["exposure"],
        negative_prompt="negative",
    )

    async def _fake_load_prompt_benchmark_snapshot(requested_lane: str = "auto") -> PromptFactoryBenchmarkResponse:
        return benchmark

    class _FakeCompletion:
        def __init__(self) -> None:
            self.choices = [
                types.SimpleNamespace(
                    message=types.SimpleNamespace(
                        content=json.dumps(
                            {
                                "rows": [
                                    {
                                        "codename": "shot-a",
                                        "series": "series-a",
                                        "checkpoint": "checkpoint-a",
                                        "loras": [],
                                        "sampler": "euler",
                                        "steps": 30,
                                        "cfg": 5.0,
                                        "clip_skip": 2,
                                        "width": 832,
                                        "height": 1216,
                                        "positive_prompt": "prompt-a",
                                        "negative_prompt": "negative-a",
                                    }
                                ]
                            }
                        )
                    )
                )
            ]

    class _FakeCompletions:
        def __init__(self, recorder: dict[str, object]) -> None:
            self._recorder = recorder

        async def create(self, **kwargs: object) -> _FakeCompletion:
            self._recorder["create_kwargs"] = kwargs
            return _FakeCompletion()

    class _FakeChat:
        def __init__(self, recorder: dict[str, object]) -> None:
            self.completions = _FakeCompletions(recorder)

    class _FakeAsyncOpenAI:
        def __init__(self, *, base_url: str, api_key: str) -> None:
            recorder["base_url"] = base_url
            recorder["api_key"] = api_key
            self.chat = _FakeChat(recorder)

    recorder: dict[str, object] = {}
    fake_openai = types.SimpleNamespace(AsyncOpenAI=_FakeAsyncOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setattr(
        prompt_factory_service,
        "load_prompt_benchmark_snapshot",
        _fake_load_prompt_benchmark_snapshot,
    )

    request = PromptBatchGenerateRequest(
        concept_brief="adult pilot concept",
        workflow_lane="auto",
        count=1,
        chunk_size=1,
        content_mode="adult_nsfw",
        provider="default",
        direction_pass_enabled=False,
        dedupe=False,
    )

    response = await prompt_factory_service.generate_prompt_batch(request)

    assert recorder["base_url"] == "https://openrouter.ai/api/v1"
    assert recorder["api_key"] == "openrouter-key"
    assert "response_format" not in recorder["create_kwargs"]
    assert response.provider == "openrouter"
    assert response.model == "x-ai/grok-4.1-fast"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py -q -k "prompt_facing_adult_default or adult_default_not_ready_without_openrouter_key"
```

Expected: FAIL because Prompt Factory still reads `HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE` and does not pin the adult Grok model.

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
- Modify: `backend/tests/test_marketing_routes.py`
- Modify: `backend/app/story_planner_assets/policy_packs.json`

- [ ] **Step 1: Write the failing metadata tests**

Add a focused catalog assertion in `backend/tests/test_story_planner_catalog.py`:

```python
def test_adult_policy_pack_points_to_adult_grok_profile():
    catalog = load_story_planner_catalog()
    adult_pack = next(pack for pack in catalog.policy_packs if pack.id == "canon_adult_nsfw_v1")

    assert adult_pack.prompt_provider_profile_id == "adult_openrouter_grok"
    profile = get_prompt_provider_profile(
        adult_pack.prompt_provider_profile_id,
        content_mode="adult_nsfw",
    )
    assert profile["provider_kind"] == "openrouter"
```

Add a catalog-route regression in `backend/tests/test_story_planner_routes.py`:

```python
adult_pack = next(pack for pack in body["policy_packs"] if pack["id"] == "canon_adult_nsfw_v1")
assert adult_pack["prompt_provider_profile_id"] == "adult_openrouter_grok"
```

Keep the existing plan-route anchor assertions intact so the test proves catalog metadata moved but the preview contract did not.

Add a handoff regression in `backend/tests/test_marketing_routes.py`:

```python
assert approved_plan["policy_pack_id"] == "canon_adult_nsfw_v1"
assert approved_plan["anchor_render"]["policy_pack_id"] == "canon_adult_nsfw_v1"
```

- [ ] **Step 2: Run the Story Planner tests to verify they fail**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_story_planner_catalog.py tests/test_story_planner_routes.py tests/test_marketing_routes.py -q -k story_planner
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
cd backend && ./.venv/bin/python -m pytest tests/test_story_planner_catalog.py tests/test_story_planner_routes.py tests/test_marketing_routes.py -q -k story_planner
```

Expected: PASS. Adult policy metadata should point to the new profile id while the preview/anchor contract stays stable.

- [ ] **Step 5: Commit**

```bash
git add backend/app/story_planner_assets/policy_packs.json backend/tests/test_story_planner_catalog.py backend/tests/test_story_planner_routes.py backend/tests/test_marketing_routes.py
git commit -m "feat(hollowforge): align adult story planner metadata"
```

## Task 4: Document the Env Split and Run Final Verification

**Files:**
- Modify: `backend/tests/test_sequence_run_service.py`
- Modify: `docs/GROK_PROMPT_FACTORY_20260311.md`
- Verify: `backend/app/services/sequence_run_service.py`
- Verify: `docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md`

- [ ] **Step 1: Add the sequence-runtime guardrail test**

Extend `backend/tests/test_sequence_run_service.py` with:

```python
def test_sequence_runtime_adult_default_remains_local_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sequence_run_service.settings,
        "HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE",
        "adult_local_llm",
    )
    monkeypatch.setattr(
        sequence_run_service.settings,
        "HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE",
        "adult_openrouter_grok",
    )

    assert sequence_run_service._default_prompt_provider_profile_id("adult_nsfw") == "adult_local_llm"
```

- [ ] **Step 2: Run the guardrail test**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_run_service.py -q -k sequence_runtime_adult_default_remains_local_llm
```

Expected: PASS. This is a non-regression guardrail for untouched runtime-selection code.

- [ ] **Step 3: Add the operator note**

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

- [ ] **Step 4: Run the full targeted verification sweep**

Run:

```bash
cd backend && ./.venv/bin/python -m pytest tests/test_sequence_registry.py tests/test_story_planner_catalog.py tests/test_story_planner_routes.py tests/test_marketing_routes.py tests/test_sequence_run_service.py -q -k "story_planner or prompt_factory or sequence_runtime_adult_default_remains_local_llm"
```

Expected: PASS

- [ ] **Step 5: Verify sequence defaults were not widened**

Run:

```bash
cd backend && rg -n "HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE|adult_local_llm" app/services/sequence_run_service.py
cd .. && rg -n 'Expected Stage 1 default: `adult_local_llm`' docs/HOLLOWFORGE_SEQUENCE_STAGE1_RUNBOOK_20260325.md
```

Expected: The runtime code and runbook still point to `adult_local_llm` for sequence-stage adult defaults.

- [ ] **Step 6: Optional local smoke check if backend is already running**

Run:

```bash
curl -s http://127.0.0.1:8000/api/v1/tools/prompt-factory/capabilities | jq '.content_mode_defaults[] | select(.content_mode=="adult_nsfw")'
curl -s -X POST http://127.0.0.1:8000/api/v1/tools/prompt-factory/generate -H 'Content-Type: application/json' -d '{"concept_brief":"adult pilot concept","count":1,"chunk_size":1,"content_mode":"adult_nsfw","provider":"default","direction_pass_enabled":false,"dedupe":false}' | jq '{provider, model, row_count:(.rows|length)}'
curl -s -X POST http://127.0.0.1:8000/api/v1/tools/story-planner/plan -H 'Content-Type: application/json' -d '{"story_prompt":"Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing.","lane":"adult_nsfw"}' | jq '{policy_pack_id, anchor_render: .anchor_render.policy_pack_id, resolved_cast}'
curl -s -X POST http://127.0.0.1:8000/api/v1/tools/story-planner/plan -H 'Content-Type: application/json' -d '{"story_prompt":"Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing.","lane":"adult_nsfw"}' > /tmp/hf-story-plan.json
jq '{approved_plan: ., candidate_count: 1}' /tmp/hf-story-plan.json | curl -s -X POST http://127.0.0.1:8000/api/v1/tools/story-planner/generate-anchors -H 'Content-Type: application/json' --data @- | jq '{lane, requested_shot_count, queued_generation_count}'
```

Expected: capabilities report `adult_openrouter_grok`; Prompt Factory generate resolves through OpenRouter/Grok; Story Planner still returns `policy_pack_id: "canon_adult_nsfw_v1"` with a stable anchor payload; `generate-anchors` returns the adult lane with queued shots.

- [ ] **Step 7: Commit**

```bash
git add backend/tests/test_sequence_run_service.py docs/GROK_PROMPT_FACTORY_20260311.md
git commit -m "docs(hollowforge): document adult grok default split"
```
