"""Production hub endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.models import (
    ProductionEpisodeCreate,
    ProductionEpisodeDetailResponse,
    ProductionSeriesCreate,
    ProductionSeriesResponse,
    ProductionWorkCreate,
    ProductionWorkResponse,
)
from app.services.production_hub_repository import (
    create_production_episode,
    create_series,
    create_work,
    get_production_episode_detail,
    list_series,
    list_works,
    list_production_episodes,
)

router = APIRouter(prefix="/api/v1/production", tags=["production"])


def _http_error_from_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = (
        status.HTTP_404_NOT_FOUND
        if "unknown" in detail.lower() or "not found" in detail.lower()
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=status_code, detail=detail)


@router.post("/works", response_model=ProductionWorkResponse, status_code=status.HTTP_201_CREATED)
async def create_work_endpoint(payload: ProductionWorkCreate) -> ProductionWorkResponse:
    try:
        return await create_work(payload)
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.get("/works", response_model=list[ProductionWorkResponse])
async def list_works_endpoint() -> list[ProductionWorkResponse]:
    return await list_works()


@router.post("/series", response_model=ProductionSeriesResponse, status_code=status.HTTP_201_CREATED)
async def create_series_endpoint(payload: ProductionSeriesCreate) -> ProductionSeriesResponse:
    try:
        return await create_series(payload)
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.get("/series", response_model=list[ProductionSeriesResponse])
async def list_series_endpoint(
    work_id: Optional[str] = Query(default=None),
) -> list[ProductionSeriesResponse]:
    return await list_series(work_id=work_id)


@router.post(
    "/episodes",
    response_model=ProductionEpisodeDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_production_episode_endpoint(
    payload: ProductionEpisodeCreate,
) -> ProductionEpisodeDetailResponse:
    try:
        return await create_production_episode(payload)
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.get("/episodes", response_model=list[ProductionEpisodeDetailResponse])
async def list_production_episodes_endpoint(
    work_id: Optional[str] = Query(default=None),
) -> list[ProductionEpisodeDetailResponse]:
    return await list_production_episodes(work_id=work_id)


@router.get("/episodes/{production_episode_id}", response_model=ProductionEpisodeDetailResponse)
async def get_production_episode_endpoint(
    production_episode_id: str,
) -> ProductionEpisodeDetailResponse:
    detail = await get_production_episode_detail(production_episode_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Production episode not found",
        )
    return detail
