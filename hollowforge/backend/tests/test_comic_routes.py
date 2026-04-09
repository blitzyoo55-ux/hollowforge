from __future__ import annotations

import asyncio
import json
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.db import get_db, init_db
from app.main import create_app
from app.models import ComicEpisodeCreate, StoryPlannerCastInput, StoryPlannerPlanRequest
from app.services.comic_repository import create_comic_episode
from app.services.generation_service import GenerationService
from app.services import comic_render_service
from app.services.story_planner_service import plan_story_episode


def _build_client(*, generation_service=None) -> TestClient:  # type: ignore[no-untyped-def]
    app = create_app(lightweight=True)
    if generation_service is not None:
        app.state.generation_service = generation_service
    return TestClient(app)


def _build_prompt_only_approved_plan():
    return plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt=(
                "Kaede Ren pauses in a private intake lounge after closing "
                "to review a sealed invitation."
            ),
            lane="adult_nsfw",
        )
    )


def _build_registry_led_approved_plan():
    return plan_story_episode(
        StoryPlannerPlanRequest(
            story_prompt=(
                "Hana Seo compares notes with a quiet messenger in the "
                "Moonlit Bathhouse corridor after closing."
            ),
            lane="adult_nsfw",
            cast=[
                StoryPlannerCastInput(
                    role="lead",
                    source_type="registry",
                    character_id="hana_seo",
                ),
                StoryPlannerCastInput(
                    role="support",
                    source_type="freeform",
                    freeform_description="quiet messenger in a dark coat",
                ),
            ],
        )
    )


def _insert_panel_fixture(temp_db) -> str:
    episode = asyncio.run(
        create_comic_episode(
            ComicEpisodeCreate(
                character_id="char_kaede_ren",
                character_version_id="charver_kaede_ren_still_v1",
                title="After Hours Entry",
                synopsis="Kaede runs into a private after-hours invitation.",
                target_output="oneshot_manga",
            ),
            episode_id="comic_ep_route_render_queue_1",
        )
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
                location_label,
                continuity_notes,
                involved_character_ids,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comic_scene_route_render_queue_1",
                episode.id,
                1,
                "Kaede studies the invitation.",
                "Private Lounge",
                "Keep the scene controlled and intimate.",
                '["char_kaede_ren"]',
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
                "comic_panel_route_render_queue_1",
                "comic_scene_route_render_queue_1",
                1,
                "beat",
                "tight waist-up portrait",
                "slightly low camera",
                "Kaede turns the invitation over in her hand.",
                "measured curiosity with a faint edge of heat",
                "Placeholder dialogue intent for queueing.",
                "Stay on brand for the character version.",
                1,
                1,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        conn.commit()

    return "comic_panel_route_render_queue_1"


def _insert_panel_with_mixed_asset_roles_fixture(temp_db) -> str:
    panel_id = _insert_panel_fixture(temp_db)

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
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
                    "gen-candidate-1",
                    "candidate 1",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    1,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "gen-derived-preview-1",
                    "derived preview 1",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    2,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "gen-final-master-1",
                    "final master 1",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    3,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "gen-candidate-2",
                    "candidate 2",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    4,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    "2026-04-04T00:00:00+00:00",
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
                    "asset-candidate-1",
                    panel_id,
                    "gen-candidate-1",
                    "candidate",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "asset-derived-preview-1",
                    panel_id,
                    "gen-derived-preview-1",
                    "derived_preview",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "asset-final-master-1",
                    panel_id,
                    "gen-final-master-1",
                    "final_master",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "asset-candidate-2",
                    panel_id,
                    "gen-candidate-2",
                    "candidate",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            ],
        )
        conn.commit()

    return panel_id


def _insert_panel_with_existing_selected_asset_fixture(temp_db) -> str:
    panel_id = _insert_panel_fixture(temp_db)

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
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
                    "gen-selected-old",
                    "selected old",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    10,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "gen-candidate-new",
                    "candidate new",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    11,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "gen-derived-preview-old",
                    "derived preview old",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    12,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    "2026-04-04T00:00:00+00:00",
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
                    "asset-selected-old",
                    panel_id,
                    "gen-selected-old",
                    "selected",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    1,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "asset-candidate-new",
                    panel_id,
                    "gen-candidate-new",
                    "candidate",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
                (
                    "asset-derived-preview-old",
                    panel_id,
                    "gen-derived-preview-old",
                    "derived_preview",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            ],
        )
        conn.commit()

    return panel_id


def _insert_panel_render_jobs_fixture(temp_db) -> str:
    panel_id = _insert_panel_fixture(temp_db)

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executemany(
            """
            INSERT INTO generations (
                id,
                prompt,
                negative_prompt,
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
                image_path,
                source_id,
                error_message,
                created_at,
                completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "gen-panel-job-old",
                    "old prompt",
                    "avoid blur",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    101,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "completed",
                    "images/comics/panel-job-old.png",
                    f"comic-panel-render:{panel_id}:2:remote_worker",
                    None,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:05:00+00:00",
                ),
                (
                    "gen-panel-job-new",
                    "new prompt",
                    "avoid blur",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    102,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "failed",
                    None,
                    f"comic-panel-render:{panel_id}:2:remote_worker",
                    "remote worker timeout",
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:06:00+00:00",
                ),
                (
                    "gen-other-panel-job",
                    "other panel prompt",
                    "avoid blur",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    103,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "submitted",
                    None,
                    "comic-panel-render:other-panel:1:remote_worker",
                    None,
                    "2026-04-04T00:00:00+00:00",
                    None,
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
                    "asset-panel-job-old",
                    panel_id,
                    "gen-panel-job-old",
                    "candidate",
                    "images/comics/panel-job-old.png",
                    '{"prompt":"old prompt"}',
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:05:00+00:00",
                ),
                (
                    "asset-panel-job-new",
                    panel_id,
                    "gen-panel-job-new",
                    "candidate",
                    None,
                    '{"prompt":"new prompt"}',
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:06:00+00:00",
                ),
            ],
        )
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
                "comic_scene_route_render_jobs_other",
                "comic_ep_route_render_queue_1",
                2,
                "Other panel context.",
                "Private Lounge",
                "Keep continuity intact.",
                '["char_kaede_ren"]',
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
                "comic_panel_route_render_jobs_other",
                "comic_scene_route_render_jobs_other",
                2,
                "beat",
                "wide panel",
                "eye level",
                "Other panel action.",
                "other expression",
                "Other dialogue intent.",
                "Stay on brand for the character version.",
                1,
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
                "asset-other-panel-job",
                "comic_panel_route_render_jobs_other",
                "gen-other-panel-job",
                "candidate",
                None,
                '{"prompt":"other panel prompt"}',
                None,
                "[]",
                None,
                None,
                0,
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:02:00+00:00",
            ),
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
                    "comic-render-job-old",
                    panel_id,
                    "asset-panel-job-old",
                    "gen-panel-job-old",
                    0,
                    f"comic-panel-render:{panel_id}:2:remote_worker",
                    "comic_panel_still",
                    "remote_worker",
                    "default",
                    "completed",
                    '{"comic":{"scene_panel_id":"comic_panel_route_render_queue_1"}}',
                    "remote-old",
                    "https://worker.test/jobs/remote-old",
                    "images/comics/panel-job-old.png",
                    None,
                    "2026-04-04T00:01:00+00:00",
                    "2026-04-04T00:05:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:05:00+00:00",
                ),
                (
                    "comic-render-job-new",
                    panel_id,
                    "asset-panel-job-new",
                    "gen-panel-job-new",
                    1,
                    f"comic-panel-render:{panel_id}:2:remote_worker",
                    "comic_panel_still",
                    "remote_worker",
                    "default",
                    "failed",
                    '{"comic":{"scene_panel_id":"comic_panel_route_render_queue_1"}}',
                    "remote-new",
                    "https://worker.test/jobs/remote-new",
                    None,
                    "remote worker timeout",
                    "2026-04-04T00:02:00+00:00",
                    "2026-04-04T00:06:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:06:00+00:00",
                ),
                (
                    "comic-render-job-other",
                    "comic_panel_route_render_jobs_other",
                    "asset-other-panel-job",
                    "gen-other-panel-job",
                    0,
                    "comic-panel-render:other-panel:1:remote_worker",
                    "comic_panel_still",
                    "remote_worker",
                    "default",
                    "submitted",
                    '{"comic":{"scene_panel_id":"comic_panel_route_render_jobs_other"}}',
                    "remote-other",
                    "https://worker.test/jobs/remote-other",
                    None,
                    None,
                    "2026-04-04T00:02:30+00:00",
                    None,
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:02:30+00:00",
                ),
            ],
        )
        conn.commit()

    return panel_id


@pytest.mark.asyncio
async def test_comic_remote_render_jobs_table_exists(temp_db) -> None:
    await init_db()

    async with get_db() as db:
        cursor = await db.execute("PRAGMA table_info(comic_render_jobs)")
        rows = await cursor.fetchall()

    columns = {row["name"] for row in rows}

    assert {"id", "scene_panel_id", "render_asset_id", "generation_id", "status"} <= columns


def _insert_episode_with_page_panels_fixture(
    temp_db,
    *,
    panel_count: int = 5,
    include_selected_assets: bool = True,
) -> str:
    episode = asyncio.run(
        create_comic_episode(
            ComicEpisodeCreate(
                character_id="char_kaede_ren",
                character_version_id="charver_kaede_ren_still_v1",
                title="After Hours Entry",
                synopsis="Kaede studies a sealed invitation after closing.",
                target_output="oneshot_manga",
            ),
            episode_id="comic_ep_route_pages_1",
        )
    )

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        route_asset_path = settings.IMAGES_DIR / "route-page-asset.png"
        Image.new("RGB", (64, 64), "#2f7ae5").save(route_asset_path, format="PNG")
        route_asset_rel = route_asset_path.resolve().relative_to(settings.DATA_DIR.resolve()).as_posix()
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
                "comic_scene_route_pages_1",
                episode.id,
                1,
                "Kaede studies the invitation.",
                "Private Lounge",
                "Stay restrained and intimate.",
                '["char_kaede_ren"]',
                "2026-04-04T00:00:00+00:00",
                "2026-04-04T00:00:00+00:00",
            ),
        )
        for index in range(panel_count):
            panel_no = index + 1
            panel_id = f"comic_panel_route_pages_1_{panel_no}"
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
                    panel_id,
                    "comic_scene_route_pages_1",
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
                    "2026-04-04T00:00:00+00:00",
                    "2026-04-04T00:00:00+00:00",
                ),
            )
            if include_selected_assets:
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
                        f"asset-route-pages-{panel_no}",
                        panel_id,
                        "gen-ready-1",
                        "selected",
                        route_asset_rel,
                        '{"prompt":"page-asset"}',
                        0.92,
                        "[]",
                        '{"crop_mode":"fit"}',
                        "Selected for page assembly route test.",
                        1,
                        "2026-04-04T00:00:00+00:00",
                        "2026-04-04T00:00:00+00:00",
                    ),
                )
        conn.commit()

    return episode.id


class _StubGenerationService:
    def __init__(self, db_path) -> None:
        self._db_path = db_path

    async def queue_generation_batch(  # type: ignore[no-untyped-def]
        self,
        generation,
        count: int,
        seed_increment: int = 1,
    ):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            for index in range(count):
                queued_generation_id = f"queued-generation-{index + 1}"
                conn.execute(
                    """
                    INSERT INTO generations (
                        id,
                        prompt,
                        negative_prompt,
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
                        source_id,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        queued_generation_id,
                        generation.prompt,
                        generation.negative_prompt,
                        generation.checkpoint,
                        json.dumps(generation.model_dump()["loras"]),
                        100 + index,
                        generation.steps,
                        generation.cfg,
                        generation.width,
                        generation.height,
                        generation.sampler,
                        generation.scheduler,
                        "queued",
                        generation.source_id,
                        "2026-04-04T00:00:00+00:00",
                    ),
                )
            conn.commit()
        return 100, [
            SimpleNamespace(id=f"queued-generation-{index + 1}")
            for index in range(count)
        ]


def test_get_comic_characters_returns_seeded_character(temp_db) -> None:
    client = _build_client()

    response = client.get("/api/v1/comic/characters")

    assert response.status_code == 200
    body = response.json()
    kaede = next(character for character in body if character["id"] == "char_kaede_ren")
    assert kaede["slug"] == "kaede_ren"
    assert kaede["name"] == "Kaede Ren"


def test_get_comic_character_versions_returns_seeded_version(temp_db) -> None:
    client = _build_client()

    response = client.get("/api/v1/comic/character-versions")

    assert response.status_code == 200
    body = response.json()
    kaede = next(
        version for version in body if version["id"] == "charver_kaede_ren_still_v1"
    )
    assert kaede["character_id"] == "char_kaede_ren"
    assert kaede["version_name"] == "still_default_v1"
    assert kaede["purpose"] == "still_default"


def test_post_comic_episode_returns_201_with_empty_scenes_and_pages(temp_db) -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/comic/episodes",
        json={
            "character_id": "char_kaede_ren",
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "After Hours Entry",
            "synopsis": "Kaede runs into a private after-hours invitation.",
            "target_output": "oneshot_manga",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["episode"]["character_id"] == "char_kaede_ren"
    assert body["episode"]["character_version_id"] == "charver_kaede_ren_still_v1"
    assert body["episode"]["title"] == "After Hours Entry"
    assert body["scenes"] == []
    assert body["pages"] == []


def test_post_comic_episode_persists_explicit_v2_episode_fields(temp_db) -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/comic/episodes",
        json={
            "character_id": "char_camila_duarte",
            "character_version_id": "charver_camila_duarte_still_v1",
            "title": "Camila V2 Create",
            "synopsis": "Explicit V2 metadata should persist from create endpoint.",
            "target_output": "oneshot_manga",
            "render_lane": "character_canon_v2",
            "series_style_id": "camila_pilot_v1",
            "character_series_binding_id": "camila_pilot_binding_v1",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["episode"]["render_lane"] == "character_canon_v2"
    assert body["episode"]["series_style_id"] == "camila_pilot_v1"
    assert body["episode"]["character_series_binding_id"] == "camila_pilot_binding_v1"


def test_post_comic_episode_rejects_explicit_v2_for_non_camila_character(temp_db) -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/comic/episodes",
        json={
            "character_id": "char_kaede_ren",
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "Kaede V2 Rejected",
            "synopsis": "Only Camila should be allowed on explicit V2 lane.",
            "target_output": "oneshot_manga",
            "render_lane": "character_canon_v2",
            "series_style_id": "camila_pilot_v1",
            "character_series_binding_id": "camila_pilot_binding_v1",
        },
    )

    assert response.status_code == 400
    assert "Camila Duarte" in response.json()["detail"]


def test_get_comic_episode_detail_returns_created_episode(temp_db) -> None:
    created = asyncio.run(
        create_comic_episode(
            ComicEpisodeCreate(
                character_id="char_kaede_ren",
                character_version_id="charver_kaede_ren_still_v1",
                title="After Hours Entry",
                synopsis="Kaede runs into a private after-hours invitation.",
                target_output="oneshot_manga",
            ),
            episode_id="comic_ep_route_detail",
        )
    )
    client = _build_client()

    response = client.get(f"/api/v1/comic/episodes/{created.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["episode"]["id"] == "comic_ep_route_detail"
    assert body["episode"]["title"] == "After Hours Entry"
    assert body["scenes"] == []
    assert body["pages"] == []


def test_get_comic_episode_detail_includes_panel_remote_job_counts(temp_db) -> None:
    _insert_panel_render_jobs_fixture(temp_db)
    client = _build_client()

    response = client.get("/api/v1/comic/episodes/comic_ep_route_render_queue_1")

    assert response.status_code == 200
    body = response.json()

    scene_one_panel = body["scenes"][0]["panels"][0]
    assert scene_one_panel["id"] == "comic_panel_route_render_queue_1"
    assert scene_one_panel["remote_job_count"] == 2
    assert scene_one_panel["pending_remote_job_count"] == 0

    scene_two_panel = body["scenes"][1]["panels"][0]
    assert scene_two_panel["id"] == "comic_panel_route_render_jobs_other"
    assert scene_two_panel["remote_job_count"] == 1
    assert scene_two_panel["pending_remote_job_count"] == 1


def test_get_comic_episodes_lists_created_episode(temp_db) -> None:
    asyncio.run(
        create_comic_episode(
            ComicEpisodeCreate(
                character_id="char_kaede_ren",
                character_version_id="charver_kaede_ren_still_v1",
                title="After Hours Entry",
                synopsis="Kaede runs into a private after-hours invitation.",
                target_output="oneshot_manga",
            ),
            episode_id="comic_ep_route_list",
        )
    )
    client = _build_client()

    response = client.get("/api/v1/comic/episodes")

    assert response.status_code == 200
    body = response.json()
    episode_summary = next(
        item for item in body if item["episode"]["id"] == "comic_ep_route_list"
    )
    assert episode_summary["episode"]["character_id"] == "char_kaede_ren"
    assert episode_summary["scene_count"] == 0
    assert episode_summary["page_count"] == 0


def test_get_missing_comic_episode_returns_404(temp_db) -> None:
    client = _build_client()

    response = client.get("/api/v1/comic/episodes/missing-episode")

    assert response.status_code == 404
    assert response.json() == {"detail": "Comic episode not found"}


def test_queue_comic_panel_renders_accepts_remote_execution_mode(temp_db, monkeypatch) -> None:
    panel_id = _insert_panel_fixture(temp_db)
    app = create_app(lightweight=True)
    app.state.generation_service = GenerationService()
    client = TestClient(app)

    async def _fake_dispatch(job, generation, render_asset, panel_context):  # type: ignore[no-untyped-def]
        return {
            "id": f"remote-job-{job['request_index']}",
            "job_id": f"remote-job-{job['request_index']}",
            "job_url": f"https://worker.test/jobs/{job['id']}",
        }

    monkeypatch.setattr(
        comic_render_service,
        "dispatch_comic_render_job",
        _fake_dispatch,
    )

    response = client.post(
        f"/api/v1/comic/panels/{panel_id}/queue-renders",
        params={"candidate_count": 3, "execution_mode": "remote_worker"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["execution_mode"] == "remote_worker"
    assert body["requested_count"] == 3
    assert body["queued_generation_count"] == 3
    assert body["materialized_asset_count"] == 0
    assert body["pending_render_job_count"] == 3
    assert body["remote_job_count"] == 3
    assert len(body["render_assets"]) == 3
    assert all(asset["storage_path"] is None for asset in body["render_assets"])

    with sqlite3.connect(temp_db) as conn:
        generation_count = conn.execute(
            "SELECT COUNT(*) FROM generations WHERE source_id LIKE ?",
            (f"comic-panel-render:{panel_id}:3:remote_worker%",),
        ).fetchone()[0]
        asset_count = conn.execute(
            "SELECT COUNT(*) FROM comic_panel_render_assets WHERE scene_panel_id = ?",
            (panel_id,),
        ).fetchone()[0]
        job_count = conn.execute(
            "SELECT COUNT(*) FROM comic_render_jobs WHERE scene_panel_id = ?",
            (panel_id,),
        ).fetchone()[0]

    assert generation_count == 3
    assert asset_count == 3
    assert job_count == 3


def test_get_panel_render_jobs_lists_jobs_newest_first(temp_db) -> None:
    panel_id = _insert_panel_render_jobs_fixture(temp_db)
    client = _build_client()

    response = client.get(f"/api/v1/comic/panels/{panel_id}/render-jobs")

    assert response.status_code == 200
    body = response.json()
    assert [job["id"] for job in body] == [
        "comic-render-job-new",
        "comic-render-job-old",
    ]
    assert body[0]["status"] == "failed"
    assert body[0]["external_job_url"] == "https://worker.test/jobs/remote-new"
    assert body[0]["output_path"] is None
    assert body[0]["error_message"] == "remote worker timeout"
    assert body[1]["status"] == "completed"
    assert body[1]["output_path"] == "images/comics/panel-job-old.png"


def test_get_panel_render_jobs_returns_404_for_unknown_panel(temp_db) -> None:
    client = _build_client()

    response = client.get("/api/v1/comic/panels/missing-panel/render-jobs")

    assert response.status_code == 404
    assert response.json() == {"detail": "Comic panel not found: missing-panel"}


def test_post_comic_episode_rejects_mismatched_character_and_version(temp_db) -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/comic/episodes",
        json={
            "character_id": "char_kaede_ren",
            "character_version_id": "charver_imani_adebayo_still_v1",
            "title": "After Hours Entry",
            "synopsis": "Kaede runs into a private after-hours invitation.",
            "target_output": "oneshot_manga",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": (
            "Comic character version charver_imani_adebayo_still_v1 "
            "does not belong to character char_kaede_ren"
        )
    }


def test_post_comic_episode_rejects_missing_character_version(temp_db) -> None:
    client = _build_client()

    response = client.post(
        "/api/v1/comic/episodes",
        json={
            "character_id": "char_kaede_ren",
            "character_version_id": "charver_missing",
            "title": "After Hours Entry",
            "synopsis": "Kaede runs into a private after-hours invitation.",
            "target_output": "oneshot_manga",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Unknown comic character version: charver_missing"
    }


def test_import_story_plan_route_persists_episode(temp_db) -> None:
    client = _build_client()
    approved_plan = _build_prompt_only_approved_plan()

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan.model_dump(mode="json"),
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "Night Intake",
            "panel_multiplier": 2,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["episode"]["title"] == "Night Intake"
    assert body["episode"]["character_id"] == "char_kaede_ren"
    assert body["episode"]["character_version_id"] == "charver_kaede_ren_still_v1"


def test_import_story_plan_route_persists_explicit_v2_episode_fields(temp_db) -> None:
    client = _build_client()
    approved_plan = _build_prompt_only_approved_plan()

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan.model_dump(mode="json"),
            "character_version_id": "charver_camila_duarte_still_v1",
            "title": "Camila Pilot Intake",
            "panel_multiplier": 2,
            "render_lane": "character_canon_v2",
            "series_style_id": "camila_pilot_v1",
            "character_series_binding_id": "camila_pilot_binding_v1",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["episode"]["render_lane"] == "character_canon_v2"
    assert body["episode"]["series_style_id"] == "camila_pilot_v1"
    assert body["episode"]["character_series_binding_id"] == "camila_pilot_binding_v1"


def test_import_story_plan_route_rejects_explicit_v2_missing_required_fields(
    temp_db,
) -> None:
    client = _build_client()
    approved_plan = _build_prompt_only_approved_plan()

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan.model_dump(mode="json"),
            "character_version_id": "charver_camila_duarte_still_v1",
            "title": "Camila V2 Missing Style",
            "render_lane": "character_canon_v2",
            "character_series_binding_id": "camila_pilot_binding_v1",
        },
    )

    assert response.status_code == 422
    assert "requires series_style_id" in response.text


def test_import_story_plan_route_rejects_explicit_v2_for_non_camila_character(
    temp_db,
) -> None:
    client = _build_client()
    approved_plan = _build_prompt_only_approved_plan()

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan.model_dump(mode="json"),
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "Kaede V2 Rejected",
            "render_lane": "character_canon_v2",
            "series_style_id": "camila_pilot_v1",
            "character_series_binding_id": "camila_pilot_binding_v1",
        },
    )

    assert response.status_code == 400
    assert "Camila Duarte" in response.json()["detail"]


def test_import_story_plan_route_rejects_binding_style_mismatch_for_explicit_v2(
    temp_db,
) -> None:
    client = _build_client()
    approved_plan = _build_prompt_only_approved_plan()

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan.model_dump(mode="json"),
            "character_version_id": "charver_camila_duarte_still_v1",
            "title": "Camila V2 Binding Mismatch",
            "render_lane": "character_canon_v2",
            "series_style_id": "camila_motion_test_v1",
            "character_series_binding_id": "camila_pilot_binding_v1",
        },
    )

    assert response.status_code == 400
    assert "does not match series style" in response.json()["detail"]


def test_import_story_plan_route_returns_four_scenes_and_two_panels_per_scene(
    temp_db,
) -> None:
    client = _build_client()
    approved_plan = _build_prompt_only_approved_plan()

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan.model_dump(mode="json"),
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "Night Intake",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["scenes"]) == 4
    assert all(len(scene["panels"]) == 2 for scene in body["scenes"])
    assert all(
        scene["scene"]["involved_character_ids"] == ["char_kaede_ren"]
        for scene in body["scenes"]
    )


def test_import_story_plan_route_persists_source_story_plan_json(temp_db) -> None:
    client = _build_client()
    approved_plan = _build_prompt_only_approved_plan()

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan.model_dump(mode="json"),
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "Night Intake",
        },
    )

    assert response.status_code == 201
    stored_plan = json.loads(response.json()["episode"]["source_story_plan_json"])
    assert stored_plan["approval_token"] == approved_plan.approval_token
    assert len(stored_plan["shots"]) == 4


def test_import_story_plan_route_rejects_invalid_approval_token(temp_db) -> None:
    client = _build_client()
    approved_plan = _build_prompt_only_approved_plan().model_dump(mode="json")
    approved_plan["approval_token"] = "0" * 64

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan,
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "Night Intake",
        },
    )

    assert response.status_code == 400
    assert "approval_token" in response.json()["detail"]


def test_import_story_plan_route_rejects_registry_lead_that_conflicts_with_selected_version(
    temp_db,
) -> None:
    client = _build_client()
    approved_plan = _build_registry_led_approved_plan()

    response = client.post(
        "/api/v1/comic/episodes/import-story-plan",
        json={
            "approved_plan": approved_plan.model_dump(mode="json"),
            "character_version_id": "charver_kaede_ren_still_v1",
            "title": "Night Intake",
        },
    )

    assert response.status_code == 400
    assert "conflicts" in response.json()["detail"]
    assert "hana_seo" in response.json()["detail"]


def test_queue_and_select_panel_render_assets_keep_one_selected_asset_per_panel(
    temp_db,
) -> None:
    panel_id = _insert_panel_fixture(temp_db)
    app = create_app(lightweight=True)
    app.state.generation_service = _StubGenerationService(temp_db)
    client = TestClient(app)

    queue_response = client.post(
        f"/api/v1/comic/panels/{panel_id}/queue-renders",
        params={"candidate_count": 3, "execution_mode": "local_preview"},
    )

    assert queue_response.status_code == 200
    queue_body = queue_response.json()
    assert queue_body["execution_mode"] == "local_preview"
    assert queue_body["requested_count"] == 3
    assert queue_body["queued_generation_count"] == 3
    assert queue_body["materialized_asset_count"] == 3
    assert queue_body["pending_render_job_count"] == 0
    assert queue_body["remote_job_count"] == 0
    assert len(queue_body["render_assets"]) == 3

    first_asset_id = queue_body["render_assets"][0]["id"]
    second_asset_id = queue_body["render_assets"][1]["id"]

    first_select_response = client.post(
        f"/api/v1/comic/panels/{panel_id}/assets/{first_asset_id}/select"
    )
    assert first_select_response.status_code == 200
    assert first_select_response.json()["is_selected"] is True

    second_select_response = client.post(
        f"/api/v1/comic/panels/{panel_id}/assets/{second_asset_id}/select"
    )
    assert second_select_response.status_code == 200
    assert second_select_response.json()["is_selected"] is True

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """
            SELECT id, is_selected
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (panel_id,),
        ).fetchall()

    assert sum(row[1] for row in rows) == 1
    assert {row[0] for row in rows if row[1]} == {second_asset_id}


def test_select_panel_render_asset_preserves_non_selected_sibling_roles(
    temp_db,
) -> None:
    panel_id = _insert_panel_with_mixed_asset_roles_fixture(temp_db)
    app = create_app(lightweight=True)
    client = TestClient(app)

    response = client.post(
        f"/api/v1/comic/panels/{panel_id}/assets/asset-candidate-2/select"
    )

    assert response.status_code == 200
    assert response.json()["asset_role"] == "selected"

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """
            SELECT id, asset_role, is_selected
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY id ASC
            """,
            (panel_id,),
        ).fetchall()

    assert rows == [
        ("asset-candidate-1", "candidate", 0),
        ("asset-candidate-2", "selected", 1),
        ("asset-derived-preview-1", "derived_preview", 0),
        ("asset-final-master-1", "final_master", 0),
    ]


def test_select_panel_render_asset_demotes_previous_selected_sibling_to_candidate(
    temp_db,
) -> None:
    panel_id = _insert_panel_with_existing_selected_asset_fixture(temp_db)
    app = create_app(lightweight=True)
    client = TestClient(app)

    response = client.post(
        f"/api/v1/comic/panels/{panel_id}/assets/asset-candidate-new/select"
    )

    assert response.status_code == 200
    assert response.json()["asset_role"] == "selected"

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """
            SELECT id, asset_role, is_selected
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY id ASC
            """,
            (panel_id,),
        ).fetchall()

    assert rows == [
        ("asset-candidate-new", "selected", 1),
        ("asset-derived-preview-old", "derived_preview", 0),
        ("asset-selected-old", "candidate", 0),
    ]


def test_post_comic_panel_dialogue_generation_route_returns_dialogue_rows(
    temp_db, monkeypatch
) -> None:
    panel_id = _insert_panel_fixture(temp_db)
    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads",
        lambda **_: [
            {
                "type": "speech",
                "speaker_character_id": "char_kaede_ren",
                "text": "I know what this invitation means.",
                "tone": "measured",
                "priority": 10,
                "balloon_style_hint": "rounded",
                "placement_hint": "upper left",
            },
            {
                "type": "caption",
                "speaker_character_id": None,
                "text": "The lounge stays quiet after closing.",
                "tone": "observational",
                "priority": 20,
                "balloon_style_hint": None,
                "placement_hint": "top edge",
            },
            {
                "type": "sfx",
                "speaker_character_id": None,
                "text": "tap",
                "tone": "soft",
                "priority": 30,
                "balloon_style_hint": None,
                "placement_hint": "near hand",
            },
        ],
    )
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/panels/{panel_id}/dialogues/generate"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["generated_count"] == 3
    assert [dialogue["type"] for dialogue in body["dialogues"]] == [
        "speech",
        "caption",
        "sfx",
    ]

    with sqlite3.connect(temp_db) as conn:
        row_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM comic_panel_dialogues
            WHERE scene_panel_id = ?
            """,
            (panel_id,),
        ).fetchone()[0]

    assert row_count == 3


def test_post_comic_episode_page_assembly_route_returns_pages_and_manifest(
    temp_db,
) -> None:
    episode_id = _insert_episode_with_page_panels_fixture(temp_db, panel_count=5)
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/episodes/{episode_id}/pages/assemble"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["layout_template_id"] == "jp_2x2_v1"
    assert len(body["pages"]) == 2
    assert body["export_manifest_path"].endswith(".json")
    assert body["teaser_handoff_manifest_path"].endswith(".json")
    assert (settings.DATA_DIR / body["export_manifest_path"]).is_file()
    assert (settings.DATA_DIR / body["pages"][0]["preview_path"]).is_file()


def test_post_comic_episode_page_export_route_returns_zip_and_artifacts(
    temp_db,
) -> None:
    episode_id = _insert_episode_with_page_panels_fixture(temp_db, panel_count=5)
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/episodes/{episode_id}/pages/export"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["export_zip_path"].endswith(".zip")
    assert body["page_assembly_manifest_path"].endswith(".json")
    assert body["dialogue_json_path"].endswith(".json")
    assert body["panel_asset_manifest_path"].endswith(".json")
    assert body["teaser_handoff_manifest_path"].endswith(".json")
    assert all(page["export_state"] == "exported" for page in body["pages"])
    assert (settings.DATA_DIR / body["export_zip_path"]).is_file()


def test_export_route_accepts_manuscript_profile_id(temp_db) -> None:
    episode_id = _insert_episode_with_page_panels_fixture(temp_db, panel_count=2)
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/episodes/{episode_id}/pages/export",
        params={
            "layout_template_id": "jp_2x2_v1",
            "manuscript_profile_id": "jp_manga_rightbound_v1",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["manuscript_profile"]["id"] == "jp_manga_rightbound_v1"
    assert body["manuscript_profile_manifest_path"].endswith("_manuscript_profile.json")
    assert body["handoff_readme_path"].endswith("_handoff_readme.md")
    assert body["production_checklist_path"].endswith("_production_checklist.json")


def test_post_comic_episode_page_assembly_route_rejects_missing_selected_assets(
    temp_db,
) -> None:
    episode_id = _insert_episode_with_page_panels_fixture(
        temp_db,
        panel_count=2,
        include_selected_assets=False,
    )
    client = _build_client()

    response = client.post(
        f"/api/v1/comic/episodes/{episode_id}/pages/assemble"
    )

    assert response.status_code == 400
    assert "requires a selected render asset for every panel" in response.json()["detail"]


def test_list_comic_manuscript_profiles() -> None:
    client = _build_client()

    response = client.get("/api/v1/comic/manuscript-profiles")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": "jp_manga_rightbound_v1",
            "label": "Japanese Manga Right-Bound v1",
            "binding_direction": "right_to_left",
            "finishing_tool": "clip_studio_ex",
            "print_intent": "japanese_manga",
            "trim_reference": "B5 monochrome manga manuscript preset",
            "bleed_reference": "CLIP STUDIO EX Japanese comic print bleed preset",
            "safe_area_reference": "CLIP STUDIO EX default inner safe area guide",
            "naming_pattern": "page_{page_no:03d}.tif",
        }
    ]
