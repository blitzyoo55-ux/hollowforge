from __future__ import annotations

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


def test_adult_prompt_profile_defaults_to_local() -> None:
    profile = get_prompt_provider_profile("adult_local_llm")
    assert profile["provider_kind"] == "local_llm"
