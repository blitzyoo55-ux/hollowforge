from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from app.config import settings
from app.db import get_db, init_db


@pytest.fixture
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(settings, "DB_PATH", data_dir / "hollowforge.db")
    monkeypatch.setattr(settings, "IMAGES_DIR", data_dir / "images")
    monkeypatch.setattr(settings, "THUMBS_DIR", data_dir / "thumbs")
    monkeypatch.setattr(settings, "WORKFLOWS_DIR", data_dir / "workflows")
    monkeypatch.setattr(settings, "COMICS_DIR", data_dir / "comics")
    monkeypatch.setattr(settings, "COMICS_PREVIEWS_DIR", settings.COMICS_DIR / "previews")
    monkeypatch.setattr(settings, "COMICS_EXPORTS_DIR", settings.COMICS_DIR / "exports")
    monkeypatch.setattr(settings, "COMICS_MANIFESTS_DIR", settings.COMICS_DIR / "manifests")
    monkeypatch.setattr(settings, "LEAN_MODE", True)

    for path in (
        settings.DATA_DIR,
        settings.IMAGES_DIR,
        settings.THUMBS_DIR,
        settings.WORKFLOWS_DIR,
        settings.COMICS_DIR,
        settings.COMICS_PREVIEWS_DIR,
        settings.COMICS_EXPORTS_DIR,
        settings.COMICS_MANIFESTS_DIR,
    ):
        Path(path).mkdir(parents=True, exist_ok=True)

    return settings.DB_PATH


@pytest_asyncio.fixture(autouse=True)
async def publishing_db(temp_db: Path):
    await init_db()

    now = datetime(2026, 3, 26, 0, 0, tzinfo=timezone.utc).isoformat()

    (settings.IMAGES_DIR / "gen-ready-1.png").write_bytes(b"ready-1")
    (settings.THUMBS_DIR / "gen-ready-1.png").write_bytes(b"thumb-1")
    (settings.IMAGES_DIR / "gen-ready-2.png").write_bytes(b"ready-2")
    (settings.THUMBS_DIR / "gen-ready-2.png").write_bytes(b"thumb-2")

    async with get_db() as db:
        await db.executemany(
            """
            INSERT INTO generations (
                id,
                prompt,
                checkpoint,
                seed,
                image_path,
                thumbnail_path,
                created_at,
                curated_at,
                publish_approved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "gen-ready-1",
                    "Ready generation 1",
                    "waiIllustriousSDXL_v160.safetensors",
                    101,
                    "images/gen-ready-1.png",
                    "thumbs/gen-ready-1.png",
                    now,
                    now,
                    1,
                ),
                (
                    "gen-ready-2",
                    "Ready generation 2",
                    "waiIllustriousSDXL_v160.safetensors",
                    202,
                    "images/gen-ready-2.png",
                    "thumbs/gen-ready-2.png",
                    now,
                    now,
                    1,
                ),
            ],
        )
        await db.execute(
            """
            INSERT INTO publish_jobs (
                id,
                generation_id,
                caption_variant_id,
                platform,
                status,
                scheduled_at,
                published_at,
                external_post_id,
                external_post_url,
                notes,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "publish-job-draft-1",
                "gen-ready-1",
                None,
                "twitter",
                "draft",
                None,
                None,
                None,
                None,
                "existing draft job",
                now,
                now,
            ),
        )
        await db.commit()
