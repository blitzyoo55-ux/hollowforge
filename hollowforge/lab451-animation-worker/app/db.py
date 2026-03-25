"""SQLite helpers for the animation worker."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

import aiosqlite

from app.config import settings


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    db = await aiosqlite.connect(str(settings.DB_PATH))
    db.row_factory = _dict_factory  # type: ignore[assignment]
    try:
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    settings.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(settings.DB_PATH))
    try:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_jobs (
                id TEXT PRIMARY KEY,
                hollowforge_job_id TEXT NOT NULL,
                candidate_id TEXT,
                generation_id TEXT NOT NULL,
                publish_job_id TEXT,
                target_tool TEXT NOT NULL,
                executor_mode TEXT NOT NULL,
                executor_key TEXT NOT NULL,
                status TEXT NOT NULL,
                source_image_url TEXT NOT NULL,
                generation_metadata TEXT,
                request_json TEXT,
                callback_url TEXT,
                callback_token TEXT,
                external_job_id TEXT,
                external_job_url TEXT,
                output_url TEXT,
                error_message TEXT,
                submitted_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_worker_jobs_status_updated
            ON worker_jobs(status, updated_at DESC)
            """
        )
        await db.commit()
    finally:
        await db.close()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
