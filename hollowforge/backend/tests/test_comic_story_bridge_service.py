from __future__ import annotations

from app.models import StoryPlannerCastInput, StoryPlannerPlanRequest
from app.services.comic_story_bridge_service import build_comic_draft_from_story_plan
from app.services.story_planner_service import plan_story_episode


def _build_registry_led_approved_plan():
    return plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt=(
                "Hana Seo compares notes with a quiet messenger in the "
                "Moonlit Bathhouse corridor after closing."
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
                    freeform_description="quiet messenger in a dark coat",
                ),
            ],
        )
    )


def test_story_plan_bridge_drops_non_core_planner_ids_from_scene_involvement() -> None:
    detail = build_comic_draft_from_story_plan(
        approved_plan=_build_registry_led_approved_plan(),
        character_version_id="charver_kaede_ren_still_v1",
        title="Night Intake",
        panel_multiplier=2,
    )

    assert detail.title == "Night Intake"
    assert detail.character_version_id == "charver_kaede_ren_still_v1"
    assert len(detail.scenes) == 4
    assert len(detail.panels) == 8
    assert detail.scenes[0].location_label == "Moonlit Bathhouse"
    assert detail.scenes[0].involved_character_ids == []
    assert detail.scenes[0].target_panel_count == 2
    assert detail.panels[0].reading_order == 1
    assert detail.panels[1].reading_order == 2
    assert detail.panels[0].dialogue_intent


def test_story_plan_bridge_preserves_explicit_v2_metadata() -> None:
    detail = build_comic_draft_from_story_plan(
        approved_plan=_build_registry_led_approved_plan(),
        character_version_id="charver_camila_duarte_still_v1",
        title="Camila Pilot Intake",
        panel_multiplier=2,
        render_lane="character_canon_v2",
        series_style_id="camila_pilot_v1",
        character_series_binding_id="camila_pilot_binding_v1",
    )

    assert detail.render_lane == "character_canon_v2"
    assert detail.series_style_id == "camila_pilot_v1"
    assert detail.character_series_binding_id == "camila_pilot_binding_v1"


def test_story_plan_bridge_maps_single_panel_per_shot_to_canonical_role_sequence() -> None:
    detail = build_comic_draft_from_story_plan(
        approved_plan=_build_registry_led_approved_plan(),
        character_version_id="charver_camila_duarte_still_v1",
        title="Camila V2 Four Shot Acceptance",
        panel_multiplier=1,
        render_lane="character_canon_v2",
        series_style_id="camila_pilot_v1",
        character_series_binding_id="camila_pilot_binding_v1",
    )

    assert [panel.panel_type for panel in detail.panels] == [
        "establish",
        "beat",
        "insert",
        "closeup",
    ]
    assert [panel.reading_order for panel in detail.panels] == [1, 2, 3, 4]
