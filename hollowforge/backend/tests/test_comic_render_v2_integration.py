from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import ComicEpisodeCreate
from app.services import comic_render_service
from app.services.comic_render_service import queue_panel_render_candidates
from app.services.comic_render_v2_resolver import ComicRenderV2Contract
from app.services.comic_repository import create_comic_episode
from app.services.generation_service import GenerationService

pytestmark = pytest.mark.asyncio


def _now() -> str:
    return "2026-04-04T00:00:00+00:00"


async def _create_panel_fixture(
    temp_db: Path,
    *,
    panel_id: str,
    scene_id: str,
    episode_id: str,
    render_lane: str,
    character_id: str,
    character_version_id: str,
    series_style_id: str | None = None,
    character_series_binding_id: str | None = None,
) -> str:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id=character_id,
            character_version_id=character_version_id,
            title="Lane fixture",
            synopsis="Lane fixture for comic render integration tests.",
            target_output="oneshot_manga",
            render_lane=render_lane,  # type: ignore[arg-type]
            series_style_id=series_style_id,
            character_series_binding_id=character_series_binding_id,
        ),
        episode_id=episode_id,
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
                "Camila checks the easel notes.",
                "Artist Loft Morning",
                "Carry over brush and sketchbook placement.",
                json.dumps([character_id]),
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
                "beat",
                "waist-up with workspace context",
                "eye-level camera",
                "Camila checks notes beside the easel.",
                "focused calm",
                "placeholder dialogue",
                "Keep brush and sketchbook continuity.",
                1,
                1,
                _now(),
                _now(),
            ),
        )
        conn.commit()

    return panel_id


class _StubGenerationService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self.batch_calls: list[tuple[dict[str, object], int, int]] = []

    async def queue_generation_batch(  # type: ignore[no-untyped-def]
        self,
        generation,
        count: int,
        seed_increment: int = 1,
    ):
        payload = generation.model_dump()
        self.batch_calls.append((payload, count, seed_increment))

        rows = [SimpleNamespace(id=f"v2-local-gen-{index + 1}") for index in range(count)]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            for index, row in enumerate(rows):
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
                        row.id,
                        generation.prompt,
                        generation.negative_prompt,
                        generation.checkpoint,
                        json.dumps(payload["loras"]),
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
        return 100, rows


async def test_v2_lane_uses_resolver_contract_not_legacy_prompt_assembly_and_records_snapshot(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(
        temp_db,
        panel_id="panel_v2_local_1",
        scene_id="scene_v2_local_1",
        episode_id="episode_v2_local_1",
        render_lane="character_canon_v2",
        character_id="char_camila_duarte",
        character_version_id="charver_camila_duarte_still_v1",
        series_style_id="camila_pilot_v1",
        character_series_binding_id="camila_pilot_binding_v1",
    )
    generation_service = _StubGenerationService(temp_db)

    def _unexpected_legacy_prompt(_context):  # type: ignore[no-untyped-def]
        raise AssertionError("legacy prompt assembly invoked for character_canon_v2 lane")

    contract = ComicRenderV2Contract(
        identity_block=("Identity: Camila grounded presence",),
        style_block=("Style: Camila Pilot V1",),
        binding_block=("Binding: Camila pilot binding",),
        role_block=("Role: beat panel",),
        execution_params={
            "checkpoint": "v2_style_checkpoint.safetensors",
            "loras": (
                {"filename": "v2_style_lora.safetensors", "strength": 0.61},
            ),
            "steps": 29,
            "cfg": 5.35,
            "sampler": "euler_a",
        },
        negative_rules=("Avoid style drift", "Avoid identity drift"),
    )

    monkeypatch.setattr(comic_render_service, "_build_prompt", _unexpected_legacy_prompt)
    monkeypatch.setattr(
        comic_render_service,
        "resolve_comic_render_v2_contract",
        lambda **_: contract,
        raising=False,
    )

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,  # type: ignore[arg-type]
        candidate_count=2,
        execution_mode="local_preview",
    )

    assert len(generation_service.batch_calls) == 1
    payload, _, _ = generation_service.batch_calls[0]
    assert payload["checkpoint"] == "v2_style_checkpoint.safetensors"
    assert payload["loras"] == [
        {
            "filename": "v2_style_lora.safetensors",
            "strength": 0.61,
            "category": None,
        },
    ]
    assert payload["steps"] == 29
    assert payload["cfg"] == 5.35
    assert payload["sampler"] == "euler_a"
    assert payload["width"] == 960
    assert payload["height"] == 1216

    with sqlite3.connect(temp_db) as conn:
        raw_snapshot = conn.execute(
            """
            SELECT prompt_snapshot
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (panel_id,),
        ).fetchone()[0]

    snapshot = json.loads(raw_snapshot)
    assert snapshot["render_lane"] == "character_canon_v2"
    assert snapshot["series_style_id"] == "camila_pilot_v1"
    assert snapshot["character_series_binding_id"] == "camila_pilot_binding_v1"
    assert snapshot["resolver_sections"] == {
        "identity_block": ["Identity: Camila grounded presence"],
        "style_block": ["Style: Camila Pilot V1"],
        "binding_block": ["Binding: Camila pilot binding"],
        "role_block": ["Role: beat panel"],
        "negative_rules": ["Avoid style drift", "Avoid identity drift"],
    }


async def test_v2_remote_job_request_json_carries_lane_binding_and_resolver_summary(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(
        temp_db,
        panel_id="panel_v2_remote_1",
        scene_id="scene_v2_remote_1",
        episode_id="episode_v2_remote_1",
        render_lane="character_canon_v2",
        character_id="char_camila_duarte",
        character_version_id="charver_camila_duarte_still_v1",
        series_style_id="camila_pilot_v1",
        character_series_binding_id="camila_pilot_binding_v1",
    )
    generation_service = GenerationService()

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
        candidate_count=2,
        execution_mode="remote_worker",
    )

    with sqlite3.connect(temp_db) as conn:
        request_json = json.loads(
            conn.execute(
                """
                SELECT request_json
                FROM comic_render_jobs
                WHERE scene_panel_id = ?
                ORDER BY request_index ASC
                LIMIT 1
                """,
                (panel_id,),
            ).fetchone()[0]
        )

    comic_payload = request_json["comic"]
    assert comic_payload["render_lane"] == "character_canon_v2"
    assert comic_payload["series_style_id"] == "camila_pilot_v1"
    assert comic_payload["character_series_binding_id"] == "camila_pilot_binding_v1"
    resolver_sections = comic_payload["resolver_sections"]
    assert sorted(resolver_sections.keys()) == [
        "binding_block",
        "identity_block",
        "negative_rules",
        "role_block",
        "style_block",
    ]
    assert all(isinstance(value, list) for value in resolver_sections.values())
