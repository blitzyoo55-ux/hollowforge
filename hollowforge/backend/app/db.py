"""Async SQLite database helpers."""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
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

        migration_file = _MIGRATIONS_DIR / "001_init.sql"
        if migration_file.exists():
            sql = migration_file.read_text(encoding="utf-8")
            await db.executescript(sql)

        await db.commit()
    finally:
        await db.close()
