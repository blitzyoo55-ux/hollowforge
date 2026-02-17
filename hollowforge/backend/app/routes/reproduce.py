"""Reproduce / variation endpoints."""

import json
import random
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, status

from app.db import get_db
from app.models import (
    GenerationCreate,
    GenerationResponse,
    LoraInput,
    ReproduceRequest,
)
from app.services.generation_service import GenerationService

router = APIRouter(prefix="/api/v1/reproduce", tags=["reproduce"])


def _parse_json(val: Optional[str], default: Any = None) -> Any:
    if val is None:
        return default
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return default


@router.post("/{generation_id}", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
async def reproduce_generation(
    generation_id: str, req: ReproduceRequest, request: Request
) -> GenerationResponse:
    """Reproduce or create a variation of an existing generation.

    - mode=exact: same parameters + same seed
    - mode=variation: same parameters + new random seed
    """
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM generations WHERE id = ?", (generation_id,)
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )

    # Determine seed
    if req.mode == "exact":
        seed = req.seed if req.seed is not None else row["seed"]
    else:  # variation
        seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)

    # Rebuild LoRA list
    loras_raw = _parse_json(row.get("loras"), [])
    loras = [
        LoraInput(**l) if isinstance(l, dict) else l for l in loras_raw
    ]
    tags = _parse_json(row.get("tags"))

    gen_create = GenerationCreate(
        prompt=row["prompt"],
        negative_prompt=row.get("negative_prompt"),
        checkpoint=row["checkpoint"],
        loras=loras,
        seed=seed,
        steps=row["steps"],
        cfg=row["cfg"],
        width=row["width"],
        height=row["height"],
        sampler=row["sampler"],
        scheduler=row["scheduler"],
        tags=tags,
        preset_id=row.get("preset_id"),
        notes=req.notes or f"Reproduced ({req.mode}) from {generation_id}",
        source_id=generation_id,
    )

    service: GenerationService = request.app.state.generation_service
    return await service.queue_generation(gen_create)
