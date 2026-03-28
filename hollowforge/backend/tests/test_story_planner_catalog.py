from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    StoryPlannerCastInput,
    StoryPlannerCharacterCatalogEntry,
    StoryPlannerLocationCatalogEntry,
    StoryPlannerPlanRequest,
    StoryPlannerPolicyPackCatalogEntry,
)
from app.services.story_planner_catalog import load_story_planner_catalog


SHARED_HARD_FORBIDDEN_BASELINE = {
    "minors",
    "age ambiguity",
    "non-consensual framing",
}


def test_load_story_planner_catalog_returns_spec_aligned_entries():
    catalog = load_story_planner_catalog()

    assert {pack.lane for pack in catalog.policy_packs} == {
        "unrestricted",
        "all_ages",
        "adult_nsfw",
    }

    character_keys = {
        "id",
        "name",
        "canonical_anchor",
        "anti_drift",
        "wardrobe_notes",
        "personality_notes",
        "preferred_checkpoints",
    }
    location_keys = {
        "id",
        "name",
        "setting_anchor",
        "visual_rules",
        "restricted_elements",
    }
    policy_pack_keys = {
        "id",
        "lane",
        "prompt_provider_profile_id",
        "negative_prompt_mode",
        "forbidden_defaults",
        "planner_rules",
        "render_preferences",
    }

    assert catalog.characters
    assert catalog.locations
    assert catalog.policy_packs
    assert all(set(character.model_dump().keys()) == character_keys for character in catalog.characters)
    assert all(set(location.model_dump().keys()) == location_keys for location in catalog.locations)
    assert all(set(pack.model_dump().keys()) == policy_pack_keys for pack in catalog.policy_packs)
    assert all(character.preferred_checkpoints for character in catalog.characters)
    assert all(location.visual_rules for location in catalog.locations)
    assert all(pack.planner_rules for pack in catalog.policy_packs)
    assert all(
        SHARED_HARD_FORBIDDEN_BASELINE.issubset(set(pack.forbidden_defaults))
        for pack in catalog.policy_packs
    )


def test_story_planner_plan_request_accepts_registry_and_freeform_cast_with_supported_roles():
    payload = StoryPlannerPlanRequest(
        story_prompt="Hana Seo pauses in a spa corridor after reading a cryptic message.",
        lane="unrestricted",
        cast=[
            StoryPlannerCastInput(
                role="lead",
                source_type="registry",
                character_id="hana_seo",
            ),
            StoryPlannerCastInput(
                role="support",
                source_type="freeform",
                freeform_description="anonymous messenger",
            ),
        ],
    )

    assert payload.cast[0].role == "lead"
    assert payload.cast[0].character_id == "hana_seo"
    assert payload.cast[1].role == "support"
    assert payload.cast[1].freeform_description == "anonymous messenger"


@pytest.mark.parametrize(
    ("model_cls", "payload", "missing_field"),
    [
        (
            StoryPlannerCharacterCatalogEntry,
            {
                "id": "hana_seo",
                "name": "Hana Seo",
                "canonical_anchor": "anchor",
                "anti_drift": "drift guard",
                "wardrobe_notes": "wardrobe",
                "personality_notes": "personality",
            },
            "preferred_checkpoints",
        ),
        (
            StoryPlannerLocationCatalogEntry,
            {
                "id": "moonlit_bathhouse",
                "name": "Moonlit Bathhouse",
                "setting_anchor": "premium bathhouse",
            },
            "visual_rules",
        ),
        (
            StoryPlannerPolicyPackCatalogEntry,
            {
                "id": "canon_unrestricted_v1",
                "lane": "unrestricted",
                "prompt_provider_profile_id": "adult_local_llm",
                "negative_prompt_mode": "blank",
            },
            "forbidden_defaults",
        ),
    ],
)
def test_catalog_entry_models_reject_omitted_required_fields(
    model_cls: type,
    payload: dict[str, object],
    missing_field: str,
):
    with pytest.raises(ValidationError, match=missing_field):
        model_cls(**payload)


@pytest.mark.parametrize(
    ("payload", "error_fragment"),
    [
        (
            {
                "role": "lead",
                "source_type": "registry",
                "freeform_description": "should not be allowed",
            },
            "character_id is required",
        ),
        (
            {
                "role": "support",
                "source_type": "freeform",
                "character_id": "hana_seo",
            },
            "freeform_description is required",
        ),
        (
            {
                "role": "support",
                "source_type": "registry",
                "character_id": "hana_seo",
                "freeform_description": "extra",
            },
            "freeform_description is not allowed",
        ),
        (
            {
                "role": "villain",
                "source_type": "freeform",
                "freeform_description": "impostor",
            },
            "lead",
        ),
        (
            {
                "role": "lead",
                "source_type": "registry",
                "character_id": "hana_seo",
                "unexpected": "extra",
            },
            "unexpected",
        ),
    ],
)
def test_story_planner_cast_input_rejects_out_of_contract_payloads(
    payload: dict[str, str],
    error_fragment: str,
):
    with pytest.raises(ValidationError, match=error_fragment):
        StoryPlannerCastInput(**payload)


def test_story_planner_plan_request_rejects_extra_top_level_fields():
    with pytest.raises(ValidationError, match="unexpected"):
        StoryPlannerPlanRequest(
            story_prompt="A tense meeting unfolds at the bathhouse reception desk.",
            lane="all_ages",
            unexpected="extra",
        )


def test_story_planner_plan_request_rejects_more_than_two_cast_members():
    with pytest.raises(ValidationError, match="at most 2 items"):
        StoryPlannerPlanRequest(
            story_prompt="A tense meeting unfolds at the bathhouse reception desk.",
            lane="all_ages",
            cast=[
                StoryPlannerCastInput(
                    role="lead",
                    source_type="registry",
                    character_id="hana_seo",
                ),
                StoryPlannerCastInput(
                    role="support",
                    source_type="registry",
                    character_id="mina_park",
                ),
                StoryPlannerCastInput(
                    role="support",
                    source_type="freeform",
                    freeform_description="anonymous observer",
                ),
            ],
        )


def test_story_planner_plan_request_rejects_duplicate_cast_roles():
    with pytest.raises(ValidationError, match="duplicate cast roles"):
        StoryPlannerPlanRequest(
            story_prompt="A tense meeting unfolds at the bathhouse reception desk.",
            lane="all_ages",
            cast=[
                StoryPlannerCastInput(
                    role="support",
                    source_type="registry",
                    character_id="hana_seo",
                ),
                StoryPlannerCastInput(
                    role="support",
                    source_type="freeform",
                    freeform_description="anonymous observer",
                ),
            ],
        )


def test_story_planner_plan_request_defaults_to_empty_cast():
    payload = StoryPlannerPlanRequest(
        story_prompt="A tense meeting unfolds at the bathhouse reception desk.",
        lane="all_ages",
    )

    assert payload.cast == []
