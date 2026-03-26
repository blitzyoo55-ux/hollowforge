from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.db import init_db
from app.services.sequence_repository import (
    create_anchor_candidate,
    list_anchor_candidates,
    update_anchor_candidate_selection,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_sequence_candidate_fixture(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO sequence_blueprints (
                id,
                content_mode,
                policy_profile_id,
                character_id,
                location_id,
                beat_grammar_id,
                target_duration_sec,
                shot_count,
                tone,
                executor_policy,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "bp_1",
                "all_ages",
                "safe_stage1_v1",
                "char_1",
                "location_1",
                "stage1_single_location_v1",
                36,
                6,
                None,
                "safe_remote_prod",
                _now(),
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO sequence_runs (
                id,
                sequence_blueprint_id,
                content_mode,
                policy_profile_id,
                prompt_provider_profile_id,
                execution_mode,
                status,
                selected_rough_cut_id,
                total_score,
                error_summary,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run_1",
                "bp_1",
                "all_ages",
                "safe_stage1_v1",
                "safe_hosted_grok",
                "local",
                "queued",
                None,
                None,
                None,
                _now(),
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO sequence_shots (
                id,
                sequence_run_id,
                content_mode,
                policy_profile_id,
                shot_no,
                beat_type,
                camera_intent,
                emotion_intent,
                action_intent,
                target_duration_sec,
                continuity_rules,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "shot_1",
                "run_1",
                "all_ages",
                "safe_stage1_v1",
                1,
                "establish",
                "wide_master",
                "grounded",
                "reveal_location",
                6,
                "continuity",
                _now(),
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO generations (
                id,
                prompt,
                checkpoint,
                loras,
                seed,
                steps,
                cfg,
                width,
                height,
                sampler,
                scheduler,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "gen_1",
                "prompt",
                "checkpoint.safetensors",
                "[]",
                1,
                28,
                7.0,
                832,
                1216,
                "euler",
                "normal",
                "queued",
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO generations (
                id,
                prompt,
                checkpoint,
                loras,
                seed,
                steps,
                cfg,
                width,
                height,
                sampler,
                scheduler,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "gen_2",
                "prompt",
                "checkpoint.safetensors",
                "[]",
                2,
                28,
                7.0,
                832,
                1216,
                "euler",
                "normal",
                "queued",
                _now(),
            ),
        )
        conn.commit()


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


def test_expand_blueprint_rejects_wrong_content_lane() -> None:
    from app.services.sequence_blueprint_service import expand_blueprint_into_shots

    with pytest.raises(ValueError, match="content mode"):
        expand_blueprint_into_shots(
            beat_grammar_id="stage1_single_location_v1",
            target_duration_sec=36,
            content_mode="adult_nsfw",
        )


def test_expand_blueprint_allows_adult_stage1_lane_with_adult_grammar() -> None:
    from app.services.sequence_blueprint_service import expand_blueprint_into_shots

    shots = expand_blueprint_into_shots(
        beat_grammar_id="adult_stage1_v1",
        target_duration_sec=36,
        content_mode="adult_nsfw",
    )

    assert [shot["beat_type"] for shot in shots] == [
        "establish",
        "attention",
        "approach",
        "contact_action",
        "close_reaction",
        "settle",
    ]
    assert all("same fixed location" in str(shot["continuity_rules"]) for shot in shots)


@pytest.mark.asyncio
async def test_create_anchor_candidate_rejects_primary_backup_overlap(temp_db) -> None:
    await init_db()
    _seed_sequence_candidate_fixture(str(temp_db))

    with pytest.raises(ValueError, match="both primary and backup"):
        await create_anchor_candidate(
            sequence_shot_id="shot_1",
            content_mode="all_ages",
            policy_profile_id="safe_stage1_v1",
            generation_id="gen_1",
            is_selected_primary=True,
            is_selected_backup=True,
        )


@pytest.mark.asyncio
async def test_update_anchor_candidate_selection_clears_sibling_primary(temp_db) -> None:
    await init_db()
    _seed_sequence_candidate_fixture(str(temp_db))

    first = await create_anchor_candidate(
        candidate_id="cand_1",
        sequence_shot_id="shot_1",
        content_mode="all_ages",
        policy_profile_id="safe_stage1_v1",
        generation_id="gen_1",
        is_selected_primary=True,
    )
    second = await create_anchor_candidate(
        candidate_id="cand_2",
        sequence_shot_id="shot_1",
        content_mode="all_ages",
        policy_profile_id="safe_stage1_v1",
        generation_id="gen_2",
    )

    assert first["is_selected_primary"] is True
    updated = await update_anchor_candidate_selection("cand_2", is_selected_primary=True)

    assert updated is not None
    assert updated["is_selected_primary"] is True

    rows = await list_anchor_candidates("shot_1")
    by_id = {row["id"]: row for row in rows}
    assert by_id["cand_1"]["is_selected_primary"] is False
    assert by_id["cand_2"]["is_selected_primary"] is True


@pytest.mark.asyncio
async def test_update_anchor_candidate_selection_backup_clears_primary_on_row(temp_db) -> None:
    await init_db()
    _seed_sequence_candidate_fixture(str(temp_db))

    await create_anchor_candidate(
        candidate_id="cand_1",
        sequence_shot_id="shot_1",
        content_mode="all_ages",
        policy_profile_id="safe_stage1_v1",
        generation_id="gen_1",
        is_selected_primary=True,
    )

    updated = await update_anchor_candidate_selection("cand_1", is_selected_backup=True)

    assert updated is not None
    assert updated["is_selected_primary"] is False
    assert updated["is_selected_backup"] is True
