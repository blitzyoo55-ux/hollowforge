"""DreamActor API routes."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from app.services.dreamactor_service import DreamActorService

router = APIRouter(prefix="/api/v1/generations", tags=["dreamactor"])


def _get_service(request: Request) -> DreamActorService:
    service = getattr(request.app.state, "dreamactor_service", None)
    if isinstance(service, DreamActorService):
        return service
    return DreamActorService()


@router.post("/{generation_id}/dreamactor")
async def submit_dreamactor_task(
    generation_id: str,
    request: Request,
    template_video: UploadFile = File(...),
) -> dict[str, str]:
    """Submit a DreamActor motion-driving task from generation + template video."""
    service = _get_service(request)
    video_bytes = await template_video.read()

    try:
        task_id = await service.submit_dreamactor_task(
            generation_id=generation_id,
            template_video_bytes=video_bytes,
            template_filename=template_video.filename or "template.mp4",
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        message = str(exc)
        error_status = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=error_status, detail=message) from exc

    return {"task_id": task_id, "status": "processing"}


@router.get("/{generation_id}/dreamactor/status")
async def get_dreamactor_status(
    generation_id: str,
    request: Request,
) -> dict[str, object]:
    """Poll DreamActor status and return latest status/progress/video URL."""
    service = _get_service(request)
    state = await service.get_generation_dreamactor_state(generation_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Generation {generation_id} not found",
        )

    task_id = state.get("dreamactor_task_id")
    dreamactor_path = state.get("dreamactor_path")
    dreamactor_status = state.get("dreamactor_status")

    if isinstance(dreamactor_path, str) and dreamactor_path:
        return {
            "status": "succeeded",
            "progress": 100,
            "video_url": f"/data/{dreamactor_path}",
            "dreamactor_path": dreamactor_path,
        }

    if not isinstance(task_id, str) or not task_id:
        return {
            "status": str(dreamactor_status or "idle"),
            "progress": 0,
            "video_url": None,
            "dreamactor_path": None,
        }

    try:
        return await service.poll_dreamactor_task(generation_id, task_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
