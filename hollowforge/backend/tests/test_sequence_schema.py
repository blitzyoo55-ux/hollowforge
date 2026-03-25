from __future__ import annotations

import sqlite3

import pytest

from app.db import init_db


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
        shot_clip_foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(shot_clips)"
        ).fetchall()

    assert {row[0] for row in table_rows} == expected_tables
    assert required_sequence_run_columns.issubset(sequence_run_columns)
    assert any(
        fk[2] == "animation_jobs"
        and fk[3] == "selected_animation_job_id"
        and fk[4] == "id"
        for fk in shot_clip_foreign_keys
    )
