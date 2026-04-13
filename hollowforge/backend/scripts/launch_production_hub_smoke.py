"""Create or reuse a minimal linked production hub record set."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_db, init_db
from app.models import ComicEpisodeCreate, ProductionEpisodeCreate, ProductionSeriesCreate, ProductionWorkCreate, SequenceBlueprintCreate
from app.services.comic_repository import create_comic_episode, get_comic_episode_detail
from app.services.production_hub_repository import create_production_episode, create_series, create_work, get_production_episode_detail
from app.services.sequence_repository import create_blueprint, get_blueprint

WORK_ID = "work_demo"
SERIES_ID = "series_demo"
COMIC_EPISODE_ID = "comic_ep_demo"
SEQUENCE_BLUEPRINT_ID = "bp_demo"
PRODUCTION_EPISODE_TITLE = "Production Hub Smoke Episode"


async def _fetch_one(query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    async with get_db() as db:
        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
    if row is None:
        return None
    return dict(row)


async def _ensure_work() -> str:
    row = await _fetch_one("SELECT id FROM works WHERE id = ?", (WORK_ID,))
    if row is not None:
        return str(row["id"])
    work = await create_work(
        ProductionWorkCreate(
            id=WORK_ID,
            title="Production Hub Demo",
            format_family="mixed",
            default_content_mode="all_ages",
        )
    )
    return work.id


async def _ensure_series(work_id: str) -> str:
    row = await _fetch_one("SELECT id FROM series WHERE id = ?", (SERIES_ID,))
    if row is not None:
        return str(row["id"])
    series = await create_series(
        ProductionSeriesCreate(
            id=SERIES_ID,
            work_id=work_id,
            title="Production Hub Demo Series",
            delivery_mode="serial",
            audience_mode="all_ages",
        )
    )
    return series.id


async def _ensure_production_episode(work_id: str, series_id: str) -> str:
    row = await _fetch_one(
        """
        SELECT id
        FROM production_episodes
        WHERE work_id = ? AND series_id = ? AND title = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (work_id, series_id, PRODUCTION_EPISODE_TITLE),
    )
    if row is not None:
        return str(row["id"])
    episode = await create_production_episode(
        ProductionEpisodeCreate(
            work_id=work_id,
            series_id=series_id,
            title=PRODUCTION_EPISODE_TITLE,
            synopsis="Smoke verification episode for linked comic and animation tracks.",
            content_mode="all_ages",
            target_outputs=["comic", "animation"],
        )
    )
    return episode.id


async def _ensure_comic_track(work_id: str, series_id: str, production_episode_id: str) -> tuple[str, str]:
    detail = await get_comic_episode_detail(COMIC_EPISODE_ID)
    if detail is not None:
        return detail.episode.id, detail.episode.content_mode
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            work_id=work_id,
            series_id=series_id,
            production_episode_id=production_episode_id,
            content_mode="all_ages",
            title="Production Hub Demo Comic",
            synopsis="Smoke verification comic track linked to the production episode.",
        ),
        episode_id=COMIC_EPISODE_ID,
    )
    return episode.id, episode.content_mode


async def _ensure_animation_track(work_id: str, series_id: str, production_episode_id: str) -> tuple[str, str]:
    blueprint = await get_blueprint(SEQUENCE_BLUEPRINT_ID)
    if blueprint is not None:
        return blueprint.id, blueprint.content_mode
    created = await create_blueprint(
        SequenceBlueprintCreate(
            work_id=work_id,
            series_id=series_id,
            production_episode_id=production_episode_id,
            content_mode="all_ages",
            policy_profile_id="safe_stage1_v1",
            character_id="char_1",
            location_id="location_1",
            beat_grammar_id="stage1_single_location_v1",
            target_duration_sec=36,
            shot_count=6,
            executor_policy="safe_remote_prod",
        ),
        blueprint_id=SEQUENCE_BLUEPRINT_ID,
    )
    return created.id, created.content_mode


async def run_smoke() -> dict[str, str]:
    await init_db()
    work_id = await _ensure_work()
    series_id = await _ensure_series(work_id)
    production_episode_id = await _ensure_production_episode(work_id, series_id)
    comic_episode_id, comic_content_mode = await _ensure_comic_track(
        work_id,
        series_id,
        production_episode_id,
    )
    sequence_blueprint_id, sequence_content_mode = await _ensure_animation_track(
        work_id,
        series_id,
        production_episode_id,
    )

    production_detail = await get_production_episode_detail(production_episode_id)
    if production_detail is None:
        raise RuntimeError("Production episode detail missing after smoke setup")

    return {
        "work_id": work_id,
        "series_id": series_id,
        "production_episode_id": production_episode_id,
        "comic_episode_id": comic_episode_id,
        "comic_content_mode": comic_content_mode,
        "sequence_blueprint_id": sequence_blueprint_id,
        "sequence_content_mode": sequence_content_mode,
    }


def main() -> int:
    result = asyncio.run(run_smoke())
    print(
        "PRODUCTION_HUB_OK "
        f"work={result['work_id']} "
        f"series={result['series_id']} "
        f"production_episode={result['production_episode_id']}"
    )
    print(
        "COMIC_TRACK_OK "
        f"comic_episode={result['comic_episode_id']} "
        f"content_mode={result['comic_content_mode']}"
    )
    print(
        "ANIMATION_TRACK_OK "
        f"sequence_blueprint={result['sequence_blueprint_id']} "
        f"content_mode={result['sequence_content_mode']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
