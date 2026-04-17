from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.services.generation_service import GenerationService
from app.models import GenerationCreate

pytestmark = pytest.mark.asyncio


def _count_generations_for_source(temp_db: Path, source_id: str) -> int:
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM generations WHERE source_id = ?",
            (source_id,),
        )
        row = cursor.fetchone()
    assert row is not None
    return int(row[0])


async def test_queue_generation_batch_preserves_blank_negative_prompt_when_requested(
    temp_db: Path,
) -> None:
    service = GenerationService()

    _, queued = await service.queue_generation_batch(
        GenerationCreate(
            prompt="blank negative prompt test",
            negative_prompt=None,
            preserve_blank_negative_prompt=True,
            checkpoint="waiIllustriousSDXL_v140.safetensors",
            workflow_lane="sdxl_illustrious",
            source_id="story-planner:blank-negative",
        ),
        count=2,
    )

    assert [row.negative_prompt for row in queued] == [None, None]
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute(
            "SELECT negative_prompt FROM generations WHERE source_id = ? ORDER BY created_at ASC",
            ("story-planner:blank-negative",),
        )
        rows = cursor.fetchall()

    assert [row[0] for row in rows] == [None, None]


async def test_queue_generation_batch_reuses_existing_source_id_batch(
    temp_db: Path,
) -> None:
    service = GenerationService()
    generation = GenerationCreate(
        prompt="reused source batch",
        checkpoint="waiIllustriousSDXL_v140.safetensors",
        workflow_lane="sdxl_illustrious",
        source_id="story-planner:shot-01",
    )

    first_base_seed, first_batch = await service.queue_generation_batch(
        generation,
        count=2,
    )
    second_base_seed, second_batch = await service.queue_generation_batch(
        generation,
        count=2,
    )

    assert second_base_seed == first_base_seed
    assert [row.id for row in second_batch] == [row.id for row in first_batch]
    assert _count_generations_for_source(temp_db, "story-planner:shot-01") == 2


async def test_queue_generation_batch_rejects_partial_source_id_batch(
    temp_db: Path,
) -> None:
    service = GenerationService()
    generation = GenerationCreate(
        prompt="partial source batch",
        checkpoint="waiIllustriousSDXL_v140.safetensors",
        workflow_lane="sdxl_illustrious",
        source_id="story-planner:shot-02",
    )

    await service.queue_generation(
        generation.model_copy(update={"seed": 101})
    )

    with pytest.raises(ValueError, match="partial batch"):
        await service.queue_generation_batch(
            generation,
            count=2,
        )

    assert _count_generations_for_source(temp_db, "story-planner:shot-02") == 1


async def test_queue_generation_batch_accepts_single_generation(
    temp_db: Path,
) -> None:
    service = GenerationService()

    base_seed, queued = await service.queue_generation_batch(
        GenerationCreate(
            prompt="single generation batch",
            checkpoint="waiIllustriousSDXL_v140.safetensors",
            workflow_lane="sdxl_illustrious",
            source_id="story-planner:single-batch",
        ),
        count=1,
    )

    assert len(queued) == 1
    assert queued[0].seed == base_seed
    assert _count_generations_for_source(temp_db, "story-planner:single-batch") == 1


async def test_create_generation_shell_batch_accepts_single_generation(
    temp_db: Path,
) -> None:
    service = GenerationService()

    base_seed, queued = await service.create_generation_shell_batch(
        GenerationCreate(
            prompt="single shell batch",
            checkpoint="waiIllustriousSDXL_v140.safetensors",
            workflow_lane="sdxl_illustrious",
            source_id="story-planner:single-shell-batch",
        ),
        count=1,
    )

    assert len(queued) == 1
    assert queued[0].seed == base_seed
    assert _count_generations_for_source(
        temp_db, "story-planner:single-shell-batch"
    ) == 1
