from __future__ import annotations

import sqlite3

import pytest
from PIL import Image

from app.config import settings
from app.models import ComicEpisodeCreate
from app.services.comic_page_assembly_service import assemble_episode_pages
from app.services.comic_repository import (
    create_comic_episode,
    get_comic_episode_detail,
    list_comic_character_versions,
)


def _now() -> str:
    return "2026-04-04T00:00:00+00:00"


async def _seed_episode_with_page_panels(temp_db) -> str:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="After Hours Entry",
            synopsis="Kaede runs into a private after-hours invitation.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_repo_page_round_trip",
    )

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        repo_asset_path = settings.IMAGES_DIR / "repo-page-asset.png"
        Image.new("RGB", (64, 64), "#cf4a7d").save(repo_asset_path, format="PNG")
        repo_asset_rel = repo_asset_path.resolve().relative_to(settings.DATA_DIR.resolve()).as_posix()
        conn.execute(
            """
            INSERT INTO comic_episode_scenes (
                id,
                episode_id,
                scene_no,
                premise,
                location_label,
                continuity_notes,
                involved_character_ids,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comic_scene_repo_page_round_trip",
                episode.id,
                1,
                "Kaede studies the invitation.",
                "Private Lounge",
                "Stay restrained and intimate.",
                '["char_kaede_ren"]',
                _now(),
                _now(),
            ),
        )
        for panel_no in range(1, 3):
            conn.execute(
                """
                INSERT INTO comic_scene_panels (
                    id,
                    episode_scene_id,
                    panel_no,
                    panel_type,
                    framing,
                    camera_intent,
                    action_intent,
                    expression_intent,
                    dialogue_intent,
                    continuity_lock,
                    page_target_hint,
                    reading_order,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"comic_panel_repo_page_round_trip_{panel_no}",
                    "comic_scene_repo_page_round_trip",
                    panel_no,
                    "beat",
                    f"framing {panel_no}",
                    "slightly low camera",
                    f"Action {panel_no}",
                    f"Expression {panel_no}",
                    f"Dialogue intent {panel_no}",
                    "Stay on brand.",
                    1,
                    panel_no,
                    _now(),
                    _now(),
                ),
            )
            conn.execute(
                """
                INSERT INTO comic_panel_render_assets (
                    id,
                    scene_panel_id,
                    generation_id,
                    asset_role,
                    storage_path,
                    prompt_snapshot,
                    quality_score,
                    bubble_safe_zones,
                    crop_metadata,
                    render_notes,
                    is_selected,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"comic_panel_repo_page_asset_{panel_no}",
                    f"comic_panel_repo_page_round_trip_{panel_no}",
                    "gen-ready-1",
                    "selected",
                    repo_asset_rel,
                    '{"prompt":"repo-page-asset"}',
                    0.91,
                    "[]",
                    '{"crop_mode":"fit"}',
                    "Selected for repository page assembly test.",
                    1,
                    _now(),
                    _now(),
                ),
            )
        conn.commit()

    return episode.id


@pytest.mark.asyncio
async def test_create_comic_episode_and_fetch_detail_returns_empty_scenes_and_pages(
    temp_db,
) -> None:
    payload = ComicEpisodeCreate(
        character_id="char_kaede_ren",
        character_version_id="charver_kaede_ren_still_v1",
        title="After Hours Entry",
        synopsis="Kaede runs into a private after-hours invitation.",
        target_output="oneshot_manga",
    )

    created = await create_comic_episode(payload, episode_id="comic_ep_test_1")
    detail = await get_comic_episode_detail(created.id)

    assert created.id == "comic_ep_test_1"
    assert detail is not None
    assert detail.episode.id == "comic_ep_test_1"
    assert detail.episode.character_id == "char_kaede_ren"
    assert detail.episode.character_version_id == "charver_kaede_ren_still_v1"
    assert detail.episode.title == "After Hours Entry"
    assert detail.episode.synopsis == "Kaede runs into a private after-hours invitation."
    assert detail.scenes == []
    assert detail.pages == []


@pytest.mark.asyncio
async def test_list_comic_character_versions_returns_seeded_versions(
    temp_db,
) -> None:
    versions = await list_comic_character_versions()

    kaede = next(
        version for version in versions if version.id == "charver_kaede_ren_still_v1"
    )

    assert kaede.character_id == "char_kaede_ren"
    assert kaede.version_name == "still_default_v1"
    assert kaede.purpose == "still_default"


@pytest.mark.asyncio
async def test_list_comic_character_versions_filters_by_character_id(temp_db) -> None:
    versions = await list_comic_character_versions(character_id="char_kaede_ren")

    assert versions
    assert {version.character_id for version in versions} == {"char_kaede_ren"}


@pytest.mark.asyncio
async def test_create_comic_episode_rejects_mismatched_character_and_version(
    temp_db,
) -> None:
    payload = ComicEpisodeCreate(
        character_id="char_kaede_ren",
        character_version_id="charver_imani_adebayo_still_v1",
        title="After Hours Entry",
        synopsis="Kaede runs into a private after-hours invitation.",
        target_output="oneshot_manga",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Comic character version charver_imani_adebayo_still_v1 "
            "does not belong to character char_kaede_ren"
        ),
    ):
        await create_comic_episode(payload)


@pytest.mark.asyncio
async def test_create_comic_episode_rejects_missing_character_version(temp_db) -> None:
    payload = ComicEpisodeCreate(
        character_id="char_kaede_ren",
        character_version_id="charver_missing",
        title="After Hours Entry",
        synopsis="Kaede runs into a private after-hours invitation.",
        target_output="oneshot_manga",
    )

    with pytest.raises(
        ValueError,
        match="Unknown comic character version: charver_missing",
    ):
        await create_comic_episode(payload)


@pytest.mark.asyncio
async def test_get_comic_episode_detail_round_trips_non_empty_json_backed_lists(
    temp_db,
) -> None:
    created = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="After Hours Entry",
            synopsis="Kaede runs into a private after-hours invitation.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_with_json_lists",
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
                involved_character_ids,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "scene_json_1",
                created.id,
                1,
                "Kaede enters the lounge.",
                '["char_kaede_ren","char_imani_adebayo"]',
                _now(),
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO comic_page_assemblies (
                id,
                episode_id,
                page_no,
                ordered_panel_ids,
                export_state,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "page_json_1",
                created.id,
                1,
                '["panel_a","panel_b"]',
                "draft",
                _now(),
                _now(),
            ),
        )
        conn.commit()

    detail = await get_comic_episode_detail(created.id)

    assert detail is not None
    assert detail.scenes[0].scene.involved_character_ids == [
        "char_kaede_ren",
        "char_imani_adebayo",
    ]
    assert detail.pages[0].ordered_panel_ids == ["panel_a", "panel_b"]


@pytest.mark.asyncio
async def test_get_comic_episode_detail_raises_on_malformed_json_backed_lists(
    temp_db,
) -> None:
    created = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="After Hours Entry",
            synopsis="Kaede runs into a private after-hours invitation.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_bad_json_lists",
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
                involved_character_ids,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "scene_bad_json_1",
                created.id,
                1,
                "Kaede enters the lounge.",
                '{"character_id":"char_kaede_ren"}',
                _now(),
                _now(),
            ),
        )
        conn.commit()

    with pytest.raises(ValueError, match="comic_episode_scenes.involved_character_ids"):
        await get_comic_episode_detail(created.id)


@pytest.mark.asyncio
async def test_get_comic_episode_detail_round_trips_after_page_assembly(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_page_panels(temp_db)

    await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    detail = await get_comic_episode_detail(episode_id)

    assert detail is not None
    assert len(detail.pages) == 1
    assert detail.pages[0].ordered_panel_ids == [
        "comic_panel_repo_page_round_trip_1",
        "comic_panel_repo_page_round_trip_2",
    ]
    assert isinstance(detail.pages[0].export_manifest, dict)
    assert detail.pages[0].export_manifest["panel_ids"] == [
        "comic_panel_repo_page_round_trip_1",
        "comic_panel_repo_page_round_trip_2",
    ]


@pytest.mark.asyncio
async def test_get_comic_episode_detail_includes_panel_remote_job_counts(
    temp_db,
) -> None:
    created = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="After Hours Entry",
            synopsis="Kaede runs into a private after-hours invitation.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_with_remote_job_counts",
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
                involved_character_ids,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "scene_remote_counts_1",
                created.id,
                1,
                "Kaede enters the lounge.",
                '["char_kaede_ren"]',
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
                framing,
                camera_intent,
                action_intent,
                expression_intent,
                dialogue_intent,
                continuity_lock,
                page_target_hint,
                reading_order,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "panel_remote_counts_1",
                "scene_remote_counts_1",
                1,
                "beat",
                "tight portrait",
                "eye level",
                "Kaede studies the invitation.",
                "measured curiosity",
                "Keep the line short.",
                None,
                1,
                1,
                _now(),
                _now(),
            ),
        )
        conn.executemany(
            """
            INSERT INTO generations (
                id,
                prompt,
                checkpoint,
                loras,
                seed,
                steps,
                cfg,
                width,
                height,
                sampler,
                scheduler,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "gen_remote_counts_processing",
                    "processing prompt",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    101,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "processing",
                    _now(),
                ),
                (
                    "gen_remote_counts_completed",
                    "completed prompt",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    102,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "completed",
                    _now(),
                ),
            ],
        )
        conn.executemany(
            """
            INSERT INTO comic_panel_render_assets (
                id,
                scene_panel_id,
                generation_id,
                asset_role,
                storage_path,
                prompt_snapshot,
                quality_score,
                bubble_safe_zones,
                crop_metadata,
                render_notes,
                is_selected,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "asset_remote_counts_processing",
                    "panel_remote_counts_1",
                    "gen_remote_counts_processing",
                    "candidate",
                    None,
                    '{"prompt":"processing prompt"}',
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    _now(),
                    _now(),
                ),
                (
                    "asset_remote_counts_completed",
                    "panel_remote_counts_1",
                    "gen_remote_counts_completed",
                    "candidate",
                    "images/comics/panel-remote-completed.png",
                    '{"prompt":"completed prompt"}',
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    _now(),
                    _now(),
                ),
            ],
        )
        conn.executemany(
            """
            INSERT INTO comic_render_jobs (
                id,
                scene_panel_id,
                render_asset_id,
                generation_id,
                request_index,
                source_id,
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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "job_remote_counts_processing",
                    "panel_remote_counts_1",
                    "asset_remote_counts_processing",
                    "gen_remote_counts_processing",
                    0,
                    "comic-panel-render:panel_remote_counts_1:2:remote_worker",
                    "comic_panel_still",
                    "remote_worker",
                    "default",
                    "processing",
                    '{"comic":{"scene_panel_id":"panel_remote_counts_1"}}',
                    "remote-processing",
                    "https://worker.test/jobs/remote-processing",
                    None,
                    None,
                    _now(),
                    None,
                    _now(),
                    _now(),
                ),
                (
                    "job_remote_counts_completed",
                    "panel_remote_counts_1",
                    "asset_remote_counts_completed",
                    "gen_remote_counts_completed",
                    1,
                    "comic-panel-render:panel_remote_counts_1:2:remote_worker",
                    "comic_panel_still",
                    "remote_worker",
                    "default",
                    "completed",
                    '{"comic":{"scene_panel_id":"panel_remote_counts_1"}}',
                    "remote-completed",
                    "https://worker.test/jobs/remote-completed",
                    "images/comics/panel-remote-completed.png",
                    None,
                    _now(),
                    _now(),
                    _now(),
                    _now(),
                ),
            ],
        )
        conn.commit()

    detail = await get_comic_episode_detail(created.id)

    assert detail is not None
    assert detail.scenes[0].panels[0].remote_job_count == 2
    assert detail.scenes[0].panels[0].pending_remote_job_count == 1
