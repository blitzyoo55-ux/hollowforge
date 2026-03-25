from __future__ import annotations

import sqlite3

import pytest

from app.config import settings
from app.db import init_db


@pytest.mark.asyncio
async def test_sequence_schema_tables_exist() -> None:
    await init_db()

    expected_tables = {
        "sequence_blueprints",
        "sequence_runs",
        "sequence_shots",
        "shot_anchor_candidates",
        "shot_clips",
        "rough_cuts",
    }

    with sqlite3.connect(settings.DB_PATH) as conn:
        rows = conn.execute(
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

    assert {row[0] for row in rows} == expected_tables
