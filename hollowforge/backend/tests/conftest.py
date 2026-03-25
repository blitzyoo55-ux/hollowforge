from __future__ import annotations

from pathlib import Path

import pytest

from app.config import settings


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    original_data_dir = settings.DATA_DIR
    original_db_path = settings.DB_PATH
    original_images_dir = settings.IMAGES_DIR
    original_thumbs_dir = settings.THUMBS_DIR
    original_workflows_dir = settings.WORKFLOWS_DIR
    original_lean_mode = settings.LEAN_MODE

    settings.DATA_DIR = tmp_path / "data"
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.DB_PATH = settings.DATA_DIR / "hollowforge.db"
    settings.IMAGES_DIR = settings.DATA_DIR / "images"
    settings.THUMBS_DIR = settings.DATA_DIR / "thumbs"
    settings.WORKFLOWS_DIR = settings.DATA_DIR / "workflows"
    settings.LEAN_MODE = True

    try:
        yield settings.DB_PATH
    finally:
        settings.DATA_DIR = original_data_dir
        settings.DB_PATH = original_db_path
        settings.IMAGES_DIR = original_images_dir
        settings.THUMBS_DIR = original_thumbs_dir
        settings.WORKFLOWS_DIR = original_workflows_dir
        settings.LEAN_MODE = original_lean_mode
