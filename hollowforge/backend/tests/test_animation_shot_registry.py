from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.models import ComicEpisodeCreate
from app.services.animation_shot_registry import (
    create_animation_shot_variant,
    get_current_animation_shot,
    resolve_or_create_current_animation_shot,
    update_animation_shot_variant_from_job,
)
from app.services.comic_repository import create_comic_episode


def _now() -> str:
    return "2026-04-08T00:00:00+00:00"


def _insert_animation_job(
    temp_db: Path,
    *,
    job_id: str,
    status: str,
    generation_id: str = "gen-ready-1",
    output_path: str | None = None,
    error_message: str | None = None,
    completed_at: str | None = None,
) -> None:
    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO animation_jobs (
                id,
                candidate_id,
                generation_id,
                publish_job_id,
                target_tool,
                executor_mode,
                executor_key,
                status,
                request_json,
                external_job_id,
                external_job_url,
                output_path,
                error_message,
                submitted_at,
                completed_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                None,
                generation_id,
                None,
                "dreamactor",
                "remote_worker",
                "default",
                status,
                None,
                f"worker-{job_id}",
                f"https://worker.test/jobs/{job_id}",
                output_path,
                error_message,
                _now(),
                completed_at,
                _now(),
                _now(),
            ),
        )
        conn.commit()


def _seed_panel_assets(
    temp_db: Path,
    *,
    episode_id: str,
    scene_panel_id: str = "comic_panel_shot_registry_service_1",
    asset_a_id: str = "comic_asset_shot_registry_service_1",
    asset_b_id: str = "comic_asset_shot_registry_service_2",
) -> tuple[str, str]:
    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO comic_episode_scenes (
                id,
                episode_id,
                scene_no,
                premise,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "comic_scene_shot_registry_service_1",
                episode_id,
                1,
                "Service test scene.",
                _now(),
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO comic_scene_panels (
                id,
                episode_scene_id,
                panel_no,
                panel_type,
                reading_order,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scene_panel_id,
                "comic_scene_shot_registry_service_1",
                1,
                "beat",
                1,
                _now(),
                _now(),
            ),
        )
        conn.executemany(
            """
            INSERT INTO comic_panel_render_assets (
                id,
                scene_panel_id,
                generation_id,
                asset_role,
                bubble_safe_zones,
                is_selected,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    asset_a_id,
                    scene_panel_id,
                    "gen-ready-1",
                    "selected",
                    "[]",
                    1,
                    _now(),
                    _now(),
                ),
                (
                    asset_b_id,
                    scene_panel_id,
                    "gen-ready-2",
                    "selected",
                    "[]",
                    1,
                    _now(),
                    _now(),
                ),
            ],
        )
        conn.commit()
    return asset_a_id, asset_b_id


def _fetch_shot_rows(temp_db: Path) -> list[dict[str, object]]:
    with sqlite3.connect(temp_db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
            FROM animation_shots
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]


@pytest.mark.asyncio
async def test_resolve_current_shot_reuses_same_selected_render(temp_db: Path) -> None:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Animation Shot Service Reuse",
            synopsis="Ensure same selected render reuses the same shot row.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_shot_registry_service_reuse",
    )
    asset_a_id, _asset_b_id = _seed_panel_assets(temp_db, episode_id=episode.id)

    first = await resolve_or_create_current_animation_shot(
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_1",
        selected_render_asset_id=asset_a_id,
        generation_id="gen-ready-1",
    )
    second = await resolve_or_create_current_animation_shot(
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_1",
        selected_render_asset_id=asset_a_id,
        generation_id="gen-ready-1",
    )

    rows = _fetch_shot_rows(temp_db)
    assert second.id == first.id
    assert len(rows) == 1
    assert rows[0]["selected_render_asset_id"] == asset_a_id
    assert rows[0]["is_current"] == 1


@pytest.mark.asyncio
async def test_resolve_current_shot_creates_new_row_when_selected_render_changes(
    temp_db: Path,
) -> None:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Animation Shot Service Switch",
            synopsis="Ensure a new current shot is created when the selected render changes.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_shot_registry_service_switch",
    )
    asset_a_id, asset_b_id = _seed_panel_assets(
        temp_db,
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_switch_1",
        asset_a_id="comic_asset_shot_registry_service_switch_1",
        asset_b_id="comic_asset_shot_registry_service_switch_2",
    )

    first = await resolve_or_create_current_animation_shot(
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_switch_1",
        selected_render_asset_id=asset_a_id,
        generation_id="gen-ready-1",
    )
    second = await resolve_or_create_current_animation_shot(
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_switch_1",
        selected_render_asset_id=asset_b_id,
        generation_id="gen-ready-2",
    )

    rows = _fetch_shot_rows(temp_db)
    first_row = next(row for row in rows if row["id"] == first.id)
    second_row = next(row for row in rows if row["id"] == second.id)
    assert second.id != first.id
    assert len(rows) == 2
    assert first_row["is_current"] == 0
    assert second_row["is_current"] == 1


@pytest.mark.asyncio
async def test_create_variant_links_job_and_preset(temp_db: Path) -> None:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Animation Shot Variant Create",
            synopsis="Ensure variants persist preset/job linkage.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_shot_registry_service_variant",
    )
    asset_a_id, _asset_b_id = _seed_panel_assets(
        temp_db,
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_variant_1",
        asset_a_id="comic_asset_shot_registry_service_variant_1",
        asset_b_id="comic_asset_shot_registry_service_variant_2",
    )
    shot = await resolve_or_create_current_animation_shot(
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_variant_1",
        selected_render_asset_id=asset_a_id,
        generation_id="gen-ready-1",
    )
    _insert_animation_job(temp_db, job_id="anim-shot-variant-job-1", status="queued")

    variant = await create_animation_shot_variant(
        animation_shot_id=shot.id,
        animation_job_id="anim-shot-variant-job-1",
        preset_id="sdxl_ipadapter_microanim_v2",
        launch_reason="initial",
        status="queued",
    )

    assert variant.animation_shot_id == shot.id
    assert variant.animation_job_id == "anim-shot-variant-job-1"
    assert variant.preset_id == "sdxl_ipadapter_microanim_v2"
    assert variant.launch_reason == "initial"
    assert variant.status == "queued"


@pytest.mark.asyncio
async def test_update_animation_shot_variant_from_job_syncs_terminal_fields(
    temp_db: Path,
) -> None:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Animation Shot Variant Sync",
            synopsis="Ensure linked variants mirror terminal animation job fields.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_shot_registry_service_sync",
    )
    asset_a_id, _asset_b_id = _seed_panel_assets(
        temp_db,
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_sync_1",
        asset_a_id="comic_asset_shot_registry_service_sync_1",
        asset_b_id="comic_asset_shot_registry_service_sync_2",
    )
    shot = await resolve_or_create_current_animation_shot(
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_sync_1",
        selected_render_asset_id=asset_a_id,
        generation_id="gen-ready-1",
    )
    _insert_animation_job(
        temp_db,
        job_id="anim-shot-variant-job-sync-1",
        status="queued",
    )
    await create_animation_shot_variant(
        animation_shot_id=shot.id,
        animation_job_id="anim-shot-variant-job-sync-1",
        preset_id="sdxl_ipadapter_microanim_v2",
        launch_reason="initial",
        status="queued",
    )
    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            UPDATE animation_jobs
            SET status = ?,
                output_path = ?,
                error_message = ?,
                completed_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                "completed",
                "outputs/shot-sync.mp4",
                None,
                "2026-04-08T01:00:00+00:00",
                "2026-04-08T01:00:00+00:00",
                "anim-shot-variant-job-sync-1",
            ),
        )
        conn.commit()

    variant = await update_animation_shot_variant_from_job(
        "anim-shot-variant-job-sync-1"
    )

    assert variant is not None
    assert variant.status == "completed"
    assert variant.output_path == "outputs/shot-sync.mp4"
    assert variant.error_message is None
    assert variant.completed_at == "2026-04-08T01:00:00+00:00"


@pytest.mark.asyncio
async def test_get_current_animation_shot_returns_recent_variants(temp_db: Path) -> None:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Animation Shot Current Read",
            synopsis="Ensure the current shot response includes recent variants.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_shot_registry_service_current",
    )
    asset_a_id, _asset_b_id = _seed_panel_assets(
        temp_db,
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_current_1",
        asset_a_id="comic_asset_shot_registry_service_current_1",
        asset_b_id="comic_asset_shot_registry_service_current_2",
    )
    shot = await resolve_or_create_current_animation_shot(
        episode_id=episode.id,
        scene_panel_id="comic_panel_shot_registry_service_current_1",
        selected_render_asset_id=asset_a_id,
        generation_id="gen-ready-1",
    )
    _insert_animation_job(temp_db, job_id="anim-shot-current-job-1", status="queued")
    _insert_animation_job(temp_db, job_id="anim-shot-current-job-2", status="completed")
    await create_animation_shot_variant(
        animation_shot_id=shot.id,
        animation_job_id="anim-shot-current-job-1",
        preset_id="preset-a",
        launch_reason="initial",
        status="queued",
    )
    await create_animation_shot_variant(
        animation_shot_id=shot.id,
        animation_job_id="anim-shot-current-job-2",
        preset_id="preset-b",
        launch_reason="rerun",
        status="completed",
        output_path="outputs/current-2.mp4",
    )

    current = await get_current_animation_shot(
        scene_panel_id="comic_panel_shot_registry_service_current_1",
        selected_render_asset_id=asset_a_id,
        limit=2,
    )

    assert current.shot is not None
    assert current.shot.id == shot.id
    assert [variant.animation_job_id for variant in current.variants] == [
        "anim-shot-current-job-2",
        "anim-shot-current-job-1",
    ]
