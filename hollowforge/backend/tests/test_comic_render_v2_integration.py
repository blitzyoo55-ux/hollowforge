from __future__ import annotations

import io
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.config import settings
from app.models import ComicEpisodeCreate
from app.models import AnimationJobCallbackPayload
from app.services import comic_render_service
from app.services.comic_render_service import (
    materialize_remote_render_job_callback,
    queue_panel_render_candidates,
)
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
    panel_type: str = "beat",
    framing: str = "waist-up with workspace context",
    camera_intent: str = "eye-level camera",
    action_intent: str = "Camila checks notes beside the easel.",
    expression_intent: str = "focused calm",
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
                panel_type,
                framing,
                camera_intent,
                action_intent,
                expression_intent,
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
    def __init__(self, db_path: Path, *, generation_id_prefix: str = "") -> None:
        self._db_path = db_path
        self._generation_id_prefix = generation_id_prefix
        self.batch_calls: list[tuple[dict[str, object], int, int]] = []

    async def queue_generation_batch(  # type: ignore[no-untyped-def]
        self,
        generation,
        count: int,
        seed_increment: int = 1,
    ):
        payload = generation.model_dump()
        self.batch_calls.append((payload, count, seed_increment))

        rows = [
            SimpleNamespace(id=f"{self._generation_id_prefix}v2-local-gen-{index + 1}")
            for index in range(count)
        ]
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
        identity_block=(
            "Camila, poised adult woman with a practical, grounded presence",
            "Defined but natural face structure with calm proportions and stable recognition.",
            "Clear, attentive eyes with a steady directness and consistent gaze.",
            "Practical, low-fuss hair that reads as lived-in and controlled.",
            "Preserve a natural skin surface with light texture and avoid oversmoothing.",
            "Adult, grounded build with believable presence and balanced posture.",
            "Calm, observant, and direct with small controlled shifts in emotion.",
            "No glamour styling, no editorial beauty language, no resort presentation, no model-pose drift.",
            "Simple, functional wardrobe choices that support the scene without turning her into a fashion portrait.",
            "Measured, observant, and direct; she reads as self-possessed rather than performatively styled.",
            "Keep Camila anchored in a calm, grounded, non-glamour identity. Avoid drifting into editorial beauty framing.",
        ),
        style_block=(
            "Series style: Camila Pilot V1",
            "Keep linework clean, controlled, and panel-readable without heavy finish loss.",
            "Use restrained shading that supports volume while avoiding muddy contrast.",
            "Render surfaces with enough texture to stay natural without adding noise.",
            "Prioritize clear subject separation and readable forms in still frames.",
            "Avoid blur, melt, warped anatomy, over-smoothing, and other generation artifacts.",
            "Preserve hands and faces with extra care because they are the highest risk regions for still quality.",
            "Style notes: Pilot series style canon for the Camila-only V2 pilot.",
        ),
        binding_block=(
            "Binding notes: Camila-only pilot binding for the V2 registry pilot.",
            "Identity lock: strong",
            "Hair lock: strong",
            "Face lock: strong",
            "Wardrobe family: simple functional everyday wardrobe",
            "Do not mutate: Do not mutate Camila identity ownership or style ownership through this binding.",
            "Location: artist loft morning",
            "Continuity: Carry over the wet brush on the easel from prior panel.",
        ),
        role_block=("Role: beat panel",),
        execution_params={
            "checkpoint": "v2_style_checkpoint.safetensors",
            "loras": (
                {"filename": "v2_style_lora.safetensors", "strength": 0.61},
            ),
            "steps": 29,
            "cfg": 5.35,
            "sampler": "euler_a",
            "identity_lock_strength": 0.92,
            "style_lock_strength": 0.88,
            "width": 960,
            "height": 1216,
            "framing_profile": "beat_dialogue_v1",
            "positive_merge_sequence": (
                "role",
                "identity",
                "style",
                "binding",
                "continuity_location",
            ),
            "negative_merge_sequence": (
                "style_artifacts",
                "identity_drift",
                "binding_drift",
                "role_quality",
            ),
        },
        negative_rules=(
            "Avoid blur, melt, warped anatomy, over-smoothing, and other generation artifacts.",
            "No glamour styling, no editorial beauty language, no resort presentation, no model-pose drift, no school-uniform cues, no necktie, no orange hair, no youth-coded anime heroine drift.",
            "Keep Camila anchored in a calm, grounded, adult non-glamour identity. Avoid drifting into editorial beauty framing, school-uniform styling, or youthful heroine shortcuts.",
            "No wardrobe drift, no glamour drift, no editorial styling drift.",
            "Role negative: plastic skin, waxy face, dead eyes",
        ),
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
    assert "Inside Artist Loft Morning." in payload["prompt"]
    assert "Camila checks notes beside the easel." in payload["prompt"]
    assert "Action:" not in payload["prompt"]
    assert "Composition:" not in payload["prompt"]
    assert "Series style:" not in payload["prompt"]
    assert "Binding notes:" not in payload["prompt"]

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
        "identity_block": [
            "Camila, poised adult woman with a practical, grounded presence",
            "Defined but natural face structure with calm proportions and stable recognition.",
            "Clear, attentive eyes with a steady directness and consistent gaze.",
            "Practical, low-fuss hair that reads as lived-in and controlled.",
            "Preserve a natural skin surface with light texture and avoid oversmoothing.",
            "Adult, grounded build with believable presence and balanced posture.",
            "Calm, observant, and direct with small controlled shifts in emotion.",
            "No glamour styling, no editorial beauty language, no resort presentation, no model-pose drift.",
            "Simple, functional wardrobe choices that support the scene without turning her into a fashion portrait.",
            "Measured, observant, and direct; she reads as self-possessed rather than performatively styled.",
            "Keep Camila anchored in a calm, grounded, non-glamour identity. Avoid drifting into editorial beauty framing.",
        ],
        "style_block": [
            "Series style: Camila Pilot V1",
            "Keep linework clean, controlled, and panel-readable without heavy finish loss.",
            "Use restrained shading that supports volume while avoiding muddy contrast.",
            "Render surfaces with enough texture to stay natural without adding noise.",
            "Prioritize clear subject separation and readable forms in still frames.",
            "Avoid blur, melt, warped anatomy, over-smoothing, and other generation artifacts.",
            "Preserve hands and faces with extra care because they are the highest risk regions for still quality.",
            "Style notes: Pilot series style canon for the Camila-only V2 pilot.",
        ],
        "binding_block": [
            "Binding notes: Camila-only pilot binding for the V2 registry pilot.",
            "Identity lock: strong",
            "Hair lock: strong",
            "Face lock: strong",
            "Wardrobe family: simple functional everyday wardrobe",
            "Do not mutate: Do not mutate Camila identity ownership or style ownership through this binding.",
            "Location: artist loft morning",
            "Continuity: Carry over the wet brush on the easel from prior panel.",
        ],
        "role_block": ["Role: beat panel"],
        "negative_rules": [
            "Avoid blur, melt, warped anatomy, over-smoothing, and other generation artifacts.",
            "No glamour styling, no editorial beauty language, no resort presentation, no model-pose drift, no school-uniform cues, no necktie, no orange hair, no youth-coded anime heroine drift.",
            "Keep Camila anchored in a calm, grounded, adult non-glamour identity. Avoid drifting into editorial beauty framing, school-uniform styling, or youthful heroine shortcuts.",
            "No wardrobe drift, no glamour drift, no editorial styling drift.",
            "Role negative: plastic skin, waxy face, dead eyes",
        ],
    }
    assert snapshot["resolver_execution_summary"]["identity_lock_strength"] == 0.92
    assert snapshot["resolver_execution_summary"]["style_lock_strength"] == 0.88
    assert snapshot["resolver_execution_summary"]["width"] == 960
    assert snapshot["resolver_execution_summary"]["height"] == 1216
    assert snapshot["resolver_execution_summary"]["framing_profile"] == "beat_dialogue_v1"
    assert snapshot["resolver_execution_summary"]["positive_merge_sequence"] == [
        "role",
        "identity",
        "style",
        "binding",
        "continuity_location",
    ]
    assert snapshot["resolver_execution_summary"]["negative_merge_sequence"] == [
        "style_artifacts",
        "identity_drift",
        "binding_drift",
        "role_quality",
    ]


async def test_v2_establish_override_and_beat_panel_keeps_base_style_stack(
    temp_db: Path,
) -> None:
    establish_panel_id = await _create_panel_fixture(
        temp_db,
        panel_id="panel_v2_establish_local_1",
        scene_id="scene_v2_establish_local_1",
        episode_id="episode_v2_establish_local_1",
        render_lane="character_canon_v2",
        character_id="char_camila_duarte",
        character_version_id="charver_camila_duarte_still_v1",
        series_style_id="camila_pilot_v1",
        character_series_binding_id="camila_pilot_binding_v1",
        panel_type="establish",
        framing="wide room composition with worktable depth",
        camera_intent="wide establishing shot inside Artist Loft Morning",
        action_intent="Camila checks the studio lockbox by the window.",
        expression_intent="measured alertness",
    )
    beat_panel_id = await _create_panel_fixture(
        temp_db,
        panel_id="panel_v2_beat_local_1",
        scene_id="scene_v2_beat_local_1",
        episode_id="episode_v2_beat_local_1",
        render_lane="character_canon_v2",
        character_id="char_camila_duarte",
        character_version_id="charver_camila_duarte_still_v1",
        series_style_id="camila_pilot_v1",
        character_series_binding_id="camila_pilot_binding_v1",
    )
    establish_generation_service = _StubGenerationService(
        temp_db,
        generation_id_prefix="establish-",
    )
    await queue_panel_render_candidates(
        panel_id=establish_panel_id,
        generation_service=establish_generation_service,  # type: ignore[arg-type]
        candidate_count=1,
        execution_mode="local_preview",
    )
    beat_generation_service = _StubGenerationService(
        temp_db,
        generation_id_prefix="beat-",
    )
    await queue_panel_render_candidates(
        panel_id=beat_panel_id,
        generation_service=beat_generation_service,  # type: ignore[arg-type]
        candidate_count=1,
        execution_mode="local_preview",
    )

    establish_payload, _, _ = establish_generation_service.batch_calls[0]
    assert establish_payload["checkpoint"] == "akiumLumenILLBase_baseV2.safetensors"
    assert establish_payload["loras"] == []
    assert establish_payload.get("reference_guided") is not True
    assert "still_backend_family" not in establish_payload

    with sqlite3.connect(temp_db) as conn:
        raw_snapshot = conn.execute(
            """
            SELECT prompt_snapshot
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (establish_panel_id,),
        ).fetchone()[0]

    snapshot = json.loads(raw_snapshot)
    assert snapshot["resolver_execution_summary"]["reference_guided"] is True
    assert snapshot["resolver_execution_summary"]["still_backend_family"] == "sdxl_ipadapter_still"

    beat_payload, _, _ = beat_generation_service.batch_calls[0]
    assert beat_payload["checkpoint"] == "prefectIllustriousXL_v70.safetensors"
    assert beat_payload["loras"] == [
        {
            "filename": "DetailedEyes_V3.safetensors",
            "strength": 0.45,
            "category": None,
        },
        {
            "filename": "Face_Enhancer_Illustrious.safetensors",
            "strength": 0.36,
            "category": None,
        },
    ]


async def test_v2_establish_lane_rolls_back_to_text_only_execution_payload(
    temp_db: Path,
) -> None:
    establish_panel_id = await _create_panel_fixture(
        temp_db,
        panel_id="panel_v2_establish_text_only_1",
        scene_id="scene_v2_establish_text_only_1",
        episode_id="episode_v2_establish_text_only_1",
        render_lane="character_canon_v2",
        character_id="char_camila_duarte",
        character_version_id="charver_camila_duarte_still_v1",
        series_style_id="camila_pilot_v1",
        character_series_binding_id="camila_pilot_binding_v1",
        panel_type="establish",
        framing="wide room composition with worktable depth",
        camera_intent="wide establishing shot inside Artist Loft Morning",
        action_intent="Camila checks the studio lockbox by the window.",
        expression_intent="measured alertness",
    )
    generation_service = _StubGenerationService(
        temp_db,
        generation_id_prefix="establish-text-only-",
    )

    await queue_panel_render_candidates(
        panel_id=establish_panel_id,
        generation_service=generation_service,  # type: ignore[arg-type]
        candidate_count=1,
        execution_mode="local_preview",
    )

    establish_payload, _, _ = generation_service.batch_calls[0]
    assert establish_payload["checkpoint"] == "akiumLumenILLBase_baseV2.safetensors"
    assert establish_payload["loras"] == []
    assert establish_payload.get("reference_guided") is not True
    assert "still_backend_family" not in establish_payload
    assert len(establish_payload["prompt"]) <= 1800
    assert len(establish_payload["negative_prompt"]) <= 800
    assert establish_payload["prompt"].count("Artist Loft Morning") <= 2


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


async def test_v2_remote_callback_blends_identity_gate_into_quality_score(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(
        temp_db,
        panel_id="panel_v2_remote_callback_1",
        scene_id="scene_v2_remote_callback_1",
        episode_id="episode_v2_remote_callback_1",
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

    async def _fake_analyze_image(_image_path: str, pixel_art_mode: bool = False):  # type: ignore[no-untyped-def]
        return {
            "wd14": {
                "bad_tags": [],
                "good_tags": [],
                "all_tags": {
                    "brown_hair": 0.91,
                    "long_hair": 0.88,
                    "wavy_hair": 0.74,
                    "solo": 0.97,
                },
            }
        }

    monkeypatch.setattr(
        comic_render_service,
        "dispatch_comic_render_job",
        _fake_dispatch,
    )
    monkeypatch.setattr(
        comic_render_service,
        "analyze_image",
        _fake_analyze_image,
    )
    monkeypatch.setattr(
        comic_render_service,
        "detect_faces",
        lambda _path: [(70, 70, 100, 110)],
    )

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=2,
        execution_mode="remote_worker",
    )

    with sqlite3.connect(temp_db) as conn:
        job_id = conn.execute(
            """
            SELECT id
            FROM comic_render_jobs
            WHERE scene_panel_id = ?
            ORDER BY request_index ASC
            LIMIT 1
            """,
            (panel_id,),
        ).fetchone()[0]

    output_dir = settings.DATA_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (240, 240), (208, 178, 148))
    for x in range(70, 170):
        for y in range(25, 90):
            image.putpixel((x, y), (108, 80, 58))
    for x in range(88, 152):
        for y in range(108, 178):
            image.putpixel((x, y), (186, 156, 134))
    image.save(output_dir / "camila-v2-panel.png")

    await materialize_remote_render_job_callback(
        job_id=job_id,
        payload=AnimationJobCallbackPayload(
            status="completed",
            output_path="outputs/camila-v2-panel.png",
            request_json={
                "worker": {
                    "quality_assessment": {
                        "positive_signals": ["expression readability"],
                        "negative_signals": [],
                    }
                }
            },
        ),
    )

    with sqlite3.connect(temp_db) as conn:
        asset_row = conn.execute(
            """
            SELECT quality_score, render_notes, storage_path
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (panel_id,),
        ).fetchone()

    assert asset_row[2] == "outputs/camila-v2-panel.png"
    assert asset_row[0] is not None
    assert asset_row[0] > 0.48
    assert "identity gate: passed" in asset_row[1]
    assert "identity reward: camila visual hair reference match" in asset_row[1]


async def test_v2_remote_callback_downloads_output_url_when_local_file_is_missing(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(
        temp_db,
        panel_id="camila-v2-panel-download",
        scene_id="camila-v2-scene-download",
        episode_id="camila-v2-episode-download",
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

    async def _fake_analyze_image(_path: str) -> dict[str, object]:
        return {
            "wd14": {
                "all_tags": {
                    "1girl": 0.98,
                    "solo": 0.97,
                    "brown_hair": 0.91,
                    "long_hair": 0.83,
                    "wavy_hair": 0.74,
                    "tanned_skin": 0.72,
                },
                "bad_tags": [],
            }
        }

    image_bytes = io.BytesIO()
    image = Image.new("RGB", (240, 240), (208, 178, 148))
    for x in range(70, 170):
        for y in range(25, 90):
            image.putpixel((x, y), (108, 80, 58))
    for x in range(88, 152):
        for y in range(108, 178):
            image.putpixel((x, y), (186, 156, 134))
    image.save(image_bytes, format="PNG")

    class _FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        async def __aenter__(self) -> "_FakeAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            return None

        async def get(self, url: str) -> _FakeResponse:
            assert url == "https://worker.test/data/outputs/camila-v2-panel.png"
            return _FakeResponse(image_bytes.getvalue())

    monkeypatch.setattr(
        comic_render_service,
        "dispatch_comic_render_job",
        _fake_dispatch,
    )
    monkeypatch.setattr(
        comic_render_service,
        "analyze_image",
        _fake_analyze_image,
    )
    monkeypatch.setattr(
        comic_render_service,
        "detect_faces",
        lambda _path: [(70, 70, 100, 110)],
    )
    monkeypatch.setattr(comic_render_service, "httpx", SimpleNamespace(AsyncClient=_FakeAsyncClient, Timeout=lambda value: value))

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=2,
        execution_mode="remote_worker",
    )

    with sqlite3.connect(temp_db) as conn:
        job_id = conn.execute(
            """
            SELECT id
            FROM comic_render_jobs
            WHERE scene_panel_id = ?
            ORDER BY request_index ASC
            LIMIT 1
            """,
            (panel_id,),
        ).fetchone()[0]

    await materialize_remote_render_job_callback(
        job_id=job_id,
        payload=AnimationJobCallbackPayload(
            status="completed",
            output_path="outputs/camila-v2-panel.png",
            output_url="https://worker.test/data/outputs/camila-v2-panel.png",
        ),
    )

    with sqlite3.connect(temp_db) as conn:
        asset_row = conn.execute(
            """
            SELECT quality_score, render_notes, storage_path
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (panel_id,),
        ).fetchone()

    assert asset_row[2] == "outputs/camila-v2-panel.png"
    assert asset_row[0] is not None
    assert "identity gate: passed" in asset_row[1]
    assert (settings.DATA_DIR / "outputs" / "camila-v2-panel.png").exists()


async def test_v2_remote_callback_fails_identity_gate_for_reference_drift(
    temp_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    panel_id = await _create_panel_fixture(
        temp_db,
        panel_id="camila-v2-panel-drift",
        scene_id="camila-v2-scene-drift",
        episode_id="camila-v2-episode-drift",
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

    async def _fake_analyze_image(_path: str) -> dict[str, object]:
        return {
            "wd14": {
                "all_tags": {
                    "1girl": 0.98,
                    "solo": 0.97,
                    "school_uniform": 0.82,
                    "black_hair": 0.88,
                    "pale_skin": 0.75,
                },
                "bad_tags": [],
            }
        }

    monkeypatch.setattr(
        comic_render_service,
        "dispatch_comic_render_job",
        _fake_dispatch,
    )
    monkeypatch.setattr(
        comic_render_service,
        "analyze_image",
        _fake_analyze_image,
    )
    monkeypatch.setattr(
        comic_render_service,
        "detect_faces",
        lambda _path: [(70, 70, 100, 110)],
    )

    await queue_panel_render_candidates(
        panel_id=panel_id,
        generation_service=generation_service,
        candidate_count=2,
        execution_mode="remote_worker",
    )

    with sqlite3.connect(temp_db) as conn:
        job_id = conn.execute(
            """
            SELECT id
            FROM comic_render_jobs
            WHERE scene_panel_id = ?
            ORDER BY request_index ASC
            LIMIT 1
            """,
            (panel_id,),
        ).fetchone()[0]

    output_dir = settings.DATA_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (240, 240), (235, 230, 234))
    for x in range(70, 170):
        for y in range(25, 90):
            image.putpixel((x, y), (30, 30, 36))
    for x in range(88, 152):
        for y in range(108, 178):
            image.putpixel((x, y), (238, 231, 236))
    image.save(output_dir / "camila-v2-drift.png")

    await materialize_remote_render_job_callback(
        job_id=job_id,
        payload=AnimationJobCallbackPayload(
            status="completed",
            output_path="outputs/camila-v2-drift.png",
        ),
    )

    with sqlite3.connect(temp_db) as conn:
        asset_row = conn.execute(
            """
            SELECT quality_score, render_notes, storage_path
            FROM comic_panel_render_assets
            WHERE scene_panel_id = ?
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (panel_id,),
        ).fetchone()

    assert asset_row[2] == "outputs/camila-v2-drift.png"
    assert asset_row[0] is not None
    assert asset_row[0] <= 0.24
    assert "identity gate: failed" in asset_row[1]
    assert "identity penalty: camila wardrobe drift" in asset_row[1]
