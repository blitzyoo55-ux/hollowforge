"""Shot planning helpers for fixed HollowForge sequence blueprints."""

from __future__ import annotations

from typing import Any

from app.services.sequence_registry import get_beat_grammar

_STAGE1_CONTINUITY_LINES = (
    "Keep the same single character identity, wardrobe, hair, and silhouette.",
    "Keep the same fixed location, lighting family, and screen geography.",
    "Do not introduce dialogue, lip-sync, or additional characters.",
    "End each shot on a clean straight-cut transition point.",
)

_STAGE1_BEAT_RULES: dict[str, dict[str, str]] = {
    "establish": {
        "camera_intent": "wide_master",
        "emotion_intent": "grounded",
        "action_intent": "reveal_location",
        "continuity_line": "Open by clearly establishing the environment before motion escalates.",
    },
    "attention": {
        "camera_intent": "medium_observe",
        "emotion_intent": "alert",
        "action_intent": "notice_trigger",
        "continuity_line": "Preserve the established screen direction while attention shifts to the trigger.",
    },
    "approach": {
        "camera_intent": "medium_tracking",
        "emotion_intent": "intent",
        "action_intent": "close_distance",
        "continuity_line": "Carry forward the same motion vector and spatial orientation into the approach.",
    },
    "contact_action": {
        "camera_intent": "medium_close",
        "emotion_intent": "committed",
        "action_intent": "perform_key_action",
        "continuity_line": "Show the decisive action without changing costume, setting, or subject identity.",
    },
    "close_reaction": {
        "camera_intent": "close_reaction",
        "emotion_intent": "reactive",
        "action_intent": "register_impact",
        "continuity_line": "Hold on the immediate aftermath so the reaction reads as the result of the prior action.",
    },
    "settle": {
        "camera_intent": "wide_release",
        "emotion_intent": "resolved",
        "action_intent": "land_aftermath",
        "continuity_line": "Resolve to a stable resting frame that feels like a natural exit point.",
    },
}


def _allocate_target_durations(target_duration_sec: int, shot_count: int) -> list[int]:
    if shot_count < 1:
        raise ValueError("shot_count must be >= 1")
    if target_duration_sec < shot_count:
        raise ValueError("target_duration_sec must be >= shot_count")

    base_duration, remainder = divmod(target_duration_sec, shot_count)
    durations = [base_duration] * shot_count
    for index in range(remainder):
        durations[index] += 1
    return durations


def _build_continuity_rules(beat_type: str) -> str:
    beat_rules = _STAGE1_BEAT_RULES.get(beat_type)
    if beat_rules is None:
        raise ValueError(f"Unsupported Stage 1 beat type: {beat_type}")
    return "\n".join((*_STAGE1_CONTINUITY_LINES, beat_rules["continuity_line"]))


def expand_blueprint_into_shots(
    *,
    beat_grammar_id: str,
    target_duration_sec: int,
    shot_count: int | None = None,
) -> list[dict[str, Any]]:
    """Expand a fixed beat grammar into ordered Stage 1 shot plans."""
    grammar = get_beat_grammar(beat_grammar_id)
    beats = list(grammar["beats"])

    if shot_count is not None and shot_count != len(beats):
        raise ValueError(
            f"shot_count {shot_count} does not match beat grammar '{beat_grammar_id}' ({len(beats)})"
        )

    durations = _allocate_target_durations(target_duration_sec, len(beats))
    shots: list[dict[str, Any]] = []
    for index, beat_type in enumerate(beats):
        beat_rules = _STAGE1_BEAT_RULES.get(beat_type)
        if beat_rules is None:
            raise ValueError(f"Unsupported Stage 1 beat type: {beat_type}")
        shots.append(
            {
                "shot_no": index + 1,
                "beat_type": beat_type,
                "camera_intent": beat_rules["camera_intent"],
                "emotion_intent": beat_rules["emotion_intent"],
                "action_intent": beat_rules["action_intent"],
                "target_duration_sec": durations[index],
                "continuity_rules": _build_continuity_rules(beat_type),
            }
        )
    return shots
