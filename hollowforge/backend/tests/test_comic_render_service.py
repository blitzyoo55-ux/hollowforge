from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import (
    AnimationJobCallbackPayload,
    ComicEpisodeCreate,
    ComicPanelRenderQueueResponse,
    StoryPlannerCatalog,
    StoryPlannerLocationCatalogEntry,
)
from app.services.comic_repository import create_comic_episode
from app.services import comic_render_service
from app.services.comic_render_service import (
    materialize_remote_render_job_callback,
    queue_panel_render_candidates,
)
from app.services.comic_render_dispatch_service import ComicRenderDispatchError
from app.services.generation_service import GenerationService

pytestmark = pytest.mark.asyncio


def _now() -> str:
    return "2026-04-04T00:00:00+00:00"


def _panel_render_source_id(
    panel_id: str,
    candidate_count: int,
    execution_mode: str,
    *,
    panel_type: str = "beat",
) -> str:
    profile = comic_render_service.resolve_comic_panel_render_profile(
        {"panel_type": panel_type}
    )
    return comic_render_service._render_request_source_id(
        panel_id,
        candidate_count,
        execution_mode,
        comic_render_service._profile_signature(profile),
    )


async def _create_panel_fixture(
    temp_db: Path,
    *,
    panel_type: str = "beat",
    panel_id: str = "comic_panel_render_queue_1",
    scene_id: str = "comic_scene_render_queue_1",
    location_label: str = "Private Lounge",
) -> str:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="After Hours Entry",
            synopsis="Kaede runs into a private after-hours invitation.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_render_queue_1",
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
                scene_id,
                episode.id,
                1,
                "Kaede studies the invitation.",
                location_label,
                "Keep the scene controlled and intimate.",
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
                panel_id,
                scene_id,
                1,
                panel_type,
                "tight waist-up portrait",
                "slightly low camera",
                "Kaede turns the invitation over in her hand.",
                "measured curiosity with a faint edge of heat",
                "Placeholder dialogue intent for queueing.",
                "Stay on brand for the character version.",
                1,
                1,
                _now(),
                _now(),
            ),
        )
        conn.commit()

    return panel_id


class _StubGenerationService:
    def __init__(self, db_path: Path, *, generation_id_prefix: str = "") -> None:
        self._db_path = db_path
        self._generation_id_prefix = generation_id_prefix
        self.batch_calls: list[tuple[dict[str, object], int, int]] = []
        self._batches: dict[tuple[object, ...], list[SimpleNamespace]] = {}

    async def queue_generation_batch(  # type: ignore[no-untyped-def]
        self,
        generation,
        count: int,
        seed_increment: int = 1,
    ):
        payload = generation.model_dump()
        self.batch_calls.append((payload, count, seed_increment))
        batch_key = (
            payload["prompt"],
            payload["checkpoint"],
            payload["negative_prompt"],
            json.dumps(payload["loras"], sort_keys=True),
            count,
            seed_increment,
        )
        existing_batch = self._batches.get(batch_key)
        if existing_batch is not None:
            return 100, existing_batch

        batch = [
            SimpleNamespace(
                id=f"{self._generation_id_prefix}queued-generation-{index + 1}"
            )
            for index in range(count)
        ]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            for index in range(count):
                queued_generation_id = (
                    f"{self._generation_id_prefix}queued-generation-{index + 1}"
                )
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
                        payload["source_id"],
                        _now(),
                    ),
                )
            conn.commit()
        self._batches[batch_key] = batch
        return 100, batch


async def test_queue_panel_render_candidates_uses_character_version_defaults_and_snapshots(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    generation_service = _StubGenerationService(temp_db)
    source_id = _panel_render_source_id(panel_id, 3, "local_preview")

    result = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="local_preview",
    )

    assert isinstance(result, ComicPanelRenderQueueResponse)
    assert result.execution_mode == "local_preview"
    assert result.requested_count == 3
    assert result.queued_generation_count == 3
    assert result.materialized_asset_count == 3
    assert result.pending_render_job_count == 0
    assert result.remote_job_count == 0
    assert [asset.generation_id for asset in result.render_assets] == [
        "queued-generation-1",
        "queued-generation-2",
        "queued-generation-3",
    ]

    assert len(generation_service.batch_calls) == 1
    generation_payload, count, seed_increment = generation_service.batch_calls[0]
    assert count == 3
    assert seed_increment == 1
    assert generation_payload["prompt"] == (
        "masterpiece, best quality, original character, adult woman, solo, "
        "fully clothed, tasteful adult allure, Kaede Ren, elegant east asian "
        "beauty, sleek black bob, cool brown eyes, porcelain skin, slim toned "
        "figure. "
        "Setting: inside Private Lounge. "
        "Action: Kaede turns the invitation over in her hand. "
        "Emotion: measured curiosity with a faint edge of heat. "
        "Composition: beat manga panel, subject and prop both readable in frame, "
        "slightly low camera, tight waist-up portrait. "
        "Continuity: Keep the scene controlled and intimate. Stay on brand for the character version."
    )
    assert generation_payload["negative_prompt"] == (
        "child, teen, underage, school uniform, text, logo, watermark, blurry, "
        "lowres, deformed, bad anatomy, extra fingers, duplicate, poorly drawn "
        "hands, explicit nudity, graphic sexual content"
    )
    assert generation_payload["checkpoint"] == "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors"
    assert generation_payload["workflow_lane"] == "sdxl_illustrious"
    assert generation_payload["steps"] == 34
    assert generation_payload["cfg"] == 5.5
    assert generation_payload["width"] == 960
    assert generation_payload["height"] == 1216
    assert generation_payload["sampler"] == "euler_ancestral"
    assert generation_payload["scheduler"] == "normal"
    assert generation_payload["clip_skip"] == 2
    assert len(generation_payload["loras"]) == 2
    assert generation_payload["source_id"] == source_id

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """
            SELECT generation_id, asset_role, is_selected, prompt_snapshot
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (panel_id,),
        ).fetchall()

    assert [row[0] for row in rows] == [
        "queued-generation-1",
        "queued-generation-2",
        "queued-generation-3",
    ]
    assert [row[1] for row in rows] == ["candidate", "candidate", "candidate"]
    assert [row[2] for row in rows] == [0, 0, 0]
    prompt_snapshot = json.loads(rows[0][3])
    assert prompt_snapshot == {
        "prompt": generation_payload["prompt"],
        "negative_prompt": generation_payload["negative_prompt"],
        "checkpoint": generation_payload["checkpoint"],
    }

    with sqlite3.connect(temp_db) as conn:
        generation_source_id = conn.execute(
            """
            SELECT source_id
            FROM generations
            WHERE id = ?
            """,
            ("queued-generation-1",),
        ).fetchone()[0]

    assert generation_source_id == source_id


async def test_build_prompt_frontloads_setting_for_establish_panels_without_glamour_bias() -> None:
    prompt = comic_render_service._build_prompt(
        {
            "prompt_prefix": "masterpiece, best quality, high-response beauty editorial, strong eye contact",
            "canonical_prompt_anchor": "Camila Duarte, glamorous adult woman, luminous skin",
            "location_label": "Artist Loft Morning",
            "scene_continuity_notes": "Keep tall windows and the worktable visible.",
            "action_intent": "The lead enters the room and clocks a black invitation on the worktable from across the space.",
            "expression_intent": "Measured alertness",
            "camera_intent": "Wide establishing shot inside Artist Loft Morning, with the room and its key props clearly visible.",
            "panel_type": "establish",
            "framing": "Wide establishing composition with room depth and key props visible.",
            "continuity_lock": "Hold Artist Loft Morning's visual rules and keep the lead silhouette consistent.",
        }
    )

    assert prompt.startswith("Setting: inside Artist Loft Morning.")
    assert "Composition: establish manga panel" in prompt
    assert "environment-first framing" in prompt
    assert "high-response beauty editorial" not in prompt
    assert "strong eye contact" not in prompt
    assert "glamorous adult woman" not in prompt
    assert "luminous skin" not in prompt


async def test_non_establish_prompt_path_does_not_touch_catalog_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("catalog lookup should not run for non-establish prompts")

    monkeypatch.setattr(
        comic_render_service,
        "_resolve_story_planner_location_metadata",
        _boom,
    )

    prompt = comic_render_service._build_prompt(
        {
            "prompt_prefix": "masterpiece, best quality, original character",
            "canonical_prompt_anchor": "Kaede Ren, elegant east asian beauty",
            "location_label": "Private Lounge",
            "scene_continuity_notes": "Keep the scene controlled and intimate.",
            "action_intent": "Kaede studies the invitation.",
            "expression_intent": "Measured curiosity",
            "camera_intent": "Tight waist-up portrait",
            "panel_type": "beat",
            "framing": "Portrait framing",
            "continuity_lock": "Stay on brand for the character version.",
        }
    )

    assert prompt.startswith(
        "masterpiece, best quality, original character, Kaede Ren, elegant east asian beauty."
    )
    assert "Setting: inside Private Lounge." in prompt


async def test_establish_prompt_scene_first_for_artist_loft_morning() -> None:
    prompt = comic_render_service._build_prompt(
        {
            "prompt_prefix": "masterpiece, best quality, original character, adult woman, solo, fully clothed, tasteful adult allure",
            "canonical_prompt_anchor": "Kaede Ren, elegant east asian beauty, sleek black bob",
            "location_label": "Artist Loft Morning",
            "scene_continuity_notes": "Keep tall windows and the worktable visible.",
            "action_intent": "The lead enters the room and clocks a black invitation on the worktable from across the space.",
            "expression_intent": "Measured alertness",
            "camera_intent": "Wide establishing shot inside Artist Loft Morning, with the room and its key props clearly visible.",
            "panel_type": "establish",
            "framing": "Wide establishing composition with room depth and key props visible.",
            "continuity_lock": "Hold Artist Loft Morning's visual rules and keep the lead silhouette consistent.",
        }
    )

    assert prompt.startswith(
        "Setting: inside Artist Loft Morning. Scene cues: tall factory windows, easel."
    )
    assert "Composition: establish manga panel" in prompt
    assert "Subject prominence:" in prompt
    assert "tasteful adult allure" not in prompt
    assert "glamorous adult woman" not in prompt
    assert "high-response beauty editorial" not in prompt
    assert "strong eye contact" not in prompt
    assert "luminous skin" not in prompt


async def test_establish_generation_request_keeps_same_checkpoint(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(
        temp_db,
        panel_type="establish",
        location_label="Artist Loft Morning",
    )
    generation_service = _StubGenerationService(temp_db)

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=1,
    )

    payload = generation_service.batch_calls[0][0]
    assert payload["checkpoint"] == "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors"


async def test_establish_negative_prompt_appends_single_subject_glamour_poster_and_subject_filling_frame(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(
        temp_db,
        panel_type="establish",
        location_label="Artist Loft Morning",
    )
    generation_service = _StubGenerationService(temp_db)

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=1,
    )

    payload = generation_service.batch_calls[0][0]
    assert payload["negative_prompt"] == (
        "child, teen, underage, school uniform, text, logo, watermark, blurry, "
        "lowres, deformed, bad anatomy, extra fingers, duplicate, poorly drawn "
        "hands, explicit nudity, graphic sexual content, glamour shoot, "
        "fashion editorial, close portrait, airbrushed skin, copy-paste composition, "
        "single-subject glamour poster, pinup composition, beauty key visual, "
        "empty background, minimal room detail, subject filling frame"
    )


async def test_establish_generation_request_loads_artist_loft_scene_cues_from_story_planner_catalog_via_location_label(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(
        temp_db,
        panel_type="establish",
        location_label="Artist Loft Morning",
    )
    generation_service = _StubGenerationService(temp_db)
    catalog = StoryPlannerCatalog(
        locations=[
            StoryPlannerLocationCatalogEntry(
                id="artist_loft_morning",
                name="Artist Loft Morning",
                setting_anchor="Catalog-only artist loft anchor",
                visual_rules=["Keep the loft airy and sunlit."],
                restricted_elements=["nightclub lighting"],
                scene_cues=["north wall easel", "coffee mug"],
            )
        ]
    )
    load_calls: list[int] = []

    def _fake_load_story_planner_catalog() -> StoryPlannerCatalog:
        load_calls.append(1)
        return catalog

    monkeypatch.setattr(
        comic_render_service,
        "load_story_planner_catalog",
        _fake_load_story_planner_catalog,
    )

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=1,
    )

    payload = generation_service.batch_calls[0][0]
    assert load_calls == [1]
    assert payload["prompt"].startswith(
        "Setting: inside Artist Loft Morning. Scene cues: north wall easel, coffee mug."
    )


async def test_build_generation_request_uses_establish_profile_dimensions(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db, panel_type="establish")
    generation_service = _StubGenerationService(temp_db)
    source_id = _panel_render_source_id(panel_id, 1, "local_preview", panel_type="establish")

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=1,
    )

    payload = generation_service.batch_calls[0][0]
    assert payload["width"] == 1216
    assert payload["height"] == 832
    assert payload["checkpoint"] == "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors"
    assert payload["workflow_lane"] == "sdxl_illustrious"
    assert payload["negative_prompt"] == (
        "child, teen, underage, school uniform, text, logo, watermark, blurry, "
        "lowres, deformed, bad anatomy, extra fingers, duplicate, poorly drawn "
        "hands, explicit nudity, graphic sexual content, glamour shoot, "
        "fashion editorial, close portrait, airbrushed skin, copy-paste composition, "
        "single-subject glamour poster, pinup composition, beauty key visual, "
        "empty background, minimal room detail, subject filling frame"
    )
    assert payload["source_id"] == source_id


async def test_establish_generation_filters_beauty_enhancer_loras(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db, panel_type="establish")
    generation_service = _StubGenerationService(temp_db)

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=1,
    )

    payload = generation_service.batch_calls[0][0]
    assert payload["loras"] == []


async def test_closeup_generation_keeps_character_version_loras(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db, panel_type="closeup")
    generation_service = _StubGenerationService(temp_db)

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=1,
    )

    payload = generation_service.batch_calls[0][0]
    with sqlite3.connect(temp_db) as conn:
        expected_loras_json = conn.execute(
            """
            SELECT loras
            FROM character_versions
            WHERE id = ?
            """,
            ("charver_kaede_ren_still_v1",),
        ).fetchone()[0]

    assert payload["checkpoint"] == "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors"
    assert payload["workflow_lane"] == "sdxl_illustrious"
    assert payload["loras"] == json.loads(expected_loras_json)


async def test_queue_panel_render_candidates_remote_creates_generation_shells_and_jobs(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    generation_service = GenerationService()
    dispatch_calls: list[dict[str, object]] = []
    source_id = _panel_render_source_id(panel_id, 3, "remote_worker")

    async def _fake_dispatch(job, generation, render_asset, panel_context):  # type: ignore[no-untyped-def]
        dispatch_calls.append(
            {
                "job": dict(job),
                "generation": dict(generation),
                "render_asset": dict(render_asset),
                "panel_context": dict(panel_context),
            }
        )
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

    result = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="remote_worker",
    )

    assert isinstance(result, ComicPanelRenderQueueResponse)
    assert result.execution_mode == "remote_worker"
    assert result.requested_count == 3
    assert result.queued_generation_count == 3
    assert result.materialized_asset_count == 0
    assert result.pending_render_job_count == 3
    assert result.remote_job_count == 3
    assert len(result.render_assets) == 3
    assert all(asset.storage_path is None for asset in result.render_assets)

    with sqlite3.connect(temp_db) as conn:
        generation_rows = conn.execute(
            """
            SELECT id, status, source_id, prompt, checkpoint, width, height, error_message, seed
            FROM generations
            WHERE source_id = ?
            ORDER BY seed ASC, created_at ASC, id ASC
            """,
            (source_id,),
        ).fetchall()
        render_asset_rows = conn.execute(
            """
            SELECT id, generation_id, asset_role, storage_path
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (panel_id,),
        ).fetchall()
        job_rows = conn.execute(
            """
            SELECT generation_id, render_asset_id, status, target_tool, executor_mode,
                   executor_key, request_json, external_job_id, external_job_url,
                   submitted_at
            FROM comic_render_jobs
            WHERE scene_panel_id = ?
            ORDER BY request_index ASC
            """,
            (panel_id,),
        ).fetchall()

    assert [row[1] for row in generation_rows] == ["submitted", "submitted", "submitted"]
    assert [row[2] for row in generation_rows] == [source_id, source_id, source_id]
    assert [row[7] for row in generation_rows] == [None, None, None]
    assert [row[1] for row in render_asset_rows] == [row[0] for row in generation_rows]
    assert [row[2] for row in render_asset_rows] == ["candidate", "candidate", "candidate"]
    assert [row[3] for row in render_asset_rows] == [None, None, None]
    assert [row[0] for row in job_rows] == [row[0] for row in generation_rows]
    assert [row[1] for row in job_rows] == [row[0] for row in render_asset_rows]
    assert [row[2] for row in job_rows] == ["submitted", "submitted", "submitted"]
    assert [row[3] for row in job_rows] == ["comic_panel_still"] * 3
    assert [row[4] for row in job_rows] == ["remote_worker"] * 3
    assert [row[5] for row in job_rows] == [
        comic_render_service.settings.ANIMATION_EXECUTOR_KEY
    ] * 3
    assert all(row[7] is not None for row in job_rows)
    assert all(row[8] is not None for row in job_rows)
    assert all(row[9] is not None for row in job_rows)

    first_request_json = json.loads(job_rows[0][6])
    second_request_json = json.loads(job_rows[1][6])
    assert first_request_json["still_generation"]["source_id"] == source_id
    assert first_request_json["still_generation"]["seed"] == generation_rows[0][8]
    assert second_request_json["still_generation"]["seed"] == generation_rows[1][8]
    assert first_request_json["still_generation"]["seed"] != second_request_json["still_generation"]["seed"]
    assert first_request_json["comic"]["scene_panel_id"] == panel_id
    assert first_request_json["comic"]["render_asset_id"] == render_asset_rows[0][0]

    assert len(dispatch_calls) == 3
    assert dispatch_calls[0]["generation"]["id"] == generation_rows[0][0]
    assert dispatch_calls[0]["render_asset"]["id"] == render_asset_rows[0][0]
    assert dispatch_calls[0]["panel_context"]["character_version_id"] == (
        "charver_kaede_ren_still_v1"
    )

    assert generation_service._generation_queue.qsize() == 0
    assert generation_service._interactive_queue.qsize() == 0
    assert generation_service._favorite_backlog_queue.qsize() == 0


async def test_queue_panel_render_candidates_remote_retry_dispatches_queued_remainder_after_partial_failure(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    generation_service = GenerationService()
    first_pass = True
    dispatch_attempts: list[int] = []
    source_id = _panel_render_source_id(panel_id, 3, "remote_worker")

    async def _dispatch_with_first_failure(job, generation, render_asset, panel_context):  # type: ignore[no-untyped-def]
        nonlocal first_pass
        dispatch_attempts.append(job["request_index"])
        if first_pass and job["request_index"] == 0:
            raise ComicRenderDispatchError("dispatch failed for first job")
        return {
            "id": f"remote-job-{job['request_index']}",
            "job_id": f"remote-job-{job['request_index']}",
            "job_url": f"https://worker.test/jobs/{job['id']}",
        }

    monkeypatch.setattr(
        comic_render_service,
        "dispatch_comic_render_job",
        _dispatch_with_first_failure,
    )

    with pytest.raises(ComicRenderDispatchError, match="dispatch failed for first job"):
        await queue_panel_render_candidates(
            panel_id=panel_id,
            generation_service=generation_service,
            candidate_count=3,
            execution_mode="remote_worker",
        )

    with sqlite3.connect(temp_db) as conn:
        failed_pass_rows = conn.execute(
            """
            SELECT g.status, g.error_message, j.status, j.request_index
            FROM generations g
            JOIN comic_render_jobs j ON j.generation_id = g.id
            WHERE g.source_id = ?
            ORDER BY j.request_index ASC
            """,
            (source_id,),
        ).fetchall()

    assert dispatch_attempts == [0]
    assert failed_pass_rows == [
        ("failed", "dispatch failed for first job", "failed", 0),
        ("queued", None, "queued", 1),
        ("queued", None, "queued", 2),
    ]

    first_pass = False
    dispatch_attempts.clear()

    result = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="remote_worker",
    )

    assert result.execution_mode == "remote_worker"
    assert result.remote_job_count == 3
    assert result.pending_render_job_count == 2
    assert dispatch_attempts == [1, 2]

    with sqlite3.connect(temp_db) as conn:
        retry_rows = conn.execute(
            """
            SELECT g.status, g.error_message, j.status, j.request_index, j.external_job_id
            FROM generations g
            JOIN comic_render_jobs j ON j.generation_id = g.id
            WHERE g.source_id = ?
            ORDER BY j.request_index ASC
            """,
            (source_id,),
        ).fetchall()

    assert retry_rows == [
        ("failed", "dispatch failed for first job", "failed", 0, None),
        ("submitted", None, "submitted", 1, "remote-job-1"),
        ("submitted", None, "submitted", 2, "remote-job-2"),
    ]


async def test_queue_panel_render_candidates_remote_pending_count_excludes_failed_jobs(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    generation_service = GenerationService()
    source_id = _panel_render_source_id(panel_id, 3, "remote_worker")

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

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="remote_worker",
    )

    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            UPDATE comic_render_jobs
            SET status = CASE request_index
                WHEN 0 THEN 'submitted'
                WHEN 1 THEN 'failed'
                ELSE 'completed'
            END
            WHERE scene_panel_id = ?
            """,
            (panel_id,),
        )
        conn.commit()

    async def _dispatch_should_not_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("remote dispatch should not run for an existing remote batch")

    monkeypatch.setattr(
        comic_render_service,
        "dispatch_comic_render_job",
        _dispatch_should_not_run,
    )

    result = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="remote_worker",
    )

    assert result.execution_mode == "remote_worker"
    assert result.remote_job_count == 3
    assert result.pending_render_job_count == 1
    assert result.materialized_asset_count == 0


async def test_queue_panel_render_candidates_remote_reuse_reports_materialized_assets_after_callback(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    generation_service = GenerationService()
    source_id = _panel_render_source_id(panel_id, 3, "remote_worker")

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

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="remote_worker",
    )

    with sqlite3.connect(temp_db) as conn:
        job_ids = [
            row[0]
            for row in conn.execute(
                """
                SELECT id
                FROM comic_render_jobs
                WHERE scene_panel_id = ?
                ORDER BY request_index ASC
                """,
                (panel_id,),
            ).fetchall()
        ]

    await materialize_remote_render_job_callback(
        job_id=job_ids[0],
        payload=AnimationJobCallbackPayload(
            status="completed",
            output_path="images/comics/panel-1.png",
        ),
    )
    await materialize_remote_render_job_callback(
        job_id=job_ids[1],
        payload=AnimationJobCallbackPayload(
            status="completed",
            output_path="images/comics/panel-2.png",
        ),
    )

    async def _dispatch_should_not_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("remote dispatch should not run for an existing remote batch")

    monkeypatch.setattr(
        comic_render_service,
        "dispatch_comic_render_job",
        _dispatch_should_not_run,
    )

    result = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="remote_worker",
    )

    assert result.execution_mode == "remote_worker"
    assert result.remote_job_count == 3
    assert result.pending_render_job_count == 1
    assert result.materialized_asset_count == 2
    assert [asset.storage_path for asset in result.render_assets] == [
        "images/comics/panel-1.png",
        "images/comics/panel-2.png",
        None,
    ]


async def test_queue_panel_render_candidates_is_idempotent_for_same_panel_and_count(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    generation_service = _StubGenerationService(temp_db)
    source_id = _panel_render_source_id(panel_id, 3, "local_preview")

    first = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
    )
    second = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
    )

    assert first.render_assets[0].id == second.render_assets[0].id
    assert [asset.id for asset in first.render_assets] == [
        asset.id for asset in second.render_assets
    ]

    with sqlite3.connect(temp_db) as conn:
        asset_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            """,
            (panel_id,),
        ).fetchone()
        generation_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM generations
            WHERE source_id = ?
            """,
            (source_id,),
        ).fetchone()

    assert asset_rows is not None
    assert generation_rows is not None
    assert asset_rows[0] == 3
    assert generation_rows[0] == 3
    assert len(generation_service.batch_calls) == 1
    assert generation_service.batch_calls[0][0]["source_id"] == source_id


async def test_queue_panel_render_candidates_reuses_legacy_local_preview_batch(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    legacy_source_id = f"comic-panel-render:{panel_id}:3"

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for index in range(3):
            generation_id = f"legacy-generation-{index + 1}"
            conn.execute(
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
                    source_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation_id,
                    "legacy prompt",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    200 + index,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    legacy_source_id,
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
                    f"legacy-asset-{index + 1}",
                    panel_id,
                    generation_id,
                    "candidate",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    _now(),
                    _now(),
                ),
            )
        conn.commit()

    generation_service = _StubGenerationService(temp_db)

    result = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="local_preview",
    )

    assert result.execution_mode == "local_preview"
    assert [asset.id for asset in result.render_assets] == [
        "legacy-asset-1",
        "legacy-asset-2",
        "legacy-asset-3",
    ]
    assert len(generation_service.batch_calls) == 0


async def test_queue_panel_render_candidates_reuses_pre_profile_remote_worker_batch(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    legacy_source_id = f"comic-panel-render:{panel_id}:3:remote_worker"
    current_source_id = _panel_render_source_id(panel_id, 3, "remote_worker")

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for index in range(3):
            generation_id = f"remote-legacy-generation-{index + 1}"
            conn.execute(
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
                    source_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation_id,
                    "legacy remote prompt",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    400 + index,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "submitted",
                    legacy_source_id,
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
                    f"remote-legacy-asset-{index + 1}",
                    panel_id,
                    generation_id,
                    "candidate",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    _now(),
                    _now(),
                ),
            )
            conn.execute(
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
                (
                    f"remote-legacy-job-{index + 1}",
                    panel_id,
                    f"remote-legacy-asset-{index + 1}",
                    generation_id,
                    index,
                    legacy_source_id,
                    "comic_panel_still",
                    "remote_worker",
                    comic_render_service.settings.ANIMATION_EXECUTOR_KEY,
                    "submitted",
                    json.dumps({"still_generation": {"source_id": legacy_source_id}}),
                    f"remote-legacy-external-{index + 1}",
                    f"https://worker.test/jobs/remote-legacy-job-{index + 1}",
                    None,
                    None,
                    _now(),
                    None,
                    _now(),
                    _now(),
                ),
            )
        conn.commit()

    generation_service = GenerationService()

    result = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="remote_worker",
    )

    assert result.execution_mode == "remote_worker"
    assert result.remote_job_count == 3
    assert result.pending_render_job_count == 3
    assert [asset.generation_id for asset in result.render_assets] == [
        "remote-legacy-generation-1",
        "remote-legacy-generation-2",
        "remote-legacy-generation-3",
    ]

    with sqlite3.connect(temp_db) as conn:
        current_generation_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM generations
            WHERE source_id = ?
            """,
            (current_source_id,),
        ).fetchone()[0]
        legacy_job_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM comic_render_jobs
            WHERE source_id = ?
            """,
            (legacy_source_id,),
        ).fetchone()[0]

    assert current_generation_count == 0
    assert legacy_job_count == 3


async def test_queue_panel_render_candidates_refuses_stale_oldest_legacy_local_preview_batch(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    legacy_source_id = f"comic-panel-render:{panel_id}:3"

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for index in range(3):
            generation_id = f"stale-legacy-generation-{index + 1}"
            conn.execute(
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
                    source_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation_id,
                    "stale legacy prompt",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    500 + index,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    legacy_source_id,
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
                    f"stale-legacy-asset-{index + 1}",
                    panel_id,
                    generation_id,
                    "candidate",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    _now(),
                    _now(),
                ),
            )
        conn.execute(
            """
            UPDATE comic_scene_panels
            SET panel_type = ?, updated_at = ?
            WHERE id = ?
            """,
            ("establish", "2026-04-04T00:10:00+00:00", panel_id),
        )
        conn.commit()

    generation_service = _StubGenerationService(temp_db)
    current_source_id = _panel_render_source_id(panel_id, 3, "local_preview", panel_type="establish")

    result = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=3,
        execution_mode="local_preview",
    )

    assert result.execution_mode == "local_preview"
    assert len(generation_service.batch_calls) == 1
    assert generation_service.batch_calls[0][0]["source_id"] == current_source_id
    assert generation_service.batch_calls[0][0]["width"] == 1216
    assert generation_service.batch_calls[0][0]["height"] == 832
    assert [asset.generation_id for asset in result.render_assets] == [
        "queued-generation-1",
        "queued-generation-2",
        "queued-generation-3",
    ]


async def test_queue_panel_render_candidates_does_not_fall_back_when_current_source_has_generations(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db)
    current_source_id = _panel_render_source_id(panel_id, 3, "local_preview")
    legacy_source_id = f"comic-panel-render:{panel_id}:3"

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
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
                source_id,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "current-partial-generation-1",
                "current partial prompt",
                "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                "[]",
                111,
                34,
                5.5,
                832,
                1216,
                "euler_ancestral",
                "normal",
                "queued",
                current_source_id,
                _now(),
            ),
        )
        for index in range(3):
            generation_id = f"legacy-current-asset-{index + 1}"
            conn.execute(
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
                    source_id,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation_id,
                    "legacy prompt",
                    "ultimateHentaiAnimeRXTRexAnime_rxV1.safetensors",
                    "[]",
                    300 + index,
                    34,
                    5.5,
                    832,
                    1216,
                    "euler_ancestral",
                    "normal",
                    "queued",
                    legacy_source_id,
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
                    f"legacy-current-asset-{index + 1}",
                    panel_id,
                    generation_id,
                    "candidate",
                    None,
                    None,
                    None,
                    "[]",
                    None,
                    None,
                    0,
                    _now(),
                    _now(),
                ),
            )
        conn.commit()

    generation_service = GenerationService()

    with pytest.raises(
        ValueError,
        match=(
            "partial batch exists for source_id "
            f"'{current_source_id}': expected 3, found 1"
        ),
    ):
        await queue_panel_render_candidates(
            panel_id=panel_id,
            generation_service=generation_service,
            candidate_count=3,
            execution_mode="local_preview",
        )

    with sqlite3.connect(temp_db) as conn:
        current_generation_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM generations
            WHERE source_id = ?
            """,
            (current_source_id,),
        ).fetchone()
        legacy_asset_rows = conn.execute(
            """
            SELECT COUNT(*)
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ? AND generation_id LIKE 'legacy-current-asset-%'
            """,
            (panel_id,),
        ).fetchone()

    assert current_generation_rows is not None
    assert legacy_asset_rows is not None
    assert current_generation_rows[0] == 1
    assert legacy_asset_rows[0] == 3


async def test_queue_panel_render_candidates_changes_source_when_panel_profile_changes(
    temp_db: Path,
) -> None:
    panel_id = await _create_panel_fixture(temp_db, panel_type="establish")
    first_generation_service = _StubGenerationService(temp_db)

    first = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=first_generation_service,
        candidate_count=1,
    )

    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            UPDATE comic_scene_panels
            SET panel_type = ?, updated_at = ?
            WHERE id = ?
            """,
            ("closeup", _now(), panel_id),
        )
        conn.commit()

    second_generation_service = _StubGenerationService(
        temp_db,
        generation_id_prefix="closeup-",
    )
    second = await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=second_generation_service,
        candidate_count=1,
    )

    assert len(first_generation_service.batch_calls) == 1
    assert len(second_generation_service.batch_calls) == 1
    assert (
        first_generation_service.batch_calls[0][0]["source_id"]
        != second_generation_service.batch_calls[0][0]["source_id"]
    )
    assert first.render_assets[0].generation_id != second.render_assets[0].generation_id
    assert first_generation_service.batch_calls[0][0]["width"] == 1216
    assert second_generation_service.batch_calls[0][0]["width"] == 832
