from __future__ import annotations

from app.models import StoryPlannerCastInput, StoryPlannerPlanRequest
from app.services.story_planner_service import plan_story_episode


def _build_request(
    *,
    story_prompt: str,
    lane: str = "adult_nsfw",
) -> StoryPlannerPlanRequest:
    return StoryPlannerPlanRequest(
        story_prompt=story_prompt,
        lane=lane,
        cast=[
            StoryPlannerCastInput(
                role="lead",
                source_type="registry",
                character_id="hana_seo",
            ),
            StoryPlannerCastInput(
                role="support",
                source_type="freeform",
                freeform_description="quiet messenger in a dark coat",
            ),
        ],
    )


def test_plan_story_episode_builds_episode_brief_and_four_shot_plan() -> None:
    preview = plan_story_episode(
        _build_request(
            story_prompt=(
                "Hana Seo meets a quiet messenger in the Moonlit Bathhouse "
                "corridor after closing."
            )
        )
    )

    assert preview.policy_pack_id == "canon_adult_nsfw_v1"
    assert preview.location.match_note
    assert preview.episode_brief.premise
    assert preview.episode_brief.continuity_guidance
    assert len(preview.shots) == 4
    assert [shot.shot_no for shot in preview.shots] == [1, 2, 3, 4]
    assert all(shot.beat for shot in preview.shots)
    assert all(shot.camera for shot in preview.shots)
    assert all(shot.action for shot in preview.shots)
    assert all(shot.emotion for shot in preview.shots)
    assert all(shot.continuity_note for shot in preview.shots)


def test_plan_story_episode_resolves_registry_cast_and_preserves_freeform_support() -> None:
    preview = plan_story_episode(
        _build_request(
            story_prompt=(
                "Hana Seo and a quiet messenger compare notes by the service door."
            )
        )
    )

    lead = next(member for member in preview.resolved_cast if member.role == "lead")
    support = next(
        member for member in preview.resolved_cast if member.role == "support"
    )

    assert lead.source_type == "registry"
    assert lead.character_id == "hana_seo"
    assert lead.character_name == "Hana Seo"
    assert support.source_type == "freeform"
    assert support.character_id is None
    assert support.character_name is None
    assert support.freeform_description == "quiet messenger in a dark coat"


def test_plan_story_episode_keeps_unresolved_registry_cast_without_fake_display_name() -> None:
    preview = plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt="An unknown consultant arrives for a private meeting.",
            lane="adult_nsfw",
            cast=[
                StoryPlannerCastInput(
                    role="lead",
                    source_type="registry",
                    character_id="unknown_consultant",
                )
            ],
        )
    )

    lead = preview.resolved_cast[0]

    assert lead.source_type == "registry"
    assert lead.character_id == "unknown_consultant"
    assert lead.character_name is None
    assert "unknown_consultant" in lead.resolution_note
    assert "not found" in lead.resolution_note.lower()


def test_plan_story_episode_resolves_location_from_prompt_and_falls_back_when_needed() -> None:
    matched_preview = plan_story_episode(
        _build_request(
            story_prompt=(
                "The pair trade signals in the rooftop tea lounge above the bathhouse."
            )
        )
    )
    restricted_term_preview = plan_story_episode(
        _build_request(
            story_prompt="A plain studio room with no dance floor staging anywhere.",
        )
    )
    fallback_preview = plan_story_episode(
        _build_request(
            story_prompt="A plain studio room with no clear setting cues.",
        )
    )

    assert matched_preview.location.id == "rooftop_tea_lounge"
    assert "matched" in matched_preview.location.match_note.lower()
    assert restricted_term_preview.location.id == "moonlit_bathhouse"
    assert "fallback" in restricted_term_preview.location.match_note.lower()
    assert fallback_preview.location.id == "moonlit_bathhouse"
    assert fallback_preview.location.match_note
    assert "fallback" in fallback_preview.location.match_note.lower()
