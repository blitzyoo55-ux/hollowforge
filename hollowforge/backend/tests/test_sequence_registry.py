from __future__ import annotations

import json
import sys
import types

from fastapi import HTTPException
import pytest

from app.config import settings
from app.models import PromptBatchGenerateRequest, PromptFactoryBenchmarkResponse
from app.services import prompt_factory_service
from app.services.sequence_registry import get_beat_grammar, get_prompt_provider_profile


def test_stage1_beat_grammar_has_expected_order() -> None:
    grammar = get_beat_grammar("stage1_single_location_v1")
    assert grammar["beats"] == [
        "establish",
        "attention",
        "approach",
        "contact_action",
        "close_reaction",
        "settle",
    ]


def test_adult_stage1_beat_grammar_is_registered_for_adult_lane() -> None:
    grammar = get_beat_grammar("adult_stage1_v1", content_mode="adult_nsfw")

    assert grammar["content_mode"] == "adult_nsfw"
    assert grammar["beats"] == [
        "establish",
        "attention",
        "approach",
        "contact_action",
        "close_reaction",
        "settle",
    ]


def test_adult_prompt_profile_defaults_to_local() -> None:
    profile = get_prompt_provider_profile("adult_local_llm")
    assert profile["provider_kind"] == "local_llm"


def test_adult_openrouter_grok_profile_is_registered() -> None:
    profile = get_prompt_provider_profile("adult_openrouter_grok", content_mode="adult_nsfw")
    assert profile["provider_kind"] == "openrouter"
    assert profile["structured_json"] is True
    assert profile["strict_json"] is False


def test_registry_lookups_return_independent_copies() -> None:
    first = get_beat_grammar("stage1_single_location_v1")
    first["beats"].append("mutated")

    second = get_beat_grammar("stage1_single_location_v1")

    assert second["beats"] == [
        "establish",
        "attention",
        "approach",
        "contact_action",
        "close_reaction",
        "settle",
    ]


@pytest.mark.asyncio
async def test_generate_prompt_batch_uses_prompt_profile_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_LOCAL_LLM_BASE_URL", "http://local-llm.test/v1")
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_LOCAL_LLM_MODEL", "local-test-model")
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
    monkeypatch.setattr(prompt_factory_service, "load_prompt_benchmark_snapshot", _fake_load_prompt_benchmark_snapshot)

    request = PromptBatchGenerateRequest(
        concept_brief="test concept",
        count=1,
        chunk_size=1,
        content_mode="adult_nsfw",
        prompt_provider_profile_id="adult_local_llm",
        workflow_lane="auto",
        provider="default",
        direction_pass_enabled=False,
        dedupe=False,
    )

    response = await prompt_factory_service.generate_prompt_batch(request)

    assert recorder["base_url"] == "http://local-llm.test/v1"
    assert recorder["api_key"] == "local_llm"
    assert "response_format" not in recorder["create_kwargs"]
    assert response.provider == "local_llm"
    assert response.model == "local-test-model"


@pytest.mark.asyncio
async def test_generate_prompt_batch_uses_strict_json_profile_response_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_LOCAL_LLM_BASE_URL", "http://local-llm.test/v1")
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_LOCAL_LLM_MODEL", "local-test-model")
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
    monkeypatch.setattr(prompt_factory_service, "load_prompt_benchmark_snapshot", _fake_load_prompt_benchmark_snapshot)

    request = PromptBatchGenerateRequest(
        concept_brief="test concept",
        count=1,
        chunk_size=1,
        content_mode="adult_nsfw",
        prompt_provider_profile_id="adult_local_llm_strict_json",
        workflow_lane="auto",
        provider="default",
        direction_pass_enabled=False,
        dedupe=False,
    )

    response = await prompt_factory_service.generate_prompt_batch(request)

    assert recorder["base_url"] == "http://local-llm.test/v1"
    assert recorder["api_key"] == "local_llm"
    assert recorder["create_kwargs"]["response_format"] == {"type": "json_object"}
    assert response.provider == "local_llm"
    assert response.model == "local-test-model"


def test_resolve_provider_config_rejects_profile_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "legacy-key")
    monkeypatch.setattr(settings, "XAI_API_KEY", "")
    monkeypatch.setattr(settings, "PROMPT_FACTORY_PROVIDER", "openrouter")

    request = PromptBatchGenerateRequest(
        concept_brief="test concept",
        provider="default",
        content_mode="all_ages",
        prompt_provider_profile_id="adult_local_llm",
    )

    with pytest.raises(HTTPException) as exc_info:
        prompt_factory_service._resolve_provider_config(request)  # noqa: SLF001

    assert exc_info.value.status_code == 400
    assert "adult_local_llm" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_generate_prompt_batch_rejects_ambiguous_no_mode_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "XAI_API_KEY", "")
    monkeypatch.setattr(settings, "PROMPT_FACTORY_PROVIDER", "openrouter")

    request = PromptBatchGenerateRequest(
        concept_brief="test concept",
        provider="default",
    )

    with pytest.raises(HTTPException) as exc_info:
        await prompt_factory_service.generate_prompt_batch(request)

    assert exc_info.value.status_code == 400
    assert "content_mode or prompt_provider_profile_id" in str(exc_info.value.detail)


def test_prompt_factory_capabilities_follow_profile_default_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "XAI_API_KEY", "xai-key")
    monkeypatch.setattr(settings, "PROMPT_FACTORY_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE", "safe_hosted_grok")
    monkeypatch.setattr(settings, "HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE", "adult_local_llm")
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE", "adult_local_llm")
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_LOCAL_LLM_BASE_URL", "http://local-llm.test/v1")
    monkeypatch.setattr(settings, "HOLLOWFORGE_SEQUENCE_LOCAL_LLM_MODEL", "local-test-model")

    capabilities = prompt_factory_service.get_prompt_factory_capabilities()
    defaults_by_mode = {item.content_mode: item for item in capabilities.content_mode_defaults}

    assert capabilities.default_prompt_provider_profile_id is None
    assert capabilities.default_provider is None
    assert capabilities.default_model is None
    assert capabilities.ready is None
    assert defaults_by_mode["all_ages"].prompt_provider_profile_id == "safe_hosted_grok"
    assert defaults_by_mode["all_ages"].provider_kind == "xai"
    assert defaults_by_mode["all_ages"].ready is True
    assert defaults_by_mode["adult_nsfw"].prompt_provider_profile_id == "adult_local_llm"
    assert defaults_by_mode["adult_nsfw"].provider_kind == "local_llm"
    assert defaults_by_mode["adult_nsfw"].model == "local-test-model"
    assert defaults_by_mode["adult_nsfw"].ready is True


def test_prompt_factory_capabilities_use_prompt_facing_adult_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setenv("XAI_API_KEY", "xai-key")
    monkeypatch.setenv("PROMPT_FACTORY_OPENROUTER_MODEL", "openrouter-generic-model")
    monkeypatch.setenv("HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE", "adult_openrouter_grok")
    monkeypatch.setenv("HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL", "x-ai/grok-4.1-fast")
    monkeypatch.setenv("HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE", "adult_local_llm")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(settings, "XAI_API_KEY", "xai-key")
    monkeypatch.setattr(settings, "PROMPT_FACTORY_OPENROUTER_MODEL", "openrouter-generic-model")
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
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("PROMPT_FACTORY_OPENROUTER_MODEL", "openrouter-generic-model")
    monkeypatch.setenv("HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE", "adult_openrouter_grok")
    monkeypatch.setenv("HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL", "x-ai/grok-4.1-fast")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "PROMPT_FACTORY_OPENROUTER_MODEL", "openrouter-generic-model")
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
    assert defaults_by_mode["adult_nsfw"].ready is False


@pytest.mark.asyncio
async def test_generate_prompt_batch_uses_adult_prompt_facing_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setenv("PROMPT_FACTORY_OPENROUTER_MODEL", "openrouter-generic-model")
    monkeypatch.setenv("HOLLOWFORGE_PROMPT_FACTORY_DEFAULT_ADULT_PROMPT_PROFILE", "adult_openrouter_grok")
    monkeypatch.setenv("HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL", "x-ai/grok-4.1-fast")
    monkeypatch.setenv("PROMPT_FACTORY_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(settings, "PROMPT_FACTORY_OPENROUTER_MODEL", "openrouter-generic-model")
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
    monkeypatch.setattr(prompt_factory_service, "load_prompt_benchmark_snapshot", _fake_load_prompt_benchmark_snapshot)

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


@pytest.mark.asyncio
async def test_generate_prompt_batch_uses_explicit_adult_openrouter_grok_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setenv("PROMPT_FACTORY_OPENROUTER_MODEL", "openrouter-generic-model")
    monkeypatch.setenv("HOLLOWFORGE_PROMPT_FACTORY_ADULT_OPENROUTER_MODEL", "x-ai/grok-4.1-fast")
    monkeypatch.setenv("PROMPT_FACTORY_PROVIDER", "openrouter")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(settings, "PROMPT_FACTORY_OPENROUTER_MODEL", "openrouter-generic-model")
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
    monkeypatch.setattr(prompt_factory_service, "load_prompt_benchmark_snapshot", _fake_load_prompt_benchmark_snapshot)

    request = PromptBatchGenerateRequest(
        concept_brief="adult pilot concept",
        workflow_lane="auto",
        count=1,
        chunk_size=1,
        content_mode="adult_nsfw",
        prompt_provider_profile_id="adult_openrouter_grok",
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


@pytest.mark.asyncio
async def test_default_provider_requires_content_mode_or_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "XAI_API_KEY", "xai-key")
    monkeypatch.setattr(settings, "PROMPT_FACTORY_PROVIDER", "openrouter")

    request = PromptBatchGenerateRequest(
        concept_brief="test concept",
        provider="default",
        count=1,
        chunk_size=1,
        direction_pass_enabled=False,
        dedupe=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await prompt_factory_service.generate_prompt_batch(request)

    assert exc_info.value.status_code == 400
    assert "content_mode or prompt_provider_profile_id" in str(exc_info.value.detail)
