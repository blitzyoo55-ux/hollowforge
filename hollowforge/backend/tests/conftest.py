from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def temp_backend_settings(tmp_path: Path) -> None:
    original_data_dir = settings.DATA_DIR
    original_db_path = settings.DB_PATH
    original_lean_mode = settings.LEAN_MODE

    settings.DATA_DIR = tmp_path / "data"
    settings.DB_PATH = settings.DATA_DIR / "hollowforge.db"
    settings.LEAN_MODE = True

    try:
        yield
    finally:
        settings.DATA_DIR = original_data_dir
        settings.DB_PATH = original_db_path
        settings.LEAN_MODE = original_lean_mode
