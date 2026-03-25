"""Async SQLite database helpers."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from app.config import settings

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Row factory that returns dicts keyed by column name."""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield an aiosqlite connection with dict row factory."""
    db = await aiosqlite.connect(str(settings.DB_PATH))
    db.row_factory = _dict_factory  # type: ignore[assignment]
    try:
        await db.execute("PRAGMA foreign_keys = ON")
        yield db
    finally:
        await db.close()


async def init_db() -> None:
    """Create tables from migration SQL files and enable WAL mode."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

    db = await aiosqlite.connect(str(settings.DB_PATH))
    try:
        await db.execute("PRAGMA journal_mode=WAL")
        await run_migrations(db)
        await db.commit()
    finally:
        await db.close()


async def run_migrations(db: aiosqlite.Connection) -> None:
    """Apply unapplied SQL migrations in filename order."""
    await db.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
               filename TEXT PRIMARY KEY,
               applied_at TEXT NOT NULL
           )"""
    )

    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    for migration_file in migration_files:
        cursor = await db.execute(
            "SELECT 1 FROM schema_migrations WHERE filename = ?",
            (migration_file.name,),
        )
        if await cursor.fetchone():
            continue

        sql = migration_file.read_text(encoding="utf-8")
        try:
            await db.executescript(sql)
        except sqlite3.OperationalError as exc:
            # Allow startup to proceed when schema drift already contains
            # the target column (e.g. manual ALTER before tracked migration).
            if "duplicate column name" not in str(exc).lower():
                raise
        await db.execute(
            "INSERT INTO schema_migrations (filename, applied_at) VALUES (?, ?)",
            (
                migration_file.name,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
