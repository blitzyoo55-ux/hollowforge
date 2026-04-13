from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.db import init_db
from app.models import (
    ComicEpisodeCreate,
    comic_render_job_response_from_row,
    ComicManuscriptProfileResponse,
    list_comic_manuscript_profiles,
)


@pytest.mark.asyncio
async def test_init_db_creates_comic_tables(temp_db) -> None:
    await init_db()

    conn = sqlite3.connect(temp_db)
    try:
        table_names = {
            row[0]
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }
    finally:
        conn.close()

    assert "comic_episodes" in table_names
    assert "comic_episode_scenes" in table_names
    assert "comic_scene_panels" in table_names
    assert "comic_panel_dialogues" in table_names
    assert "comic_panel_render_assets" in table_names
    assert "comic_page_assemblies" in table_names


@pytest.mark.asyncio
async def test_production_hub_core_tables_exist(temp_db) -> None:
    await init_db()
    with sqlite3.connect(temp_db) as conn:
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        table_names = {row[0] for row in table_rows}
    assert {"works", "series", "production_episodes"} <= table_names


@pytest.mark.asyncio
async def test_comic_episode_schema_contract(temp_db) -> None:
    await init_db()

    conn = sqlite3.connect(temp_db)
    try:
        columns = {
            row[1]: {"type": row[2], "notnull": row[3], "pk": row[5]}
            for row in conn.execute("PRAGMA table_info(comic_episodes)").fetchall()
        }
        foreign_keys = conn.execute(
            "PRAGMA foreign_key_list(comic_episodes)"
        ).fetchall()
    finally:
        conn.close()

    assert columns["synopsis"]["type"] == "TEXT"
    assert columns["synopsis"]["notnull"] == 1
    assert columns["source_story_plan_json"]["type"] == "TEXT"
    assert "notes" not in columns

    character_version_fk = next(
        row for row in foreign_keys if row[3] == "character_version_id"
    )
    assert character_version_fk[2] == "character_versions"
    assert character_version_fk[6] == "CASCADE"


@pytest.mark.asyncio
async def test_comic_and_sequence_tables_expose_production_link_columns(temp_db) -> None:
    await init_db()
    with sqlite3.connect(temp_db) as conn:
        comic_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(comic_episodes)")
        }
    assert {"content_mode", "work_id", "series_id", "production_episode_id"} <= comic_columns
@pytest.mark.asyncio
async def test_non_episode_comic_table_contracts(temp_db) -> None:
    await init_db()

    conn = sqlite3.connect(temp_db)
    try:
        scene_columns = {
            row[1]: {"type": row[2], "notnull": row[3]}
            for row in conn.execute("PRAGMA table_info(comic_episode_scenes)").fetchall()
        }
        scene_fks = conn.execute(
            "PRAGMA foreign_key_list(comic_episode_scenes)"
        ).fetchall()
        panel_columns = {
            row[1]: {"type": row[2], "notnull": row[3]}
            for row in conn.execute("PRAGMA table_info(comic_scene_panels)").fetchall()
        }
        panel_fks = conn.execute(
            "PRAGMA foreign_key_list(comic_scene_panels)"
        ).fetchall()
        dialogue_columns = {
            row[1]: {"type": row[2], "notnull": row[3]}
            for row in conn.execute("PRAGMA table_info(comic_panel_dialogues)").fetchall()
        }
        dialogue_fks = conn.execute(
            "PRAGMA foreign_key_list(comic_panel_dialogues)"
        ).fetchall()
        asset_columns = {
            row[1]: {"type": row[2], "notnull": row[3]}
            for row in conn.execute("PRAGMA table_info(comic_panel_render_assets)").fetchall()
        }
        asset_fks = conn.execute(
            "PRAGMA foreign_key_list(comic_panel_render_assets)"
        ).fetchall()
        page_columns = {
            row[1]: {"type": row[2], "notnull": row[3]}
            for row in conn.execute("PRAGMA table_info(comic_page_assemblies)").fetchall()
        }
        page_fks = conn.execute(
            "PRAGMA foreign_key_list(comic_page_assemblies)"
        ).fetchall()
    finally:
        conn.close()

    assert scene_columns["premise"]["notnull"] == 1
    assert scene_columns["involved_character_ids"]["type"] == "TEXT"
    assert next(row for row in scene_fks if row[3] == "episode_id")[6] == "CASCADE"

    assert panel_columns["panel_type"]["notnull"] == 1
    assert panel_columns["reading_order"]["notnull"] == 1
    assert next(row for row in panel_fks if row[3] == "episode_scene_id")[6] == "CASCADE"

    assert dialogue_columns["type"]["notnull"] == 1
    assert dialogue_columns["text"]["notnull"] == 1
    assert next(row for row in dialogue_fks if row[3] == "scene_panel_id")[6] == "CASCADE"
    assert next(row for row in dialogue_fks if row[3] == "speaker_character_id")[6] == "SET NULL"

    assert asset_columns["asset_role"]["notnull"] == 1
    assert asset_columns["bubble_safe_zones"]["type"] == "TEXT"
    assert asset_columns["is_selected"]["notnull"] == 1
    assert next(row for row in asset_fks if row[3] == "scene_panel_id")[6] == "CASCADE"
    assert next(row for row in asset_fks if row[3] == "generation_id")[6] == "SET NULL"

    assert page_columns["ordered_panel_ids"]["type"] == "TEXT"
    assert page_columns["export_state"]["notnull"] == 1
    assert next(row for row in page_fks if row[3] == "episode_id")[6] == "CASCADE"


@pytest.mark.asyncio
async def test_comic_page_assemblies_store_manuscript_profile_id(temp_db) -> None:
    await init_db()

    conn = sqlite3.connect(temp_db)
    try:
        columns = {
            row[1]: {"type": row[2], "notnull": row[3], "default": row[4]}
            for row in conn.execute("PRAGMA table_info(comic_page_assemblies)").fetchall()
        }
    finally:
        conn.close()

    assert columns["manuscript_profile_id"]["type"] == "TEXT"
    assert columns["manuscript_profile_id"]["notnull"] == 1
    assert columns["manuscript_profile_id"]["default"] == "'jp_manga_rightbound_v1'"


@pytest.mark.asyncio
async def test_comic_render_jobs_contract_and_indexes(temp_db) -> None:
    await init_db()

    conn = sqlite3.connect(temp_db)
    try:
        columns = {
            row[1]: {"type": row[2], "notnull": row[3]}
            for row in conn.execute("PRAGMA table_info(comic_render_jobs)").fetchall()
        }
        index_rows = conn.execute("PRAGMA index_list(comic_render_jobs)").fetchall()
        index_names = {row[1] for row in index_rows}
        index_unique_flags = {row[1]: row[2] for row in index_rows}
    finally:
        conn.close()

    assert {"id", "scene_panel_id", "render_asset_id", "generation_id", "status"} <= set(columns)
    assert columns["scene_panel_id"]["notnull"] == 1
    assert columns["render_asset_id"]["notnull"] == 1
    assert columns["generation_id"]["notnull"] == 1

    expected_indexes = {
        "uq_comic_render_jobs_render_asset_id",
        "uq_comic_render_jobs_generation_id",
        "idx_comic_render_jobs_scene_panel_id_updated_at",
        "idx_comic_render_jobs_status_updated_at",
        "idx_comic_render_jobs_external_job_id",
    }
    assert expected_indexes <= index_names
    assert index_unique_flags["uq_comic_render_jobs_render_asset_id"] == 1
    assert index_unique_flags["uq_comic_render_jobs_generation_id"] == 1

    conn = sqlite3.connect(temp_db)
    try:
        scene_panel_index_sql = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'index' AND name = ?
            """,
            ("idx_comic_render_jobs_scene_panel_id_updated_at",),
        ).fetchone()[0]
        status_index_sql = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'index' AND name = ?
            """,
            ("idx_comic_render_jobs_status_updated_at",),
        ).fetchone()[0]
    finally:
        conn.close()

    assert "scene_panel_id" in scene_panel_index_sql
    assert "updated_at" in scene_panel_index_sql
    assert "status" in status_index_sql
    assert "updated_at" in status_index_sql


def test_comic_render_job_response_parses_db_row_request_json() -> None:
    response = comic_render_job_response_from_row(
        {
            "id": "job-1",
            "scene_panel_id": "panel-1",
            "render_asset_id": "asset-1",
            "generation_id": "gen-1",
            "request_index": 1,
            "source_id": "comic-panel-render:panel-1:3:local_preview",
            "target_tool": "comic_panel_still",
            "executor_mode": "local_preview",
            "executor_key": "local_preview",
            "status": "queued",
            "request_json": '{"comic":{"render_asset_id":"asset-1"}}',
            "external_job_id": None,
            "external_job_url": None,
            "output_path": None,
            "error_message": None,
            "submitted_at": None,
            "completed_at": None,
            "created_at": "2026-04-04T00:00:00+00:00",
            "updated_at": "2026-04-04T00:00:00+00:00",
        }
    )

    assert response.request_json == {"comic": {"render_asset_id": "asset-1"}}


def test_lightweight_app_mounts_comic_static_dirs_inside_temp_sandbox(temp_db) -> None:
    from app.config import settings
    from app.main import create_app

    app = create_app(lightweight=True)

    mounted_paths = {
        route.path: Path(route.app.directory)  # type: ignore[attr-defined]
        for route in app.routes
        if hasattr(route, "app") and hasattr(route.app, "directory")
    }

    assert mounted_paths["/data/comics/previews"] == settings.COMICS_PREVIEWS_DIR
    assert mounted_paths["/data/comics/exports"] == settings.COMICS_EXPORTS_DIR
    assert mounted_paths["/data/comics/manifests"] == settings.COMICS_MANIFESTS_DIR

    assert settings.COMICS_PREVIEWS_DIR.is_relative_to(settings.DATA_DIR)
    assert settings.COMICS_EXPORTS_DIR.is_relative_to(settings.DATA_DIR)
    assert settings.COMICS_MANIFESTS_DIR.is_relative_to(settings.DATA_DIR)
    assert settings.COMICS_REPORTS_DIR.is_relative_to(settings.DATA_DIR)
    assert settings.COMICS_PREVIEWS_DIR.exists()
    assert settings.COMICS_EXPORTS_DIR.exists()
    assert settings.COMICS_MANIFESTS_DIR.exists()
    assert settings.COMICS_REPORTS_DIR.exists()


def test_comic_episode_create_requires_character_version_id() -> None:
    with pytest.raises(ValidationError, match="character_version_id"):
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            synopsis="Kaede runs into a private after-hours invitation.",
            title="After Hours Entry",
            target_output="oneshot_manga",
        )


def test_comic_episode_create_requires_non_empty_synopsis() -> None:
    with pytest.raises(ValidationError, match="synopsis"):
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            synopsis="",
            title="After Hours Entry",
            target_output="oneshot_manga",
        )


def test_comic_episode_create_exposes_story_plan_json_and_rejects_notes() -> None:
    episode = ComicEpisodeCreate(
        character_id="char_kaede_ren",
        character_version_id="charver_kaede_ren_still_v1",
        synopsis="Kaede runs into a private after-hours invitation.",
        source_story_plan_json='{"planner":"story_planner","version":"v1"}',
        title="After Hours Entry",
        target_output="oneshot_manga",
    )

    assert episode.source_story_plan_json == '{"planner":"story_planner","version":"v1"}'

    with pytest.raises(ValidationError, match="notes"):
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            synopsis="Kaede runs into a private after-hours invitation.",
            source_story_plan_json='{"planner":"story_planner","version":"v1"}',
            title="After Hours Entry",
            target_output="oneshot_manga",
            notes="not part of task 1",
        )


def test_list_comic_manuscript_profiles_contract() -> None:
    profiles = list_comic_manuscript_profiles()

    assert profiles == [
        ComicManuscriptProfileResponse(
            id="jp_manga_rightbound_v1",
            label="Japanese Manga Right-Bound v1",
            binding_direction="right_to_left",
            finishing_tool="clip_studio_ex",
            print_intent="japanese_manga",
            trim_reference="B5 monochrome manga manuscript preset",
            bleed_reference="CLIP STUDIO EX Japanese comic print bleed preset",
            safe_area_reference="CLIP STUDIO EX default inner safe area guide",
            naming_pattern="page_{page_no:03d}.tif",
        )
    ]
