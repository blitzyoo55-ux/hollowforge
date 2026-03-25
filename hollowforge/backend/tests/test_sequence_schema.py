from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

import pytest

from app.db import init_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_blueprint(conn: sqlite3.Connection, blueprint_id: str = "bp_1") -> None:
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


def _create_run(
    conn: sqlite3.Connection,
    run_id: str,
    blueprint_id: str = "bp_1",
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
            "all_ages",
            "safe_stage1_v1",
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
            "all_ages",
            "safe_stage1_v1",
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


def _create_shot(conn: sqlite3.Connection, shot_id: str, run_id: str, shot_no: int) -> None:
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
            "all_ages",
            "safe_stage1_v1",
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
        sequence_shot_indexes = conn.execute(
            "PRAGMA index_list(sequence_shots)"
        ).fetchall()
        rough_cut_foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(sequence_runs)"
        ).fetchall()
        shot_clip_foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(shot_clips)"
        ).fetchall()

    assert {row[0] for row in table_rows} == expected_tables
    assert required_sequence_run_columns.issubset(sequence_run_columns)
    for table_name, columns in required_lane_columns.items():
        assert columns.issubset(lane_columns[table_name])
    rough_cut_fk_pairs = {
        (fk[3], fk[4]) for fk in rough_cut_foreign_keys if fk[2] == "rough_cuts"
    }
    assert rough_cut_fk_pairs == {
        ("id", "sequence_run_id"),
        ("selected_rough_cut_id", "id"),
    }
    assert any(
        index[2] == 1 and index[1] == "sqlite_autoindex_sequence_shots_1"
        for index in sequence_shot_indexes
    )
    assert any(
        fk[2] == "animation_jobs"
        and fk[3] == "selected_animation_job_id"
        and fk[4] == "id"
        for fk in shot_clip_foreign_keys
    )


@pytest.mark.asyncio
async def test_sequence_shots_enforce_ordering_and_rough_cut_ownership(temp_db) -> None:
    await init_db()

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        _create_blueprint(conn)
        _create_run(conn, "run_1")
        _create_run(conn, "run_2")
        _create_shot(conn, "shot_1", "run_1", 1)
        _create_rough_cut(conn, "rough_1", "run_1")
        _create_rough_cut(conn, "rough_2", "run_2")
        conn.execute(
            "UPDATE sequence_runs SET selected_rough_cut_id = ? WHERE id = ?",
            ("rough_1", "run_1"),
        )
        conn.commit()

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

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE sequence_runs SET selected_rough_cut_id = ? WHERE id = ?",
                ("rough_2", "run_1"),
            )
