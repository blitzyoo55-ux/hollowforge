from __future__ import annotations

import pytest


def test_expand_blueprint_emits_stage1_shots_in_order() -> None:
    from app.services.sequence_blueprint_service import expand_blueprint_into_shots

    shots = expand_blueprint_into_shots(
        beat_grammar_id="stage1_single_location_v1",
        target_duration_sec=36,
    )

    assert [shot["shot_no"] for shot in shots] == [1, 2, 3, 4, 5, 6]
    assert [shot["beat_type"] for shot in shots] == [
        "establish",
        "attention",
        "approach",
        "contact_action",
        "close_reaction",
        "settle",
    ]
    assert sum(int(shot["target_duration_sec"]) for shot in shots) == 36
    assert shots[0]["camera_intent"] == "wide_master"
    assert shots[-1]["emotion_intent"] == "resolved"
    assert all(
        "same single character identity" in str(shot["continuity_rules"]) for shot in shots
    )


def test_expand_blueprint_spreads_remainder_duration_across_early_shots() -> None:
    from app.services.sequence_blueprint_service import expand_blueprint_into_shots

    shots = expand_blueprint_into_shots(
        beat_grammar_id="stage1_single_location_v1",
        target_duration_sec=37,
    )

    durations = [int(shot["target_duration_sec"]) for shot in shots]

    assert sum(durations) == 37
    assert durations == [7, 6, 6, 6, 6, 6]


def test_expand_blueprint_rejects_shot_count_mismatch() -> None:
    from app.services.sequence_blueprint_service import expand_blueprint_into_shots

    with pytest.raises(ValueError, match="shot_count"):
        expand_blueprint_into_shots(
            beat_grammar_id="stage1_single_location_v1",
            target_duration_sec=36,
            shot_count=5,
        )
