"""Seedance API routes."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from app.services.seedance_service import SeedanceService

router = APIRouter(prefix="/api/v1/seedance", tags=["seedance"])


def _get_service(request: Request) -> SeedanceService:
    service = getattr(request.app.state, "seedance_service", None)
    if isinstance(service, SeedanceService):
        return service
    return SeedanceService()


def _parse_image_ids(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return values or None


@router.post("/jobs")
async def create_seedance_job(
    request: Request,
    prompt: str = Form(...),
    duration_sec: int = Form(8),
    image_ids: str | None = Form(default=None),
    image_files: list[UploadFile] | None = File(default=None),
    video_files: list[UploadFile] | None = File(default=None),
    audio_files: list[UploadFile] | None = File(default=None),
) -> dict[str, str]:
    """Submit a Seedance generation job."""
    service = _get_service(request)
    uploaded_files = [*(image_files or []), *(video_files or []), *(audio_files or [])]

    try:
        job_id = await service.submit_seedance_job(
            prompt=prompt,
            duration=duration_sec,
            image_ids=_parse_image_ids(image_ids),
            uploaded_files=uploaded_files,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {"job_id": job_id, "status": "processing"}


@router.get("/jobs/{job_id}")
async def get_seedance_job(
    job_id: str,
    request: Request,
) -> dict[str, object]:
    """Poll and return Seedance job status."""
    service = _get_service(request)
    try:
        return await service.poll_seedance_job(job_id)
    except ValueError as exc:
        message = str(exc)
        error_status = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=error_status, detail=message) from exc


@router.get("/jobs")
async def list_seedance_jobs(request: Request) -> list[dict[str, object]]:
    """List recent Seedance jobs (latest 20)."""
    service = _get_service(request)
    return await service.list_recent_jobs(limit=20)


@router.delete("/jobs/{job_id}")
async def delete_seedance_job(
    job_id: str,
    request: Request,
) -> dict[str, bool]:
    """Delete a Seedance job and associated output file."""
    service = _get_service(request)
    deleted = await service.delete_job(job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seedance job {job_id} not found",
        )
    return {"success": True}
