"""LoRA profile listing and smart selection endpoints."""

from typing import List

from fastapi import APIRouter, status

from app.db import get_db
from app.models import LoraProfileResponse, MoodSelectRequest, MoodSelectResponse
from app.services.lora_selector import select_by_moods

router = APIRouter(prefix="/api/v1/loras", tags=["loras"])


@router.get("", response_model=List[LoraProfileResponse])
async def list_loras() -> List[LoraProfileResponse]:
    """Return all registered LoRA profiles."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM lora_profiles ORDER BY category, display_name"
        )
        rows = await cursor.fetchall()
    return [LoraProfileResponse(**r) for r in rows]


@router.post(
    "/select",
    response_model=MoodSelectResponse,
    status_code=status.HTTP_200_OK,
)
async def select_loras(req: MoodSelectRequest) -> MoodSelectResponse:
    """Smart LoRA selection based on mood keywords."""
    async with get_db() as db:
        loras, prompt_additions = await select_by_moods(
            db, req.moods, req.checkpoint
        )
    return MoodSelectResponse(loras=loras, prompt_additions=prompt_additions)
