"""Marketing automation endpoints."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.db import get_db
from app.models import (
    GenerationCreate,
    PromptBatchGenerateRequest,
    PromptBatchGenerateResponse,
    PromptBatchQueueResponse,
    PromptFactoryCapabilitiesResponse,
    StoryPlannerAnchorQueueRequest,
    StoryPlannerAnchorQueueResponse,
    StoryPlannerCatalog,
    StoryPlannerPlanRequest,
    StoryPlannerPlanResponse,
)
from app.services.caption_service import (
    generate_caption_from_image_bytes,
    mime_type_from_image_path,
)
from app.services.prompt_factory_service import (
    generate_prompt_batch,
    get_prompt_factory_capabilities,
)
from app.services.generation_service import GenerationService
from app.services.story_planner_catalog import load_story_planner_catalog
from app.services.story_planner_service import (
    plan_story_episode,
    queue_story_planner_anchor_batch,
    StoryPlannerValidationError,
)

router = APIRouter(tags=["marketing"])


class CaptionByIdRequest(BaseModel):
    generation_id: str


def _get_generation_service(request: Request) -> GenerationService:
    return request.app.state.generation_service


def _resolve_generation_image_file_path(image_path: str) -> Path:
    candidate = (settings.DATA_DIR / image_path).resolve()
    data_root = settings.DATA_DIR.resolve()
    try:
        candidate.relative_to(data_root)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsafe image path",
        ) from exc
    return candidate


@router.get(
    "/api/v1/tools/story-planner/catalog",
    response_model=StoryPlannerCatalog,
)
@router.get(
    "/api/tools/story-planner/catalog",
    response_model=StoryPlannerCatalog,
)
async def story_planner_catalog() -> StoryPlannerCatalog:
    return load_story_planner_catalog()


@router.post(
    "/api/v1/tools/story-planner/plan",
    response_model=StoryPlannerPlanResponse,
)
@router.post(
    "/api/tools/story-planner/plan",
    response_model=StoryPlannerPlanResponse,
)
async def story_planner_plan(
    payload: StoryPlannerPlanRequest,
) -> StoryPlannerPlanResponse:
    try:
        return plan_story_episode(payload)
    except StoryPlannerValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.post(
    "/api/v1/tools/story-planner/generate-anchors",
    response_model=StoryPlannerAnchorQueueResponse,
)
@router.post(
    "/api/tools/story-planner/generate-anchors",
    response_model=StoryPlannerAnchorQueueResponse,
)
async def story_planner_generate_anchors(
    payload: StoryPlannerAnchorQueueRequest,
    request: Request,
) -> StoryPlannerAnchorQueueResponse:
    service = _get_generation_service(request)
    try:
        return await queue_story_planner_anchor_batch(
            payload.approved_plan,
            service,
            candidate_count=payload.candidate_count,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/api/tools/generate-caption")
async def generate_caption(image: UploadFile = File(...)) -> dict[str, str]:
    """Generate a short caption story and hashtags from an uploaded image."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an image",
        )

    image_bytes = await image.read()
    mime_type = image.content_type or "image/png"
    return await generate_caption_from_image_bytes(image_bytes, mime_type)


@router.post("/api/v1/tools/generate-caption-by-id")
@router.post("/api/tools/generate-caption-by-id")
async def generate_caption_by_id(payload: CaptionByIdRequest) -> dict[str, str]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, image_path FROM generations WHERE id = ?",
            (payload.generation_id,),
        )
        row = await cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation not found",
        )

    image_path = row.get("image_path")
    if not isinstance(image_path, str) or not image_path.strip():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found",
        )

    image_file_path = _resolve_generation_image_file_path(image_path)
    if not image_file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found",
        )

    try:
        image_bytes = image_file_path.read_bytes()
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read image file: {exc}",
        ) from exc

    mime_type = mime_type_from_image_path(image_file_path.name)
    return await generate_caption_from_image_bytes(image_bytes, mime_type)


def _build_prompt_batch_csv(response: PromptBatchGenerateResponse) -> bytes:
    csv_buffer = io.StringIO(newline="")
    writer = csv.writer(csv_buffer, delimiter="|")
    writer.writerow(
        [
            "Set_No",
            "Checkpoint",
            "LoRA_1",
            "Strength_1",
            "LoRA_2",
            "Strength_2",
            "LoRA_3",
            "Strength_3",
            "LoRA_4",
            "Strength_4",
            "Sampler",
            "Steps",
            "CFG",
            "Clip_Skip",
            "Resolution",
            "Positive_Prompt",
            "Negative_Prompt",
        ]
    )

    for row in response.rows:
        loras = row.loras[:4]
        padded_loras = loras + [None] * (4 - len(loras))
        resolution = f"{row.width}x{row.height}"
        writer.writerow(
            [
                row.set_no,
                row.checkpoint,
                padded_loras[0].filename if padded_loras[0] else "None",
                padded_loras[0].strength if padded_loras[0] else 0.0,
                padded_loras[1].filename if padded_loras[1] else "None",
                padded_loras[1].strength if padded_loras[1] else 0.0,
                padded_loras[2].filename if padded_loras[2] else "None",
                padded_loras[2].strength if padded_loras[2] else 0.0,
                padded_loras[3].filename if padded_loras[3] else "None",
                padded_loras[3].strength if padded_loras[3] else 0.0,
                row.sampler,
                row.steps,
                row.cfg,
                row.clip_skip if row.clip_skip is not None else "",
                resolution,
                row.positive_prompt,
                row.negative_prompt or "",
            ]
        )

    return f"\ufeff{csv_buffer.getvalue()}".encode("utf-8")


def _row_to_generation_create(
    row,
    *,
    scheduler: str,
) -> GenerationCreate:
    return GenerationCreate(
        prompt=row.positive_prompt,
        negative_prompt=row.negative_prompt,
        checkpoint=row.checkpoint,
        workflow_lane=None,
        loras=row.loras,
        steps=row.steps,
        cfg=row.cfg,
        width=row.width,
        height=row.height,
        sampler=row.sampler,
        scheduler=scheduler,
        clip_skip=row.clip_skip,
        tags=[f"prompt_batch_{row.set_no:03d}", row.series, row.codename],
        notes=f"Prompt factory batch row {row.set_no}: {row.codename}",
    )


@router.get(
    "/api/v1/tools/prompt-factory/capabilities",
    response_model=PromptFactoryCapabilitiesResponse,
)
@router.get(
    "/api/tools/prompt-factory/capabilities",
    response_model=PromptFactoryCapabilitiesResponse,
)
async def prompt_factory_capabilities() -> PromptFactoryCapabilitiesResponse:
    return get_prompt_factory_capabilities()


@router.post(
    "/api/v1/tools/prompt-factory/generate",
    response_model=PromptBatchGenerateResponse,
)
@router.post(
    "/api/tools/prompt-factory/generate",
    response_model=PromptBatchGenerateResponse,
)
async def prompt_factory_generate(
    payload: PromptBatchGenerateRequest,
) -> PromptBatchGenerateResponse:
    return await generate_prompt_batch(payload)


@router.post(
    "/api/v1/tools/prompt-factory/generate-and-queue",
    response_model=PromptBatchQueueResponse,
)
@router.post(
    "/api/tools/prompt-factory/generate-and-queue",
    response_model=PromptBatchQueueResponse,
)
async def prompt_factory_generate_and_queue(
    payload: PromptBatchGenerateRequest,
    request: Request,
) -> PromptBatchQueueResponse:
    prompt_batch = await generate_prompt_batch(payload)
    service = _get_generation_service(request)
    queued_generations = []
    for row in prompt_batch.rows:
        generation = _row_to_generation_create(
            row,
            scheduler=prompt_batch.benchmark.scheduler,
        )
        queued_generations.append(await service.queue_generation(generation))
    return PromptBatchQueueResponse(
        prompt_batch=prompt_batch,
        queued_generations=queued_generations,
    )


@router.post(
    "/api/v1/tools/prompt-factory/queue",
    response_model=PromptBatchQueueResponse,
)
@router.post(
    "/api/tools/prompt-factory/queue",
    response_model=PromptBatchQueueResponse,
)
async def prompt_factory_queue_existing(
    payload: PromptBatchGenerateResponse,
    request: Request,
) -> PromptBatchQueueResponse:
    service = _get_generation_service(request)
    queued_generations = []
    for row in payload.rows:
        generation = _row_to_generation_create(
            row,
            scheduler=payload.benchmark.scheduler,
        )
        queued_generations.append(await service.queue_generation(generation))
    return PromptBatchQueueResponse(
        prompt_batch=payload,
        queued_generations=queued_generations,
    )


@router.post("/api/v1/tools/prompt-factory/generate.csv")
@router.post("/api/tools/prompt-factory/generate.csv")
async def prompt_factory_generate_csv(
    payload: PromptBatchGenerateRequest,
) -> StreamingResponse:
    response = await generate_prompt_batch(payload)
    csv_payload = _build_prompt_batch_csv(response)
    return StreamingResponse(
        content=iter([csv_payload]),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                'attachment; filename="hollowforge_prompt_batch.csv"'
            )
        },
    )
