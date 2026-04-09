"""Deterministic Story Planner to comic draft bridge."""

from __future__ import annotations

import json

from app.models import (
    ComicEpisodeDraft,
    ComicEpisodeSceneDraft,
    ComicScenePanelDraft,
    StoryPlannerPlanResponse,
    StoryPlannerShotCard,
)
from app.services.story_planner_service import _validate_story_planner_approval_token


def _scene_involved_character_ids(
    approved_plan: StoryPlannerPlanResponse,
) -> list[str]:
    involved_character_ids: list[str] = []
    for member in approved_plan.resolved_cast:
        character_id = (member.character_id or "").strip()
        if not character_id.startswith("char_"):
            continue
        if character_id in involved_character_ids:
            continue
        involved_character_ids.append(character_id)
    return involved_character_ids


def _scene_continuity_notes(
    approved_plan: StoryPlannerPlanResponse,
    shot: StoryPlannerShotCard,
) -> str:
    return (
        f"{shot.continuity_note} "
        f"Preserve location anchor: {approved_plan.location.setting_anchor}"
    )


def _panel_type_for(
    *,
    panel_no: int,
    panel_multiplier: int,
) -> str:
    if panel_no == 1:
        return "establish"
    if panel_no == panel_multiplier:
        return "closeup"
    return "beat"


def _panel_camera_intent(
    *,
    shot: StoryPlannerShotCard,
    panel_no: int,
    panel_multiplier: int,
) -> str:
    if panel_no == 1:
        return shot.camera
    if panel_no == panel_multiplier:
        return f"{shot.camera} Tighten the focus on the emotional turn."
    return f"{shot.camera} Hold the transition beat."


def _panel_action_intent(
    *,
    shot: StoryPlannerShotCard,
    panel_no: int,
    panel_multiplier: int,
) -> str:
    if panel_no == 1:
        return shot.action
    if panel_no == panel_multiplier:
        return f"{shot.action} Land the scene on the clearest reaction."
    return f"{shot.action} Bridge toward the reveal."


def _panel_expression_intent(
    *,
    shot: StoryPlannerShotCard,
    panel_no: int,
    panel_multiplier: int,
) -> str:
    if panel_no == 1:
        return shot.emotion
    if panel_no == panel_multiplier:
        return f"{shot.emotion} with the reaction pushed closer to the foreground"
    return f"{shot.emotion} while the tension continues to build"


def _panel_dialogue_intent(
    *,
    shot: StoryPlannerShotCard,
    scene_no: int,
    panel_no: int,
) -> str:
    return (
        "Placeholder dialogue intent only. "
        f"Scene {scene_no}, panel {panel_no} should support '{shot.beat}' "
        f"while carrying '{shot.emotion}'."
    )


def build_comic_draft_from_story_plan(
    *,
    approved_plan: StoryPlannerPlanResponse,
    character_version_id: str,
    title: str,
    panel_multiplier: int = 2,
    render_lane: str = "legacy",
    series_style_id: str | None = None,
    character_series_binding_id: str | None = None,
) -> ComicEpisodeDraft:
    _validate_story_planner_approval_token(approved_plan)

    involved_character_ids = _scene_involved_character_ids(approved_plan)
    scenes: list[ComicEpisodeSceneDraft] = []
    panels: list[ComicScenePanelDraft] = []

    for shot in approved_plan.shots:
        scenes.append(
            ComicEpisodeSceneDraft(
                scene_no=shot.shot_no,
                premise=shot.beat,
                location_label=approved_plan.location.name,
                tension=shot.emotion,
                reveal=shot.action,
                continuity_notes=_scene_continuity_notes(approved_plan, shot),
                involved_character_ids=involved_character_ids,
                target_panel_count=panel_multiplier,
            )
        )

        for panel_no in range(1, panel_multiplier + 1):
            panels.append(
                ComicScenePanelDraft(
                    scene_no=shot.shot_no,
                    panel_no=panel_no,
                    panel_type=_panel_type_for(
                        panel_no=panel_no,
                        panel_multiplier=panel_multiplier,
                    ),
                    framing=f"Scene {shot.shot_no} panel {panel_no}",
                    camera_intent=_panel_camera_intent(
                        shot=shot,
                        panel_no=panel_no,
                        panel_multiplier=panel_multiplier,
                    ),
                    action_intent=_panel_action_intent(
                        shot=shot,
                        panel_no=panel_no,
                        panel_multiplier=panel_multiplier,
                    ),
                    expression_intent=_panel_expression_intent(
                        shot=shot,
                        panel_no=panel_no,
                        panel_multiplier=panel_multiplier,
                    ),
                    dialogue_intent=_panel_dialogue_intent(
                        shot=shot,
                        scene_no=shot.shot_no,
                        panel_no=panel_no,
                    ),
                    continuity_lock=shot.continuity_note,
                    reading_order=panel_no,
                )
            )

    continuity_summary = "\n".join(approved_plan.episode_brief.continuity_guidance)

    return ComicEpisodeDraft(
        character_version_id=character_version_id,
        title=title,
        synopsis=approved_plan.episode_brief.premise,
        source_story_plan_json=json.dumps(
            approved_plan.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
        ),
        continuity_summary=continuity_summary or None,
        render_lane=render_lane,
        series_style_id=series_style_id,
        character_series_binding_id=character_series_binding_id,
        scenes=scenes,
        panels=panels,
    )
