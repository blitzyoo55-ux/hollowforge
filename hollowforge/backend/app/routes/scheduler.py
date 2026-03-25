"""Scheduler CRUD and run-now endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.models import ScheduledJobCreate, ScheduledJobResponse, ScheduledJobUpdate
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/api/v1/scheduler", tags=["scheduler"])


def _get_service(request: Request) -> SchedulerService:
    return request.app.state.scheduler_service


@router.get("/jobs", response_model=list[ScheduledJobResponse])
async def list_jobs(request: Request) -> list[ScheduledJobResponse]:
    service = _get_service(request)
    rows = await service.list_jobs()
    return [ScheduledJobResponse(**row) for row in rows]


@router.post(
    "/jobs",
    response_model=ScheduledJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    payload: ScheduledJobCreate, request: Request
) -> ScheduledJobResponse:
    service = _get_service(request)
    try:
        row = await service.add_or_update_job(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ScheduledJobResponse(**row)


@router.put("/jobs/{job_id}", response_model=ScheduledJobResponse)
async def update_job(
    job_id: str,
    payload: ScheduledJobUpdate,
    request: Request,
) -> ScheduledJobResponse:
    service = _get_service(request)
    data = payload.model_dump(exclude_unset=True)
    data["id"] = job_id
    try:
        row = await service.add_or_update_job(data)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ScheduledJobResponse(**row)


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request) -> dict[str, bool]:
    service = _get_service(request)
    deleted = await service.delete_job(job_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled job {job_id} not found",
        )
    return {"success": True}


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str, request: Request) -> dict[str, object]:
    service = _get_service(request)
    try:
        return await service.run_now(job_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
