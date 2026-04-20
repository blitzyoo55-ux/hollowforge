from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.db import init_db


@pytest.mark.asyncio
async def test_sequence_blueprints_expose_production_link_columns(temp_db) -> None:
    await init_db()
    with sqlite3.connect(temp_db) as conn:
        sequence_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(sequence_blueprints)")
        }
    assert {"work_id", "series_id", "production_episode_id"} <= sequence_columns


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_blueprint(
    conn: sqlite3.Connection,
    blueprint_id: str = "bp_1",
    content_mode: str = "all_ages",
    policy_profile_id: str = "safe_stage1_v1",
) -> None:
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
            blueprint_id,
            content_mode,
            policy_profile_id,
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


def _create_run(
    conn: sqlite3.Connection,
    run_id: str,
    blueprint_id: str = "bp_1",
    content_mode: str = "all_ages",
    policy_profile_id: str = "safe_stage1_v1",
    selected_rough_cut_id: str | None = None,
) -> None:
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
            run_id,
            blueprint_id,
            content_mode,
            policy_profile_id,
            "adult_local_llm",
            "local",
            "queued",
            selected_rough_cut_id,
            None,
            None,
            _now(),
            _now(),
        ),
    )


def _create_rough_cut(
    conn: sqlite3.Connection,
    rough_cut_id: str,
    run_id: str,
    content_mode: str = "all_ages",
    policy_profile_id: str = "safe_stage1_v1",
) -> None:
    conn.execute(
        """
        INSERT INTO rough_cuts (
            id,
            sequence_run_id,
            content_mode,
            policy_profile_id,
            output_path,
            timeline_json,
            total_duration_sec,
            continuity_score,
            story_score,
            overall_score,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rough_cut_id,
            run_id,
            content_mode,
            policy_profile_id,
            None,
            None,
            None,
            None,
            None,
            None,
            _now(),
            _now(),
        ),
    )


def _create_generation(conn: sqlite3.Connection, generation_id: str = "gen_1") -> None:
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
            generation_id,
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


def _create_shot(
    conn: sqlite3.Connection,
    shot_id: str,
    run_id: str,
    shot_no: int,
    content_mode: str = "all_ages",
    policy_profile_id: str = "safe_stage1_v1",
) -> None:
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
            shot_id,
            run_id,
            content_mode,
            policy_profile_id,
            shot_no,
            "establish",
            "wide",
            "calm",
            "idle",
            6,
            None,
            _now(),
            _now(),
        ),
    )


def _create_anchor_candidate(
    conn: sqlite3.Connection,
    candidate_id: str,
    shot_id: str,
    generation_id: str = "gen_1",
    content_mode: str = "all_ages",
    policy_profile_id: str = "safe_stage1_v1",
) -> None:
    conn.execute(
        """
        INSERT INTO shot_anchor_candidates (
            id,
            sequence_shot_id,
            content_mode,
            policy_profile_id,
            generation_id,
            identity_score,
            location_lock_score,
            beat_fit_score,
            quality_score,
            is_selected_primary,
            is_selected_backup,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            shot_id,
            content_mode,
            policy_profile_id,
            generation_id,
            None,
            None,
            None,
            None,
            0,
            0,
            _now(),
            _now(),
        ),
    )


def _create_clip(
    conn: sqlite3.Connection,
    clip_id: str,
    shot_id: str,
    content_mode: str = "all_ages",
    policy_profile_id: str = "safe_stage1_v1",
) -> None:
    conn.execute(
        """
        INSERT INTO shot_clips (
            id,
            sequence_shot_id,
            content_mode,
            policy_profile_id,
            selected_animation_job_id,
            clip_path,
            clip_duration_sec,
            clip_score,
            retry_count,
            is_degraded,
            created_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clip_id,
            shot_id,
            content_mode,
            policy_profile_id,
            None,
            None,
            None,
            None,
            0,
            0,
            _now(),
            _now(),
        ),
    )


@pytest.mark.asyncio
async def test_sequence_schema_tables_exist(temp_db) -> None:
    await init_db()

    expected_tables = {
        "sequence_blueprints",
        "sequence_runs",
        "sequence_shots",
        "shot_anchor_candidates",
        "shot_clips",
        "rough_cuts",
    }
    required_sequence_run_columns = {
        "content_mode",
        "policy_profile_id",
        "prompt_provider_profile_id",
        "execution_mode",
    }
    required_lane_columns = {
        "sequence_shots": {"content_mode", "policy_profile_id"},
        "shot_anchor_candidates": {"content_mode", "policy_profile_id"},
        "shot_clips": {"content_mode", "policy_profile_id"},
        "rough_cuts": {"content_mode", "policy_profile_id"},
    }

    with sqlite3.connect(temp_db) as conn:
        table_rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name IN (
                'sequence_blueprints',
                'sequence_runs',
                'sequence_shots',
                'shot_anchor_candidates',
                'shot_clips',
                'rough_cuts'
            )
            """
        ).fetchall()
        sequence_run_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(sequence_runs)").fetchall()
        }
        lane_columns = {
            table_name: {
                row[1]
                for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            for table_name in required_lane_columns
        }
        run_foreign_keys = conn.execute("PRAGMA foreign_key_list(sequence_runs)").fetchall()
        shot_foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(sequence_shots)"
        ).fetchall()
        rough_cut_foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(rough_cuts)"
        ).fetchall()
        anchor_foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(shot_anchor_candidates)"
        ).fetchall()
        clip_foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(shot_clips)"
        ).fetchall()
        shot_unique_index_columns = []
        shot_unique_indexes = conn.execute(
            "PRAGMA index_list(sequence_shots)"
        ).fetchall()
        for index in shot_unique_indexes:
            if index[2] != 1:
                continue
            index_columns = {
                row[2] for row in conn.execute(f"PRAGMA index_info({index[1]})")
            }
            shot_unique_index_columns.append(index_columns)

    def fk_pairs(rows: list[tuple], parent_table: str) -> set[tuple[str, str]]:
        return {(row[3], row[4]) for row in rows if row[2] == parent_table}

    assert {row[0] for row in table_rows} == expected_tables
    assert required_sequence_run_columns.issubset(sequence_run_columns)
    for table_name, columns in required_lane_columns.items():
        assert columns.issubset(lane_columns[table_name])
    assert fk_pairs(run_foreign_keys, "sequence_blueprints") == {
        ("sequence_blueprint_id", "id"),
        ("content_mode", "content_mode"),
        ("policy_profile_id", "policy_profile_id"),
    }
    assert fk_pairs(run_foreign_keys, "rough_cuts") == {
        ("id", "sequence_run_id"),
        ("selected_rough_cut_id", "id"),
        ("content_mode", "content_mode"),
        ("policy_profile_id", "policy_profile_id"),
    }
    assert fk_pairs(shot_foreign_keys, "sequence_runs") == {
        ("sequence_run_id", "id"),
        ("content_mode", "content_mode"),
        ("policy_profile_id", "policy_profile_id"),
    }
    assert fk_pairs(rough_cut_foreign_keys, "sequence_runs") == {
        ("sequence_run_id", "id"),
        ("content_mode", "content_mode"),
        ("policy_profile_id", "policy_profile_id"),
    }
    assert fk_pairs(anchor_foreign_keys, "sequence_shots") == {
        ("sequence_shot_id", "id"),
        ("content_mode", "content_mode"),
        ("policy_profile_id", "policy_profile_id"),
    }
    assert fk_pairs(clip_foreign_keys, "sequence_shots") == {
        ("sequence_shot_id", "id"),
        ("content_mode", "content_mode"),
        ("policy_profile_id", "policy_profile_id"),
    }
    assert {"sequence_run_id", "shot_no"} in shot_unique_index_columns


@pytest.mark.asyncio
async def test_sequence_shots_enforce_ordering_and_rough_cut_ownership(temp_db) -> None:
    await init_db()

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        _create_blueprint(conn, "bp_1", "all_ages", "safe_stage1_v1")
        _create_blueprint(conn, "bp_2", "adult", "adult_stage1_v1")
        _create_run(conn, "run_1", "bp_1", "all_ages", "safe_stage1_v1")
        _create_run(conn, "run_2", "bp_2", "adult", "adult_stage1_v1")
        _create_shot(conn, "shot_1", "run_1", 1, "all_ages", "safe_stage1_v1")
        _create_rough_cut(conn, "rough_1", "run_1", "all_ages", "safe_stage1_v1")
        _create_rough_cut(conn, "rough_2", "run_2", "adult", "adult_stage1_v1")
        _create_generation(conn, "gen_1")
        _create_anchor_candidate(
            conn,
            "anchor_1",
            "shot_1",
            "gen_1",
            "all_ages",
            "safe_stage1_v1",
        )
        _create_clip(conn, "clip_1", "shot_1", "all_ages", "safe_stage1_v1")
        conn.execute(
            "UPDATE sequence_runs SET selected_rough_cut_id = ? WHERE id = ?",
            ("rough_1", "run_1"),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
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
                    "run_bad",
                    "bp_1",
                    "adult",
                    "adult_stage1_v1",
                    "adult_local_llm",
                    "local",
                    "queued",
                    None,
                    None,
                    None,
                    _now(),
                    _now(),
                ),
            )

        with pytest.raises(sqlite3.IntegrityError):
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
                    "shot_2",
                    "run_1",
                    "all_ages",
                    "safe_stage1_v1",
                    1,
                    "attention",
                    "medium",
                    "curious",
                    "move",
                    6,
                    None,
                    _now(),
                    _now(),
                ),
            )
        conn.rollback()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO rough_cuts (
                    id,
                    sequence_run_id,
                    content_mode,
                    policy_profile_id,
                    output_path,
                    timeline_json,
                    total_duration_sec,
                    continuity_score,
                    story_score,
                    overall_score,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "rough_bad",
                    "run_1",
                    "adult",
                    "adult_stage1_v1",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    _now(),
                    _now(),
                ),
            )
        conn.rollback()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO shot_anchor_candidates (
                    id,
                    sequence_shot_id,
                    content_mode,
                    policy_profile_id,
                    generation_id,
                    identity_score,
                    location_lock_score,
                    beat_fit_score,
                    quality_score,
                    is_selected_primary,
                    is_selected_backup,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "anchor_bad",
                    "shot_1",
                    "adult",
                    "adult_stage1_v1",
                    "gen_1",
                    None,
                    None,
                    None,
                    None,
                    0,
                    0,
                    _now(),
                    _now(),
                ),
            )
        conn.rollback()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO shot_clips (
                    id,
                    sequence_shot_id,
                    content_mode,
                    policy_profile_id,
                    selected_animation_job_id,
                    clip_path,
                    clip_duration_sec,
                    clip_score,
                    retry_count,
                    is_degraded,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "clip_bad",
                    "shot_1",
                    "adult",
                    "adult_stage1_v1",
                    None,
                    None,
                    None,
                    None,
                    0,
                    0,
                    _now(),
                    _now(),
                ),
            )
        conn.rollback()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE sequence_runs SET selected_rough_cut_id = ? WHERE id = ?",
                ("rough_2", "run_1"),
            )
