from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.db import init_db
from app.models import (
    ComicEpisodeCreate,
    ComicStoryPlanImportRequest,
    StoryPlannerPlanRequest,
    comic_render_job_response_from_row,
    ComicManuscriptProfileResponse,
    list_comic_manuscript_profiles,
)
from app.services.comic_repository import create_comic_episode
from app.services.story_planner_service import plan_story_episode


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
    assert columns["render_lane"]["type"] == "TEXT"
    assert columns["render_lane"]["notnull"] == 1
    assert columns["series_style_id"]["type"] == "TEXT"
    assert columns["character_series_binding_id"]["type"] == "TEXT"
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
async def test_comic_verification_run_table_exists(temp_db) -> None:
    await init_db()
    with sqlite3.connect(temp_db) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "comic_verification_runs" in table_names


@pytest.mark.asyncio
async def test_comic_episodes_enforce_unique_production_episode_link(temp_db) -> None:
    await init_db()
    await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Existing linked episode",
            synopsis="The first linked episode owns the production link.",
            target_output="oneshot_manga",
            production_episode_id="prod_ep_unique",
        ),
        episode_id="comic_ep_existing",
    )

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(
            sqlite3.IntegrityError,
            match=r"comic_episodes.production_episode_id already linked",
        ):
            conn.execute(
                """
                INSERT INTO comic_episodes (
                    id,
                    character_id,
                    character_version_id,
                    content_mode,
                    work_id,
                    series_id,
                    production_episode_id,
                    title,
                    synopsis,
                    source_story_plan_json,
                    status,
                    continuity_summary,
                    canon_delta,
                    target_output,
                    render_lane,
                    series_style_id,
                    character_series_binding_id,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "comic_ep_duplicate",
                    "char_kaede_ren",
                    "charver_kaede_ren_still_v1",
                    "all_ages",
                    None,
                    None,
                    "prod_ep_unique",
                    "Duplicate linked episode",
                    "Should fail because the production link is already owned.",
                    None,
                    "draft",
                    None,
                    None,
                    "oneshot_manga",
                    "legacy_standard",
                    None,
                    None,
                    "2026-04-13T00:00:00+00:00",
                    "2026-04-13T00:00:00+00:00",
                ),
            )


def test_comic_episode_create_schema_requires_complete_explicit_v2_fields() -> None:
    with pytest.raises(ValidationError, match="requires series_style_id"):
        ComicEpisodeCreate(
            character_id="char_camila_duarte",
            character_version_id="charver_camila_duarte_still_v1",
            title="Camila V2 Missing Style",
            synopsis="Should reject missing style when lane is explicit V2.",
            target_output="oneshot_manga",
            render_lane="character_canon_v2",
            character_series_binding_id="camila_pilot_binding_v1",
        )

    with pytest.raises(ValidationError, match="requires character_series_binding_id"):
        ComicEpisodeCreate(
            character_id="char_camila_duarte",
            character_version_id="charver_camila_duarte_still_v1",
            title="Camila V2 Missing Binding",
            synopsis="Should reject missing binding when lane is explicit V2.",
            target_output="oneshot_manga",
            render_lane="character_canon_v2",
            series_style_id="camila_pilot_v1",
        )


def test_story_plan_import_schema_requires_complete_explicit_v2_fields() -> None:
    approved_plan = plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt="Camila receives a quiet briefing in a closed lounge.",
            lane="adult_nsfw",
        )
    )
    with pytest.raises(ValidationError, match="requires series_style_id"):
        ComicStoryPlanImportRequest(
            approved_plan=approved_plan,
            character_version_id="charver_camila_duarte_still_v1",
            title="Camila V2 Import Missing Style",
            render_lane="character_canon_v2",
            character_series_binding_id="camila_pilot_binding_v1",
        )


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
async def test_animation_shot_registry_schema_contract(temp_db) -> None:
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
        shot_columns = {
            row[1]: {"type": row[2], "notnull": row[3]}
            for row in conn.execute("PRAGMA table_info(animation_shots)").fetchall()
        }
        shot_fks = conn.execute(
            "PRAGMA foreign_key_list(animation_shots)"
        ).fetchall()
        variant_columns = {
            row[1]: {"type": row[2], "notnull": row[3]}
            for row in conn.execute(
                "PRAGMA table_info(animation_shot_variants)"
            ).fetchall()
        }
        variant_fks = conn.execute(
            "PRAGMA foreign_key_list(animation_shot_variants)"
        ).fetchall()
        index_rows = conn.execute("PRAGMA index_list(animation_shots)").fetchall()
        index_names = {row[1] for row in index_rows}
        variant_index_rows = conn.execute(
            "PRAGMA index_list(animation_shot_variants)"
        ).fetchall()
        variant_index_names = {row[1] for row in variant_index_rows}
        shot_trigger_rows = conn.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'trigger'
              AND (
                  name LIKE 'trg_animation_shots_%'
                  OR name LIKE 'trg_comic_episode_scenes_%'
                  OR name LIKE 'trg_comic_scene_panels_%'
                  OR name LIKE 'trg_comic_panel_render_assets_%'
              )
            """
        ).fetchall()
        shot_trigger_names = {row[0] for row in shot_trigger_rows}
    finally:
        conn.close()

    assert "animation_shots" in table_names
    assert "animation_shot_variants" in table_names

    assert {
        "id",
        "source_kind",
        "episode_id",
        "scene_panel_id",
        "selected_render_asset_id",
        "generation_id",
        "is_current",
        "created_at",
        "updated_at",
    } <= set(shot_columns)
    assert {
        "id",
        "animation_shot_id",
        "animation_job_id",
        "preset_id",
        "launch_reason",
        "status",
        "created_at",
    } <= set(variant_columns)

    assert shot_columns["source_kind"]["notnull"] == 1
    assert shot_columns["source_kind"]["type"] == "TEXT"
    assert shot_columns["episode_id"]["notnull"] == 1
    assert shot_columns["scene_panel_id"]["notnull"] == 1
    assert shot_columns["selected_render_asset_id"]["notnull"] == 1
    assert shot_columns["generation_id"]["notnull"] == 0
    assert shot_columns["is_current"]["notnull"] == 1
    assert shot_columns["created_at"]["notnull"] == 1
    assert shot_columns["updated_at"]["notnull"] == 1

    assert next(row for row in shot_fks if row[3] == "episode_id")[6] == "CASCADE"
    assert next(row for row in shot_fks if row[3] == "scene_panel_id")[6] == "CASCADE"
    assert (
        next(row for row in shot_fks if row[3] == "selected_render_asset_id")[6]
        == "CASCADE"
    )
    assert next(row for row in shot_fks if row[3] == "generation_id")[6] == "SET NULL"

    assert variant_columns["animation_shot_id"]["notnull"] == 1
    assert variant_columns["animation_job_id"]["notnull"] == 1
    assert variant_columns["preset_id"]["notnull"] == 1
    assert variant_columns["launch_reason"]["notnull"] == 1
    assert variant_columns["status"]["notnull"] == 1
    assert variant_columns["output_path"]["notnull"] == 0
    assert variant_columns["error_message"]["notnull"] == 0
    assert variant_columns["created_at"]["notnull"] == 1
    assert variant_columns["completed_at"]["notnull"] == 0

    assert next(row for row in variant_fks if row[3] == "animation_shot_id")[6] == "CASCADE"
    assert next(row for row in variant_fks if row[3] == "animation_job_id")[6] == "CASCADE"

    assert "uq_animation_shots_selected_render_asset_id" in index_names
    assert "uq_animation_shot_variants_animation_job_id" in variant_index_names
    assert (
        "idx_animation_shot_variants_animation_shot_id_created_at"
        in variant_index_names
    )
    assert (
        next(
            row for row in index_rows if row[1] == "uq_animation_shots_selected_render_asset_id"
        )[2]
        == 1
    )
    assert (
        next(
            row for row in variant_index_rows
            if row[1] == "uq_animation_shot_variants_animation_job_id"
        )[2]
        == 1
    )
    assert {
        "trg_animation_shots_validate_episode_scene_panel_insert",
        "trg_animation_shots_validate_episode_scene_panel_update",
        "trg_animation_shots_validate_scene_panel_asset_insert",
        "trg_animation_shots_validate_scene_panel_asset_update",
        "trg_animation_shots_validate_selected_asset_insert",
        "trg_animation_shots_validate_selected_asset_update",
        "trg_animation_shots_validate_generation_match_insert",
        "trg_animation_shots_validate_generation_match_update",
        "trg_comic_episode_scenes_block_animation_shot_reparent",
        "trg_comic_scene_panels_block_animation_shot_reparent",
        "trg_comic_panel_render_assets_block_animation_shot_reparent",
        "trg_comic_panel_render_assets_block_animation_shot_generation_drift",
    } <= shot_trigger_names

    episode_one = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Animation Shot Registry One",
            synopsis="Seed comic episode for animation shot validation.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_animation_shot_registry_1",
    )
    episode_two = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="Animation Shot Registry Two",
            synopsis="Second comic episode for impossible lineage validation.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_animation_shot_registry_2",
    )
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
                "comic_scene_animation_shot_registry_2",
                episode_one.id,
                2,
                "A mismatched lineage source scene.",
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
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
                "comic_scene_animation_shot_registry_3",
                episode_two.id,
                1,
                "A safe target scene in the new episode.",
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
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
                "comic_panel_animation_shot_registry_3",
                "comic_scene_animation_shot_registry_3",
                1,
                "beat",
                2,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
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
                "comic_panel_animation_shot_registry_2",
                "comic_scene_animation_shot_registry_2",
                1,
                "beat",
                2,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
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
            (
                "comic_asset_animation_shot_registry_2",
                "comic_panel_animation_shot_registry_3",
                "gen-ready-2",
                "candidate",
                "[]",
                0,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
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
            (
                "comic_asset_animation_shot_registry_3",
                "comic_panel_animation_shot_registry_3",
                "gen-ready-1",
                "candidate",
                "[]",
                0,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.commit()

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
                "comic_scene_animation_shot_registry_1",
                episode_one.id,
                1,
                "A valid lineage source scene.",
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
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
                "comic_panel_animation_shot_registry_1",
                "comic_scene_animation_shot_registry_1",
                1,
                "beat",
                1,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
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
            (
                "comic_asset_animation_shot_registry_1",
                "comic_panel_animation_shot_registry_1",
                "gen-ready-1",
                "selected",
                "[]",
                1,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
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
            (
                "comic_asset_animation_shot_registry_4",
                "comic_panel_animation_shot_registry_1",
                "gen-ready-2",
                "candidate",
                "[]",
                0,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
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
            (
                "comic_asset_animation_shot_registry_5",
                "comic_panel_animation_shot_registry_1",
                "gen-ready-2",
                "selected",
                "[]",
                1,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
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
            (
                "comic_asset_animation_shot_registry_6",
                "comic_panel_animation_shot_registry_1",
                "gen-ready-1",
                "candidate",
                "[]",
                0,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.execute(
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
            (
                "comic_asset_animation_shot_registry_7",
                "comic_panel_animation_shot_registry_3",
                "gen-ready-1",
                "selected",
                "[]",
                1,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=r"CHECK constraint failed",
        ):
            conn.execute(
                """
                INSERT INTO animation_shots (
                    id,
                    source_kind,
                    episode_id,
                    scene_panel_id,
                    selected_render_asset_id,
                    generation_id,
                    is_current,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "animation_shot_registry_invalid_source_kind_1",
                    "comic_selected_preview",
                    episode_one.id,
                    "comic_panel_animation_shot_registry_1",
                    "comic_asset_animation_shot_registry_1",
                    "gen-ready-1",
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            )
            conn.commit()

        conn.execute(
            """
            INSERT INTO animation_shots (
                id,
                source_kind,
                episode_id,
                scene_panel_id,
                selected_render_asset_id,
                generation_id,
                is_current,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "animation_shot_registry_valid_1",
                "comic_selected_render",
                episode_one.id,
                "comic_panel_animation_shot_registry_1",
                "comic_asset_animation_shot_registry_1",
                "gen-ready-1",
                1,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape("animation_shots.scene_panel_id must belong to episode_id"),
        ):
            conn.execute(
                """
                INSERT INTO animation_shots (
                    id,
                    source_kind,
                    episode_id,
                    scene_panel_id,
                    selected_render_asset_id,
                    generation_id,
                    is_current,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "animation_shot_registry_invalid_1",
                    "comic_selected_render",
                    episode_two.id,
                    "comic_panel_animation_shot_registry_1",
                    "comic_asset_animation_shot_registry_1",
                    "gen-ready-1",
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.selected_render_asset_id must point to selected render asset"
            ),
        ):
            conn.execute(
                """
                INSERT INTO animation_shots (
                    id,
                    source_kind,
                    episode_id,
                    scene_panel_id,
                    selected_render_asset_id,
                    generation_id,
                    is_current,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "animation_shot_registry_invalid_asset_1",
                    "comic_selected_render",
                    episode_one.id,
                    "comic_panel_animation_shot_registry_1",
                    "comic_asset_animation_shot_registry_6",
                    "gen-ready-1",
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.selected_render_asset_id must belong to scene_panel_id"
            ),
        ):
            conn.execute(
                """
                INSERT INTO animation_shots (
                    id,
                    source_kind,
                    episode_id,
                    scene_panel_id,
                    selected_render_asset_id,
                    generation_id,
                    is_current,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "animation_shot_registry_invalid_cross_panel_asset_1",
                    "comic_selected_render",
                    episode_one.id,
                    "comic_panel_animation_shot_registry_1",
                    "comic_asset_animation_shot_registry_7",
                    "gen-ready-1",
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.selected_render_asset_id must point to selected render asset"
            ),
        ):
            conn.execute(
                """
                INSERT INTO animation_shots (
                    id,
                    source_kind,
                    episode_id,
                    scene_panel_id,
                    selected_render_asset_id,
                    generation_id,
                    is_current,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "animation_shot_registry_invalid_selected_asset_1",
                    "comic_selected_render",
                    episode_one.id,
                    "comic_panel_animation_shot_registry_1",
                    "comic_asset_animation_shot_registry_4",
                    "gen-ready-2",
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.generation_id must match selected_render_asset_id.generation_id"
            ),
        ):
            conn.execute(
                """
                INSERT INTO animation_shots (
                    id,
                    source_kind,
                    episode_id,
                    scene_panel_id,
                    selected_render_asset_id,
                    generation_id,
                    is_current,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "animation_shot_registry_invalid_generation_1",
                    "comic_selected_render",
                    episode_one.id,
                    "comic_panel_animation_shot_registry_1",
                    "comic_asset_animation_shot_registry_1",
                    "gen-ready-2",
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.generation_id must match selected_render_asset_id.generation_id"
            ),
        ):
            conn.execute(
                """
                INSERT INTO animation_shots (
                    id,
                    source_kind,
                    episode_id,
                    scene_panel_id,
                    selected_render_asset_id,
                    generation_id,
                    is_current,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "animation_shot_registry_invalid_generation_null_1",
                    "comic_selected_render",
                    episode_one.id,
                    "comic_panel_animation_shot_registry_1",
                    "comic_asset_animation_shot_registry_1",
                    None,
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape("animation_shots.scene_panel_id must belong to episode_id"),
        ):
            conn.execute(
                """
                UPDATE animation_shots
                SET episode_id = ?
                WHERE id = ?
                """,
                (
                    episode_two.id,
                    "animation_shot_registry_valid_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.generation_id must match selected_render_asset_id.generation_id"
            ),
        ):
            conn.execute(
                """
                UPDATE animation_shots
                SET generation_id = ?
                WHERE id = ?
                """,
                (
                    "gen-ready-2",
                    "animation_shot_registry_valid_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.generation_id must match selected_render_asset_id.generation_id"
            ),
        ):
            conn.execute(
                """
                UPDATE animation_shots
                SET generation_id = ?
                WHERE id = ?
                """,
                (
                    None,
                    "animation_shot_registry_valid_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.selected_render_asset_id must point to selected render asset"
            ),
        ):
            conn.execute(
                """
                UPDATE animation_shots
                SET selected_render_asset_id = ?,
                    generation_id = ?
                WHERE id = ?
                """,
                (
                    "comic_asset_animation_shot_registry_6",
                    "gen-ready-1",
                    "animation_shot_registry_valid_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.generation_id must match selected_render_asset_id.generation_id"
            ),
        ):
            conn.execute(
                """
                UPDATE animation_shots
                SET selected_render_asset_id = ?
                WHERE id = ?
                """,
                (
                    "comic_asset_animation_shot_registry_5",
                    "animation_shot_registry_valid_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.selected_render_asset_id must belong to scene_panel_id"
            ),
        ):
            conn.execute(
                """
                UPDATE animation_shots
                SET scene_panel_id = ?
                WHERE id = ?
                """,
                (
                    "comic_panel_animation_shot_registry_2",
                    "animation_shot_registry_valid_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "animation_shots.selected_render_asset_id must point to selected render asset"
            ),
        ):
            conn.execute(
                """
                UPDATE animation_shots
                SET selected_render_asset_id = ?
                WHERE id = ?
                """,
                (
                    "comic_asset_animation_shot_registry_6",
                    "animation_shot_registry_valid_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "comic_scene_panels.episode_scene_id would invalidate animation_shots lineage"
            ),
        ):
            conn.execute(
                """
                UPDATE comic_scene_panels
                SET episode_scene_id = ?
                WHERE id = ?
                """,
                (
                    "comic_scene_animation_shot_registry_3",
                    "comic_panel_animation_shot_registry_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "comic_episode_scenes.episode_id would invalidate animation_shots lineage"
            ),
        ):
            conn.execute(
                """
                UPDATE comic_episode_scenes
                SET episode_id = ?
                WHERE id = ?
                """,
                (
                    episode_two.id,
                    "comic_scene_animation_shot_registry_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "comic_panel_render_assets.scene_panel_id would invalidate animation_shots lineage"
            ),
        ):
            conn.execute(
                """
                UPDATE comic_panel_render_assets
                SET scene_panel_id = ?
                WHERE id = ?
                """,
                (
                    "comic_panel_animation_shot_registry_3",
                    "comic_asset_animation_shot_registry_1",
                ),
            )
            conn.commit()

        with pytest.raises(
            (sqlite3.IntegrityError, sqlite3.OperationalError),
            match=re.escape(
                "comic_panel_render_assets.generation_id would invalidate animation_shots lineage"
            ),
        ):
            conn.execute(
                """
                UPDATE comic_panel_render_assets
                SET generation_id = ?
                WHERE id = ?
                """,
                (
                    "gen-ready-2",
                    "comic_asset_animation_shot_registry_1",
                ),
            )
            conn.commit()

        conn.execute("DELETE FROM generations WHERE id = ?", ("gen-ready-1",))
        conn.commit()

        shot_generation = conn.execute(
            """
            SELECT generation_id
            FROM animation_shots
            WHERE id = ?
            """,
            ("animation_shot_registry_valid_1",),
        ).fetchone()
        asset_generation = conn.execute(
            """
            SELECT generation_id
            FROM comic_panel_render_assets
            WHERE id = ?
            """,
            ("comic_asset_animation_shot_registry_1",),
        ).fetchone()
        assert shot_generation is not None
        assert asset_generation is not None
        assert shot_generation[0] is None
        assert asset_generation[0] is None


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
