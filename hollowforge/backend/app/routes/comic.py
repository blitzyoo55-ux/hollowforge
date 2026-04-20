"""Comic foundation endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from app.config import settings
from app.models import (
    AnimationJobCallbackPayload,
    ComicCharacterResponse,
    ComicDialogueGenerationResponse,
    ComicCharacterVersionResponse,
    ComicEpisodeCreate,
    ComicEpisodeDetailResponse,
    ComicEpisodeStatus,
    ComicManuscriptProfileId,
    ComicManuscriptProfileResponse,
    ComicEpisodeSummaryResponse,
    ComicPageAssemblyBatchResponse,
    ComicPageExportResponse,
    ComicPanelRenderAssetResponse,
    ComicRenderExecutionMode,
    ComicRenderJobResponse,
    ComicPanelRenderQueueResponse,
    ComicStoryPlanImportRequest,
    ComicPageLayoutTemplateId,
    StoryPlannerPlanResponse,
    list_comic_manuscript_profiles,
)
from app.services.comic_dialogue_service import generate_panel_dialogues
from app.services.comic_page_assembly_service import (
    assemble_episode_pages,
    export_episode_pages,
)
from app.services.comic_repository import (
    create_comic_episode_from_draft,
    create_comic_episode,
    get_comic_episode_detail,
    list_comic_characters,
    list_comic_character_versions,
    list_comic_episodes,
    resolve_comic_character_context_for_version,
)
from app.services.comic_render_service import (
    list_panel_render_jobs,
    materialize_remote_render_job_callback,
    queue_panel_render_candidates,
    select_panel_render_asset,
)
from app.services.comic_story_bridge_service import build_comic_draft_from_story_plan

router = APIRouter(prefix="/api/v1/comic", tags=["comic"])


def _content_mode_from_story_lane(lane: str) -> str:
    if lane == "adult_nsfw":
        return "adult_nsfw"
    return "all_ages"


def _validate_story_plan_character_alignment(
    approved_plan: StoryPlannerPlanResponse,
    *,
    selected_character_id: str,
    selected_character_slug: str,
) -> None:
    registry_lead = next(
        (
            member
            for member in approved_plan.resolved_cast
            if member.role == "lead"
            and member.source_type == "registry"
            and member.character_id
        ),
        None,
    )
    if registry_lead is None:
        return

    allowed_ids = {selected_character_id, selected_character_slug}
    if registry_lead.character_id not in allowed_ids:
        raise ValueError(
            "approved_plan registry lead "
            f"{registry_lead.character_id} conflicts with selected comic character "
            f"{selected_character_id} ({selected_character_slug})"
        )


def _bind_selected_character_to_draft(
    *,
    draft,
    selected_character_id: str,
) -> None:
    for scene in draft.scenes:
        scene.involved_character_ids = [
            selected_character_id,
            *[
                character_id
                for character_id in scene.involved_character_ids
                if character_id != selected_character_id
            ],
        ]


def _http_error_from_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code = (
        status.HTTP_404_NOT_FOUND
        if "not found" in detail.lower()
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=status_code, detail=detail)


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "bearer "
    value = authorization.strip()
    if value.lower().startswith(prefix):
        return value[len(prefix):].strip()
    return None


def _get_generation_service(request: Request):
    service = getattr(request.app.state, "generation_service", None)
    if service is None:
        raise RuntimeError("Generation service is not configured")
    return service


@router.get("/characters", response_model=list[ComicCharacterResponse])
async def get_comic_characters() -> list[ComicCharacterResponse]:
    return await list_comic_characters()


@router.get(
    "/manuscript-profiles",
    response_model=list[ComicManuscriptProfileResponse],
)
async def get_comic_manuscript_profiles() -> list[ComicManuscriptProfileResponse]:
    return list_comic_manuscript_profiles()


@router.get(
    "/character-versions",
    response_model=list[ComicCharacterVersionResponse],
)
async def get_comic_character_versions(
    character_id: str | None = Query(default=None),
) -> list[ComicCharacterVersionResponse]:
    return await list_comic_character_versions(character_id=character_id)


@router.post(
    "/episodes",
    response_model=ComicEpisodeDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comic_episode_endpoint(
    payload: ComicEpisodeCreate,
) -> ComicEpisodeDetailResponse:
    try:
        episode = await create_comic_episode(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    detail = await get_comic_episode_detail(episode.id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comic episode detail missing after create",
        )
    return detail


@router.post(
    "/episodes/import-story-plan",
    response_model=ComicEpisodeDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_story_plan(
    payload: ComicStoryPlanImportRequest,
) -> ComicEpisodeDetailResponse:
    try:
        character_id, character_slug = await resolve_comic_character_context_for_version(
            payload.character_version_id
        )
        _validate_story_plan_character_alignment(
            payload.approved_plan,
            selected_character_id=character_id,
            selected_character_slug=character_slug,
        )
        draft = build_comic_draft_from_story_plan(
            approved_plan=payload.approved_plan,
            character_version_id=payload.character_version_id,
            title=payload.title,
            panel_multiplier=payload.panel_multiplier,
        )
        content_mode = payload.content_mode or _content_mode_from_story_lane(
            payload.approved_plan.lane
        )
        draft = draft.model_copy(
            update={
                "content_mode": content_mode,
                "work_id": payload.work_id,
                "series_id": payload.series_id,
                "production_episode_id": payload.production_episode_id,
            }
        )
        _bind_selected_character_to_draft(
            draft=draft,
            selected_character_id=character_id,
        )
        return await create_comic_episode_from_draft(
            character_id=character_id,
            draft=draft,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/episodes", response_model=list[ComicEpisodeSummaryResponse])
async def get_comic_episodes(
    character_id: str | None = Query(default=None),
    status_filter: ComicEpisodeStatus | None = Query(default=None, alias="status"),
    production_episode_id: str | None = Query(default=None),
) -> list[ComicEpisodeSummaryResponse]:
    return await list_comic_episodes(
        character_id=character_id,
        status=status_filter,
        production_episode_id=production_episode_id,
    )


@router.get("/episodes/{episode_id}", response_model=ComicEpisodeDetailResponse)
async def get_comic_episode(episode_id: str) -> ComicEpisodeDetailResponse:
    detail = await get_comic_episode_detail(episode_id)
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comic episode not found",
        )
    return detail


@router.post(
    "/panels/{panel_id}/queue-renders",
    response_model=ComicPanelRenderQueueResponse,
)
async def queue_comic_panel_render_candidates(
    panel_id: str,
    request: Request,
    candidate_count: int = Query(default=3, ge=2, le=24),
    execution_mode: ComicRenderExecutionMode = Query(default="local_preview"),
) -> ComicPanelRenderQueueResponse:
    try:
        return await queue_panel_render_candidates(
            panel_id=panel_id,
            generation_service=_get_generation_service(request),
            candidate_count=candidate_count,
            execution_mode=execution_mode,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.get(
    "/panels/{panel_id}/render-jobs",
    response_model=list[ComicRenderJobResponse],
)
async def get_comic_panel_render_jobs(panel_id: str) -> list[ComicRenderJobResponse]:
    try:
        return await list_panel_render_jobs(panel_id=panel_id)
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.post(
    "/render-jobs/{job_id}/callback",
    response_model=ComicRenderJobResponse,
)
async def callback_comic_render_job(
    job_id: str,
    payload: AnimationJobCallbackPayload,
    authorization: str | None = Header(default=None),
) -> ComicRenderJobResponse:
    expected_token = settings.ANIMATION_CALLBACK_TOKEN
    if expected_token:
        actual_token = _extract_bearer_token(authorization)
        if actual_token != expected_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid comic render callback token",
            )
    try:
        return await materialize_remote_render_job_callback(
            job_id=job_id,
            payload=payload,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.post(
    "/panels/{panel_id}/assets/{asset_id}/select",
    response_model=ComicPanelRenderAssetResponse,
)
async def select_comic_panel_render_asset_endpoint(
    panel_id: str,
    asset_id: str,
) -> ComicPanelRenderAssetResponse:
    try:
        return await select_panel_render_asset(panel_id=panel_id, asset_id=asset_id)
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.post(
    "/panels/{panel_id}/dialogues/generate",
    response_model=ComicDialogueGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_comic_panel_dialogues_endpoint(
    panel_id: str,
    overwrite_existing: bool = Query(default=False),
) -> ComicDialogueGenerationResponse:
    try:
        return await generate_panel_dialogues(
            panel_id=panel_id,
            overwrite_existing=overwrite_existing,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.post(
    "/episodes/{episode_id}/pages/assemble",
    response_model=ComicPageAssemblyBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assemble_comic_episode_pages_endpoint(
    episode_id: str,
    layout_template_id: ComicPageLayoutTemplateId = Query(default="jp_2x2_v1"),
    manuscript_profile_id: ComicManuscriptProfileId = Query(
        default="jp_manga_rightbound_v1"
    ),
) -> ComicPageAssemblyBatchResponse:
    try:
        return await assemble_episode_pages(
            episode_id=episode_id,
            layout_template_id=layout_template_id,
            manuscript_profile_id=manuscript_profile_id,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc


@router.post(
    "/episodes/{episode_id}/pages/export",
    response_model=ComicPageExportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def export_comic_episode_pages_endpoint(
    episode_id: str,
    layout_template_id: ComicPageLayoutTemplateId = Query(default="jp_2x2_v1"),
    manuscript_profile_id: ComicManuscriptProfileId = Query(
        default="jp_manga_rightbound_v1"
    ),
) -> ComicPageExportResponse:
    try:
        return await export_episode_pages(
            episode_id=episode_id,
            layout_template_id=layout_template_id,
            manuscript_profile_id=manuscript_profile_id,
        )
    except ValueError as exc:
        raise _http_error_from_value_error(exc) from exc
