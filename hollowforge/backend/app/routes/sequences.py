"""Sequence orchestration endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.models import (
    SequenceAnchorCandidateResponse,
    SequenceBlueprintCreate,
    SequenceBlueprintDetailResponse,
    SequenceContentMode,
    SequenceRoughCutCandidateResponse,
    SequenceRunCreateRequest,
    SequenceRunDetailResponse,
    SequenceRunShotDetailResponse,
    SequenceRunSummaryResponse,
    SequenceShotClipResponse,
    SequenceShotPlanResponse,
)
from app.services.generation_service import GenerationService
from app.services.rough_cut_service import RoughCutAssemblyError, RoughCutService
from app.services.sequence_blueprint_service import expand_blueprint_into_shots
from app.services.sequence_registry import (
    SequenceRegistryError,
    get_animation_executor_profile,
)
from app.services.sequence_repository import (
    create_blueprint,
    get_blueprint,
    get_run,
    list_anchor_candidates,
    list_blueprints,
    list_rough_cuts,
    list_runs,
    list_shot_clips,
    list_shots,
)
from app.services.sequence_run_service import SequenceRunService

router = APIRouter(prefix="/api/v1/sequences", tags=["sequences"])


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _planned_shots_for_blueprint(
    *,
    beat_grammar_id: str,
    target_duration_sec: int,
    shot_count: int,
    content_mode: SequenceContentMode,
) -> list[SequenceShotPlanResponse]:
    return [
        SequenceShotPlanResponse.model_validate(shot)
        for shot in expand_blueprint_into_shots(
            beat_grammar_id=beat_grammar_id,
            target_duration_sec=target_duration_sec,
            shot_count=shot_count,
            content_mode=content_mode,
        )
    ]


def _blueprint_detail_response(blueprint) -> SequenceBlueprintDetailResponse:
    return SequenceBlueprintDetailResponse(
        blueprint=blueprint,
        planned_shots=_planned_shots_for_blueprint(
            beat_grammar_id=blueprint.beat_grammar_id,
            target_duration_sec=blueprint.target_duration_sec,
            shot_count=blueprint.shot_count,
            content_mode=blueprint.content_mode,
        ),
    )


def _get_generation_service(request: Request) -> GenerationService:
    service = getattr(request.app.state, "generation_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Generation service is unavailable",
        )
    return service


async def _build_run_detail_response(run_id: str) -> SequenceRunDetailResponse:
    run = await get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence run not found")

    blueprint = await get_blueprint(run.sequence_blueprint_id)
    if blueprint is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sequence blueprint missing for run",
        )

    shot_details: list[SequenceRunShotDetailResponse] = []
    for shot in await list_shots(run.id):
        shot_details.append(
            SequenceRunShotDetailResponse(
                shot=shot,
                anchor_candidates=[
                    SequenceAnchorCandidateResponse.model_validate(candidate)
                    for candidate in await list_anchor_candidates(shot.id)
                ],
                clips=[
                    SequenceShotClipResponse.model_validate(clip)
                    for clip in await list_shot_clips(shot.id)
                ],
            )
        )

    rough_cut_candidates = [
        SequenceRoughCutCandidateResponse(
            rough_cut=rough_cut,
            is_selected=rough_cut.id == run.selected_rough_cut_id,
        )
        for rough_cut in await list_rough_cuts(run.id)
    ]

    return SequenceRunDetailResponse(
        run=run,
        blueprint=blueprint,
        shots=shot_details,
        rough_cut_candidates=rough_cut_candidates,
    )


@router.post(
    "/blueprints",
    response_model=SequenceBlueprintDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sequence_blueprint(
    payload: SequenceBlueprintCreate,
) -> SequenceBlueprintDetailResponse:
    try:
        get_animation_executor_profile(
            payload.executor_policy,
            content_mode=payload.content_mode,
        )
        _planned_shots_for_blueprint(
            beat_grammar_id=payload.beat_grammar_id,
            target_duration_sec=payload.target_duration_sec,
            shot_count=payload.shot_count,
            content_mode=payload.content_mode,
        )
    except (SequenceRegistryError, ValueError) as exc:
        raise _bad_request(str(exc)) from exc

    blueprint = await create_blueprint(payload)
    return _blueprint_detail_response(blueprint)


@router.get("/blueprints", response_model=list[SequenceBlueprintDetailResponse])
async def list_sequence_blueprints(
    content_mode: Optional[SequenceContentMode] = Query(default=None),
    policy_profile_id: Optional[str] = Query(default=None),
    production_episode_id: Optional[str] = Query(default=None),
) -> list[SequenceBlueprintDetailResponse]:
    blueprints = await list_blueprints(
        content_mode=content_mode,
        policy_profile_id=policy_profile_id,
        production_episode_id=production_episode_id,
    )
    return [_blueprint_detail_response(blueprint) for blueprint in blueprints]


@router.post(
    "/runs",
    response_model=SequenceRunDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sequence_run(
    payload: SequenceRunCreateRequest,
    request: Request,
) -> SequenceRunDetailResponse:
    service = SequenceRunService(_get_generation_service(request))
    try:
        result = await service.create_run_from_blueprint(
            blueprint_id=payload.sequence_blueprint_id,
            prompt_provider_profile_id=payload.prompt_provider_profile_id,
            candidate_count=payload.candidate_count,
            target_tool=payload.target_tool,
        )
    except SequenceRegistryError as exc:
        raise _bad_request(str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("Unknown sequence blueprint:"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise _bad_request(detail) from exc

    return await _build_run_detail_response(result["run"].id)


@router.get("/runs", response_model=list[SequenceRunSummaryResponse])
async def list_sequence_runs(
    sequence_blueprint_id: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
) -> list[SequenceRunSummaryResponse]:
    runs = await list_runs(
        sequence_blueprint_id=sequence_blueprint_id,
        status=status_filter,
    )
    summaries: list[SequenceRunSummaryResponse] = []
    for run in runs:
        shot_rows = await list_shots(run.id)
        rough_cut_rows = await list_rough_cuts(run.id)
        summaries.append(
            SequenceRunSummaryResponse(
                run=run,
                shot_count=len(shot_rows),
                rough_cut_candidate_count=len(rough_cut_rows),
            )
        )
    return summaries


@router.get("/runs/{run_id}", response_model=SequenceRunDetailResponse)
async def get_sequence_run(run_id: str) -> SequenceRunDetailResponse:
    return await _build_run_detail_response(run_id)


@router.post("/runs/{run_id}/start", response_model=SequenceRunDetailResponse)
async def start_sequence_run(run_id: str) -> SequenceRunDetailResponse:
    service = RoughCutService()
    try:
        await service.assemble(sequence_run_id=run_id)
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("Unknown sequence run:"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from exc
        raise _bad_request(detail) from exc
    except RoughCutAssemblyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return await _build_run_detail_response(run_id)
