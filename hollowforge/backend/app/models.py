"""Pydantic v2 request / response models."""

from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.services.workflow_registry import infer_workflow_lane


MAX_GENERATION_STEPS = 150
MAX_GENERATION_CFG = 30.0
MIN_GENERATION_DIM = 256
MAX_GENERATION_DIM = 1536
MAX_GENERATION_PIXELS = 2_359_296  # 1536 * 1536
WATERMARK_COLOR_REGEX = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"
WatermarkPosition = Literal[
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "center",
]
AnimationTargetTool = Literal[
    "dreamactor",
    "seedance",
    "wan_i2v",
    "hunyuan_avatar",
    "custom",
]
AnimationExecutorMode = Literal["local", "remote_worker", "managed_api"]
PromptFactoryCheckpointPreferenceMode = Literal[
    "default",
    "prefer",
    "force",
    "exclude",
]
SequenceContentMode = Literal["all_ages", "adult_nsfw"]
StoryPlannerLane = Literal["unrestricted", "all_ages", "adult_nsfw"]
ComicEpisodeStatus = Literal["draft", "planned", "in_production", "released"]
ComicTargetOutput = Literal["oneshot_manga", "serial_episode", "teaser_animation"]
ComicPanelType = Literal["splash", "establish", "beat", "insert", "closeup", "transition"]
ComicDialogueType = Literal["speech", "thought", "caption", "sfx"]
ComicRenderAssetRole = Literal["candidate", "selected", "derived_preview", "final_master"]
ComicRenderExecutionMode = Literal["local_preview", "remote_worker"]
ComicPageExportState = Literal["draft", "preview_ready", "exported"]
ComicPageLayoutTemplateId = Literal["jp_2x2_v1", "jp_3row_v1"]
ComicManuscriptProfileId = Literal["jp_manga_rightbound_v1"]
ComicRenderLane = Literal["legacy", "character_canon_v2"]
ProductionFormatFamily = Literal["comic", "animation", "mixed"]
ProductionDeliveryMode = Literal["oneshot", "serial", "anthology"]
ProductionTargetOutput = Literal["comic", "animation"]


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

class LoraInput(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    strength: float = Field(ge=-2.0, le=2.0)
    category: Optional[str] = None


class GenerationCreate(BaseModel):
    prompt: str
    negative_prompt: Optional[str] = None
    preserve_blank_negative_prompt: bool = False
    checkpoint: str
    workflow_lane: Optional[Literal["classic_clip", "sdxl_illustrious"]] = None
    loras: List[LoraInput] = Field(default_factory=list)
    seed: Optional[int] = Field(
        default=None,
        description="Auto-random if None",
        ge=-1,
        le=2**31 - 1,
    )
    steps: int = Field(default=28, ge=1, le=MAX_GENERATION_STEPS)
    cfg: float = Field(default=7.0, ge=1.0, le=MAX_GENERATION_CFG)
    width: int = Field(default=832, ge=MIN_GENERATION_DIM, le=MAX_GENERATION_DIM)
    height: int = Field(default=1216, ge=MIN_GENERATION_DIM, le=MAX_GENERATION_DIM)
    sampler: str = "euler"
    scheduler: str = "normal"
    clip_skip: Optional[int] = Field(default=None, ge=1, le=12)
    tags: Optional[List[str]] = None
    preset_id: Optional[str] = None
    notes: Optional[str] = None
    source_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_generation_shape(self) -> "GenerationCreate":
        # Keep requests on practical bounds for single-device inference.
        if self.width % 8 != 0 or self.height % 8 != 0:
            raise ValueError("width and height must be multiples of 8")
        if self.width * self.height > MAX_GENERATION_PIXELS:
            raise ValueError(
                f"width * height must be <= {MAX_GENERATION_PIXELS} pixels"
            )
        if (
            self.preserve_blank_negative_prompt
            and isinstance(self.negative_prompt, str)
            and self.negative_prompt.strip()
        ):
            raise ValueError(
                "preserve_blank_negative_prompt requires negative_prompt to be blank"
            )
        return self

    def resolved_seed(self) -> int:
        if self.seed is None or self.seed == -1:
            return random.randint(0, 2**31 - 1)
        return self.seed


class GenerationBatchCreate(BaseModel):
    generation: GenerationCreate
    count: int = Field(
        default=4,
        ge=2,
        le=24,
        description="Number of images to queue with auto-incremented seeds",
    )
    seed_increment: int = Field(
        default=1,
        ge=1,
        le=9999,
        description="Increment added to seed for each batch item",
    )


class BenchmarkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    prompt: str
    negative_prompt: Optional[str] = None
    loras: List[LoraInput] = Field(default_factory=list)
    steps: int = Field(default=28, ge=1, le=MAX_GENERATION_STEPS)
    cfg: float = Field(default=7.0, ge=1.0, le=MAX_GENERATION_CFG)
    width: int = Field(default=832, ge=MIN_GENERATION_DIM, le=MAX_GENERATION_DIM)
    height: int = Field(default=1216, ge=MIN_GENERATION_DIM, le=MAX_GENERATION_DIM)
    sampler: str = "euler"
    scheduler: str = "normal"
    seed: Optional[int] = Field(default=None, ge=-1, le=2**31 - 1)
    checkpoints: List[str] = Field(min_length=2, max_length=10)

    @model_validator(mode="after")
    def validate_benchmark_shape(self) -> "BenchmarkCreate":
        if self.width % 8 != 0 or self.height % 8 != 0:
            raise ValueError("width and height must be multiples of 8")
        if self.width * self.height > MAX_GENERATION_PIXELS:
            raise ValueError(
                f"width * height must be <= {MAX_GENERATION_PIXELS} pixels"
            )
        return self


class PresetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    checkpoint: str
    loras: List[LoraInput] = Field(default_factory=list)
    prompt_template: Optional[str] = None
    negative_prompt: Optional[str] = None
    default_params: Dict[str, Any] = Field(default_factory=dict)
    tags: Optional[List[str]] = None


class PresetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    checkpoint: Optional[str] = None
    loras: Optional[List[LoraInput]] = None
    prompt_template: Optional[str] = None
    negative_prompt: Optional[str] = None
    default_params: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class ScheduledJobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    preset_id: str
    count: int = Field(default=4, ge=1, le=24)
    cron_hour: int = Field(default=2, ge=0, le=23)
    cron_minute: int = Field(default=0, ge=0, le=59)
    enabled: bool = True


class ScheduledJobUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    preset_id: Optional[str] = None
    count: Optional[int] = Field(default=None, ge=1, le=24)
    cron_hour: Optional[int] = Field(default=None, ge=0, le=23)
    cron_minute: Optional[int] = Field(default=None, ge=0, le=59)
    enabled: Optional[bool] = None


class LoraProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    filename: str = Field(min_length=1, max_length=255)
    category: Literal["style", "eyes", "material", "fetish"]
    default_strength: float = Field(default=0.7, ge=-2.0, le=2.0)
    tags: Optional[str] = None
    notes: Optional[str] = None
    compatible_checkpoints: Optional[List[str]] = None


class LoraProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    category: Optional[Literal["style", "eyes", "material", "fetish"]] = None
    default_strength: Optional[float] = Field(default=None, ge=-2.0, le=2.0)
    tags: Optional[str] = None
    notes: Optional[str] = None
    compatible_checkpoints: Optional[List[str]] = None


class MoodMappingCreate(BaseModel):
    mood_keyword: str = Field(min_length=1, max_length=60)
    lora_ids: List[str] = Field(default_factory=list)
    prompt_additions: str = ""


class MoodMappingUpdate(BaseModel):
    mood_keyword: Optional[str] = Field(default=None, min_length=1, max_length=60)
    lora_ids: Optional[List[str]] = None
    prompt_additions: Optional[str] = None


class MoodSelectRequest(BaseModel):
    moods: List[str]
    checkpoint: Optional[str] = None


class GalleryQuery(BaseModel):
    page: int = 1
    per_page: int = 20
    checkpoint: Optional[str] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    favorites: bool = False
    sort_by: str = "created_at"
    sort_order: str = "desc"


class ExportRequest(BaseModel):
    generation_ids: List[str] = Field(min_length=1, max_length=100)
    platform: Literal["fanbox", "fansly", "twitter", "pixiv", "custom"] = "fanbox"
    apply_watermark: bool = True
    include_originals: bool = False


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    cover_image_id: Optional[str] = None


class CollectionItemRequest(BaseModel):
    generation_id: str = Field(min_length=1, max_length=255)


class ReproduceRequest(BaseModel):
    mode: Literal["exact", "variation"]
    seed: Optional[int] = None
    notes: Optional[str] = None


class UpscaleRequest(BaseModel):
    upscale_model: str = "auto"
    mode: Literal["safe", "quality"] = "safe"
    denoise: float = Field(default=0.35, ge=0.0, le=1.0)
    steps: int = Field(default=20, ge=1, le=MAX_GENERATION_STEPS)


class ADetailRequest(BaseModel):
    denoise: float = Field(default=0.4, ge=0.05, le=0.9)
    steps: int = Field(default=20, ge=1, le=MAX_GENERATION_STEPS)


class HiresFixRequest(BaseModel):
    upscale_factor: float = Field(default=1.5, ge=1.1, le=2.0)
    denoise: float = Field(default=0.5, ge=0.2, le=0.85)
    steps: int = Field(default=20, ge=1, le=MAX_GENERATION_STEPS)
    cfg: float = Field(default=7.0, ge=1.0, le=MAX_GENERATION_CFG)


class ComfyUIConfigUpdate(BaseModel):
    url: str


class WatermarkSettingsUpdate(BaseModel):
    enabled: bool
    text: str = Field(min_length=1, max_length=120)
    position: WatermarkPosition
    opacity: float = Field(ge=0.1, le=1.0)
    font_size: int = Field(ge=20, le=72)
    padding: int = Field(ge=0, le=200)
    color: str = Field(pattern=WATERMARK_COLOR_REGEX)


class ComicEpisodeBase(BaseModel):
    model_config = {"extra": "forbid"}

    character_id: str = Field(min_length=1, max_length=120)
    character_version_id: str = Field(min_length=1, max_length=120)
    content_mode: SequenceContentMode = "all_ages"
    work_id: Optional[str] = Field(default=None, max_length=120)
    series_id: Optional[str] = Field(default=None, max_length=120)
    production_episode_id: Optional[str] = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    synopsis: str = Field(min_length=1, max_length=4000)
    source_story_plan_json: Optional[str] = None
    status: ComicEpisodeStatus = "draft"
    continuity_summary: Optional[str] = Field(default=None, max_length=4000)
    canon_delta: Optional[str] = Field(default=None, max_length=4000)
    target_output: ComicTargetOutput = "oneshot_manga"


class ComicEpisodeCreate(ComicEpisodeBase):
    pass


class ComicEpisodeSceneBase(BaseModel):
    episode_id: str = Field(min_length=1, max_length=120)
    scene_no: int = Field(ge=1, le=999)
    premise: str = Field(min_length=1, max_length=2000)
    location_label: Optional[str] = Field(default=None, max_length=240)
    tension: Optional[str] = Field(default=None, max_length=1000)
    reveal: Optional[str] = Field(default=None, max_length=1000)
    continuity_notes: Optional[str] = Field(default=None, max_length=4000)
    involved_character_ids: List[str] = Field(default_factory=list, max_length=16)
    target_panel_count: Optional[int] = Field(default=None, ge=1, le=64)


class ComicEpisodeSceneCreate(ComicEpisodeSceneBase):
    pass


class ComicScenePanelBase(BaseModel):
    episode_scene_id: str = Field(min_length=1, max_length=120)
    panel_no: int = Field(ge=1, le=999)
    panel_type: ComicPanelType = "beat"
    framing: Optional[str] = Field(default=None, max_length=240)
    camera_intent: Optional[str] = Field(default=None, max_length=500)
    action_intent: Optional[str] = Field(default=None, max_length=500)
    expression_intent: Optional[str] = Field(default=None, max_length=500)
    dialogue_intent: Optional[str] = Field(default=None, max_length=1000)
    continuity_lock: Optional[str] = Field(default=None, max_length=4000)
    page_target_hint: Optional[int] = Field(default=None, ge=1, le=999)
    reading_order: int = Field(ge=1, le=999)


class ComicScenePanelCreate(ComicScenePanelBase):
    pass


class ComicPanelDialogueBase(BaseModel):
    scene_panel_id: str = Field(min_length=1, max_length=120)
    type: ComicDialogueType
    speaker_character_id: Optional[str] = Field(default=None, max_length=120)
    text: str = Field(min_length=1, max_length=4000)
    tone: Optional[str] = Field(default=None, max_length=240)
    priority: int = Field(default=100, ge=0, le=999)
    balloon_style_hint: Optional[str] = Field(default=None, max_length=240)
    placement_hint: Optional[str] = Field(default=None, max_length=500)


class ComicPanelDialogueCreate(ComicPanelDialogueBase):
    pass


class ComicPanelRenderAssetBase(BaseModel):
    scene_panel_id: str = Field(min_length=1, max_length=120)
    generation_id: Optional[str] = Field(default=None, max_length=120)
    asset_role: ComicRenderAssetRole = "candidate"
    storage_path: Optional[str] = Field(default=None, max_length=500)
    prompt_snapshot: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = None
    bubble_safe_zones: List[Dict[str, Any]] = Field(default_factory=list)
    crop_metadata: Optional[Dict[str, Any]] = None
    render_notes: Optional[str] = Field(default=None, max_length=4000)
    is_selected: bool = False


class ComicPanelRenderAssetCreate(ComicPanelRenderAssetBase):
    pass


class ComicRenderJobResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    scene_panel_id: str
    render_asset_id: str
    generation_id: str
    request_index: int
    source_id: str
    target_tool: str
    executor_mode: str
    executor_key: str
    status: str
    request_json: Optional[Dict[str, Any]] = None
    external_job_id: Optional[str] = None
    external_job_url: Optional[str] = None
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str


def _parse_comic_render_job_request_json(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        if not raw.strip():
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Comic render job request_json must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Comic render job request_json must be a JSON object")
        return parsed
    raise ValueError("Comic render job request_json must be a JSON object")


def comic_render_job_response_from_row(row: Dict[str, Any]) -> ComicRenderJobResponse:
    payload = dict(row)
    payload["request_json"] = _parse_comic_render_job_request_json(
        payload.get("request_json")
    )
    return ComicRenderJobResponse.model_validate(payload)


class ComicPageAssemblyBase(BaseModel):
    episode_id: str = Field(min_length=1, max_length=120)
    page_no: int = Field(ge=1, le=999)
    layout_template_id: Optional[str] = Field(default=None, max_length=120)
    manuscript_profile_id: ComicManuscriptProfileId = "jp_manga_rightbound_v1"
    ordered_panel_ids: List[str] = Field(default_factory=list, max_length=64)
    export_state: ComicPageExportState = "draft"
    preview_path: Optional[str] = Field(default=None, max_length=500)
    master_path: Optional[str] = Field(default=None, max_length=500)
    export_manifest: Optional[Dict[str, Any]] = None


class ComicPageAssemblyCreate(ComicPageAssemblyBase):
    pass


class ComicEpisodeSceneDraft(BaseModel):
    model_config = {"extra": "forbid"}

    scene_no: int = Field(ge=1, le=999)
    premise: str = Field(min_length=1, max_length=2000)
    location_label: Optional[str] = Field(default=None, max_length=240)
    tension: Optional[str] = Field(default=None, max_length=1000)
    reveal: Optional[str] = Field(default=None, max_length=1000)
    continuity_notes: Optional[str] = Field(default=None, max_length=4000)
    involved_character_ids: List[str] = Field(default_factory=list, max_length=16)
    target_panel_count: Optional[int] = Field(default=None, ge=1, le=64)


class ComicScenePanelDraft(BaseModel):
    model_config = {"extra": "forbid"}

    scene_no: int = Field(ge=1, le=999)
    panel_no: int = Field(ge=1, le=999)
    panel_type: ComicPanelType = "beat"
    framing: Optional[str] = Field(default=None, max_length=240)
    camera_intent: Optional[str] = Field(default=None, max_length=500)
    action_intent: Optional[str] = Field(default=None, max_length=500)
    expression_intent: Optional[str] = Field(default=None, max_length=500)
    dialogue_intent: Optional[str] = Field(default=None, max_length=1000)
    continuity_lock: Optional[str] = Field(default=None, max_length=4000)
    page_target_hint: Optional[int] = Field(default=None, ge=1, le=999)
    reading_order: int = Field(ge=1, le=999)


class ComicEpisodeDraft(BaseModel):
    model_config = {"extra": "forbid"}

    character_version_id: str = Field(min_length=1, max_length=120)
    content_mode: SequenceContentMode = "all_ages"
    work_id: Optional[str] = Field(default=None, max_length=120)
    series_id: Optional[str] = Field(default=None, max_length=120)
    production_episode_id: Optional[str] = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    synopsis: str = Field(min_length=1, max_length=4000)
    source_story_plan_json: str = Field(min_length=1)
    status: ComicEpisodeStatus = "planned"
    continuity_summary: Optional[str] = Field(default=None, max_length=4000)
    canon_delta: Optional[str] = Field(default=None, max_length=4000)
    target_output: ComicTargetOutput = "oneshot_manga"
    scenes: List[ComicEpisodeSceneDraft] = Field(default_factory=list)
    panels: List[ComicScenePanelDraft] = Field(default_factory=list)


class ComicStoryPlanImportRequest(BaseModel):
    model_config = {"extra": "forbid"}

    approved_plan: "StoryPlannerPlanResponse"
    character_version_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    panel_multiplier: int = Field(default=2, ge=1, le=8)


class SequenceBlueprintBase(BaseModel):
    work_id: Optional[str] = Field(default=None, max_length=120)
    series_id: Optional[str] = Field(default=None, max_length=120)
    production_episode_id: Optional[str] = Field(default=None, max_length=120)
    content_mode: SequenceContentMode
    policy_profile_id: str = Field(min_length=1, max_length=120)
    character_id: str = Field(min_length=1, max_length=120)
    location_id: str = Field(min_length=1, max_length=120)
    beat_grammar_id: str = Field(min_length=1, max_length=120)
    target_duration_sec: int = Field(ge=1, le=3600)
    shot_count: int = Field(ge=1, le=64)
    tone: Optional[str] = Field(default=None, max_length=120)
    executor_policy: str = Field(min_length=1, max_length=120)


class SequenceBlueprintCreate(SequenceBlueprintBase):
    pass


class SequenceBlueprintUpdate(BaseModel):
    work_id: Optional[str] = Field(default=None, max_length=120)
    series_id: Optional[str] = Field(default=None, max_length=120)
    production_episode_id: Optional[str] = Field(default=None, max_length=120)
    content_mode: Optional[SequenceContentMode] = None
    policy_profile_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    character_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    location_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    beat_grammar_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    target_duration_sec: Optional[int] = Field(default=None, ge=1, le=3600)
    shot_count: Optional[int] = Field(default=None, ge=1, le=64)
    tone: Optional[str] = Field(default=None, max_length=120)
    executor_policy: Optional[str] = Field(default=None, min_length=1, max_length=120)


class SequenceBlueprintResponse(SequenceBlueprintBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class SequenceRunBase(BaseModel):
    sequence_blueprint_id: str = Field(min_length=1, max_length=120)
    content_mode: SequenceContentMode
    policy_profile_id: str = Field(min_length=1, max_length=120)
    prompt_provider_profile_id: str = Field(min_length=1, max_length=120)
    execution_mode: str = Field(min_length=1, max_length=120)
    status: str = Field(default="queued", min_length=1, max_length=120)
    selected_rough_cut_id: Optional[str] = Field(default=None, max_length=120)
    total_score: Optional[float] = None
    error_summary: Optional[str] = Field(default=None, max_length=1000)


class SequenceRunCreate(SequenceRunBase):
    pass


class SequenceRunUpdate(BaseModel):
    sequence_blueprint_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    content_mode: Optional[SequenceContentMode] = None
    policy_profile_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    prompt_provider_profile_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    execution_mode: Optional[str] = Field(default=None, min_length=1, max_length=120)
    status: Optional[str] = Field(default=None, min_length=1, max_length=120)
    selected_rough_cut_id: Optional[str] = Field(default=None, max_length=120)
    total_score: Optional[float] = None
    error_summary: Optional[str] = Field(default=None, max_length=1000)


class SequenceRunResponse(SequenceRunBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class SequenceShotBase(BaseModel):
    sequence_run_id: str = Field(min_length=1, max_length=120)
    content_mode: SequenceContentMode
    policy_profile_id: str = Field(min_length=1, max_length=120)
    shot_no: int = Field(ge=1, le=999)
    beat_type: str = Field(min_length=1, max_length=120)
    camera_intent: str = Field(min_length=1, max_length=240)
    emotion_intent: str = Field(min_length=1, max_length=240)
    action_intent: str = Field(min_length=1, max_length=240)
    target_duration_sec: int = Field(ge=1, le=3600)
    continuity_rules: Optional[str] = Field(default=None, max_length=4000)


class SequenceShotCreate(SequenceShotBase):
    pass


class SequenceShotUpdate(BaseModel):
    sequence_run_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    content_mode: Optional[SequenceContentMode] = None
    policy_profile_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    shot_no: Optional[int] = Field(default=None, ge=1, le=999)
    beat_type: Optional[str] = Field(default=None, min_length=1, max_length=120)
    camera_intent: Optional[str] = Field(default=None, min_length=1, max_length=240)
    emotion_intent: Optional[str] = Field(default=None, min_length=1, max_length=240)
    action_intent: Optional[str] = Field(default=None, min_length=1, max_length=240)
    target_duration_sec: Optional[int] = Field(default=None, ge=1, le=3600)
    continuity_rules: Optional[str] = Field(default=None, max_length=4000)


class SequenceShotResponse(SequenceShotBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class RoughCutBase(BaseModel):
    sequence_run_id: str = Field(min_length=1, max_length=120)
    content_mode: SequenceContentMode
    policy_profile_id: str = Field(min_length=1, max_length=120)
    output_path: Optional[str] = Field(default=None, max_length=500)
    timeline_json: Optional[Any] = None
    total_duration_sec: Optional[float] = Field(default=None, ge=0.0)
    continuity_score: Optional[float] = None
    story_score: Optional[float] = None
    overall_score: Optional[float] = None


class RoughCutCreate(RoughCutBase):
    pass


class RoughCutUpdate(BaseModel):
    sequence_run_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    content_mode: Optional[SequenceContentMode] = None
    policy_profile_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    output_path: Optional[str] = Field(default=None, max_length=500)
    timeline_json: Optional[Any] = None
    total_duration_sec: Optional[float] = Field(default=None, ge=0.0)
    continuity_score: Optional[float] = None
    story_score: Optional[float] = None
    overall_score: Optional[float] = None


class RoughCutResponse(RoughCutBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class SequenceShotPlanResponse(BaseModel):
    shot_no: int = Field(ge=1, le=999)
    beat_type: str = Field(min_length=1, max_length=120)
    camera_intent: str = Field(min_length=1, max_length=240)
    emotion_intent: str = Field(min_length=1, max_length=240)
    action_intent: str = Field(min_length=1, max_length=240)
    target_duration_sec: int = Field(ge=1, le=3600)
    continuity_rules: Optional[str] = Field(default=None, max_length=4000)


class SequenceBlueprintDetailResponse(BaseModel):
    blueprint: SequenceBlueprintResponse
    planned_shots: List[SequenceShotPlanResponse] = Field(default_factory=list)


class SequenceRunCreateRequest(BaseModel):
    sequence_blueprint_id: str = Field(min_length=1, max_length=120)
    prompt_provider_profile_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    candidate_count: int = Field(default=4, ge=2, le=24)
    target_tool: Optional[str] = Field(default=None, min_length=1, max_length=120)


class ProductionWorkCreate(BaseModel):
    id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    format_family: ProductionFormatFamily
    default_content_mode: SequenceContentMode
    status: str = Field(default="draft", min_length=1, max_length=120)
    canon_notes: Optional[str] = Field(default=None, max_length=4000)


class ProductionSeriesCreate(BaseModel):
    id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    work_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    delivery_mode: ProductionDeliveryMode
    audience_mode: SequenceContentMode
    visual_identity_notes: Optional[str] = Field(default=None, max_length=4000)


class ProductionEpisodeBase(BaseModel):
    work_id: str = Field(min_length=1, max_length=120)
    series_id: Optional[str] = Field(default=None, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    synopsis: str = Field(min_length=1, max_length=4000)
    content_mode: SequenceContentMode
    target_outputs: List[ProductionTargetOutput] = Field(default_factory=list, max_length=4)
    continuity_summary: Optional[str] = Field(default=None, max_length=4000)
    status: str = Field(default="draft", min_length=1, max_length=120)


class ProductionEpisodeCreate(ProductionEpisodeBase):
    pass


class ProductionWorkResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    title: str
    format_family: ProductionFormatFamily
    default_content_mode: SequenceContentMode
    status: str
    canon_notes: Optional[str] = None
    created_at: str
    updated_at: str


class ProductionSeriesResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    work_id: str
    title: str
    delivery_mode: ProductionDeliveryMode
    audience_mode: SequenceContentMode
    visual_identity_notes: Optional[str] = None
    created_at: str
    updated_at: str


class ProductionComicTrackLinkResponse(BaseModel):
    id: str
    status: str
    target_output: ComicTargetOutput
    character_id: str


class ProductionAnimationTrackLinkResponse(BaseModel):
    id: str
    content_mode: SequenceContentMode
    policy_profile_id: str
    shot_count: int
    executor_policy: str


class ProductionEpisodeDetailResponse(ProductionEpisodeBase):
    model_config = {"from_attributes": True}

    id: str
    comic_track: Optional[ProductionComicTrackLinkResponse] = None
    animation_track: Optional[ProductionAnimationTrackLinkResponse] = None
    comic_track_count: int = 0
    animation_track_count: int = 0
    created_at: str
    updated_at: str


class StoryPlannerCharacterCatalogEntry(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    canonical_anchor: str = Field(min_length=1, max_length=1000)
    anti_drift: str = Field(min_length=1, max_length=1000)
    wardrobe_notes: str = Field(min_length=1, max_length=600)
    personality_notes: str = Field(min_length=1, max_length=600)
    preferred_checkpoints: List[str] = Field(min_length=1, max_length=8)


class StoryPlannerLocationCatalogEntry(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    setting_anchor: str = Field(min_length=1, max_length=1000)
    visual_rules: List[str] = Field(min_length=1, max_length=12)
    restricted_elements: List[str] = Field(default_factory=list, max_length=12)


class StoryPlannerPolicyPackCatalogEntry(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1, max_length=120)
    lane: StoryPlannerLane
    prompt_provider_profile_id: str = Field(min_length=1, max_length=120)
    negative_prompt_mode: Literal["blank", "recommended", "custom"]
    forbidden_defaults: List[str] = Field(min_length=1, max_length=20)
    planner_rules: List[str] = Field(min_length=1, max_length=20)
    render_preferences: Dict[str, Any] = Field(min_length=1)


class StoryPlannerCatalog(BaseModel):
    characters: List[StoryPlannerCharacterCatalogEntry] = Field(default_factory=list)
    locations: List[StoryPlannerLocationCatalogEntry] = Field(default_factory=list)
    policy_packs: List[StoryPlannerPolicyPackCatalogEntry] = Field(default_factory=list)


class StoryPlannerCastInput(BaseModel):
    model_config = {"extra": "forbid"}

    role: Literal["lead", "support"]
    source_type: Literal["registry", "freeform"]
    character_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    freeform_description: Optional[str] = Field(default=None, min_length=1, max_length=400)

    @model_validator(mode="after")
    def validate_source_fields(self) -> "StoryPlannerCastInput":
        if self.source_type == "registry":
            if not self.character_id:
                raise ValueError("character_id is required when source_type='registry'")
            if self.freeform_description is not None:
                raise ValueError("freeform_description is not allowed when source_type='registry'")
        else:
            if not self.freeform_description:
                raise ValueError("freeform_description is required when source_type='freeform'")
            if self.character_id is not None:
                raise ValueError("character_id is not allowed when source_type='freeform'")
        return self


class StoryPlannerPlanRequest(BaseModel):
    model_config = {"extra": "forbid"}

    story_prompt: str = Field(min_length=1, max_length=2000)
    lane: StoryPlannerLane
    cast: List[StoryPlannerCastInput] = Field(default_factory=list, max_length=2)

    @model_validator(mode="after")
    def validate_unique_cast_roles(self) -> "StoryPlannerPlanRequest":
        roles = [member.role for member in self.cast]
        if len(set(roles)) != len(roles):
            raise ValueError("duplicate cast roles are not allowed")
        return self


class StoryPlannerResolvedCastEntry(BaseModel):
    model_config = {"extra": "forbid"}

    role: Literal["lead", "support"]
    source_type: Literal["registry", "freeform"]
    character_id: Optional[str] = Field(default=None, min_length=1, max_length=120)
    character_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    freeform_description: Optional[str] = Field(default=None, min_length=1, max_length=400)
    canonical_anchor: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=1000,
    )
    anti_drift: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    wardrobe_notes: Optional[str] = Field(default=None, min_length=1, max_length=600)
    personality_notes: Optional[str] = Field(default=None, min_length=1, max_length=600)
    resolution_note: str = Field(min_length=1, max_length=1000)


class StoryPlannerResolvedLocationEntry(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    setting_anchor: str = Field(min_length=1, max_length=1000)
    visual_rules: List[str] = Field(default_factory=list, min_length=1, max_length=12)
    restricted_elements: List[str] = Field(default_factory=list, max_length=12)
    match_note: str = Field(min_length=1, max_length=1000)


class StoryPlannerEpisodeBrief(BaseModel):
    model_config = {"extra": "forbid"}

    premise: str = Field(min_length=1, max_length=1000)
    continuity_guidance: List[str] = Field(default_factory=list, max_length=6)


class StoryPlannerShotCard(BaseModel):
    model_config = {"extra": "forbid"}

    shot_no: int = Field(ge=1, le=4)
    beat: str = Field(min_length=1, max_length=160)
    camera: str = Field(min_length=1, max_length=240)
    action: str = Field(min_length=1, max_length=400)
    emotion: str = Field(min_length=1, max_length=240)
    continuity_note: str = Field(min_length=1, max_length=400)


class StoryPlannerAnchorRenderSnapshot(BaseModel):
    model_config = {"extra": "forbid"}

    policy_pack_id: str = Field(min_length=1, max_length=120)
    checkpoint: str = Field(min_length=1, max_length=255)
    workflow_lane: Literal["classic_clip", "sdxl_illustrious"]
    negative_prompt: Optional[str] = Field(default=None, max_length=4000)
    preserve_blank_negative_prompt: bool = False

    @model_validator(mode="after")
    def validate_anchor_render_snapshot(self) -> "StoryPlannerAnchorRenderSnapshot":
        if infer_workflow_lane(self.checkpoint) != self.workflow_lane:
            raise ValueError(
                "anchor_render.workflow_lane must match the checkpoint workflow lane"
            )
        if (
            self.preserve_blank_negative_prompt
            and isinstance(self.negative_prompt, str)
            and self.negative_prompt.strip()
        ):
            raise ValueError(
                "anchor_render cannot preserve a blank negative prompt and carry a non-blank negative_prompt"
            )
        return self


def _infer_story_planner_policy_pack_lane(policy_pack_id: str) -> StoryPlannerLane | None:
    for lane in ("adult_nsfw", "all_ages", "unrestricted"):
        if lane in policy_pack_id:
            return lane  # type: ignore[return-value]
    return None


class StoryPlannerPlanResponse(BaseModel):
    model_config = {"extra": "forbid"}

    story_prompt: str = Field(min_length=1, max_length=2000)
    lane: StoryPlannerLane
    policy_pack_id: str = Field(min_length=1, max_length=120)
    approval_token: str = Field(min_length=64, max_length=64)
    anchor_render: StoryPlannerAnchorRenderSnapshot
    resolved_cast: List[StoryPlannerResolvedCastEntry] = Field(default_factory=list)
    location: StoryPlannerResolvedLocationEntry
    episode_brief: StoryPlannerEpisodeBrief
    shots: List[StoryPlannerShotCard] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def validate_story_planner_plan_response(self) -> "StoryPlannerPlanResponse":
        expected_shot_numbers = [1, 2, 3, 4]
        actual_shot_numbers = [shot.shot_no for shot in self.shots]
        if actual_shot_numbers != expected_shot_numbers:
            raise ValueError(
                "shots must use canonical shot numbers [1, 2, 3, 4] in order"
            )
        if self.anchor_render.policy_pack_id != self.policy_pack_id:
            raise ValueError("anchor_render.policy_pack_id must match policy_pack_id")
        inferred_policy_pack_lane = _infer_story_planner_policy_pack_lane(
            self.policy_pack_id
        )
        if inferred_policy_pack_lane is not None and inferred_policy_pack_lane != self.lane:
            raise ValueError("policy_pack_id must match lane")
        return self


class StoryPlannerAnchorQueuedShotResponse(BaseModel):
    model_config = {"extra": "forbid"}

    shot_no: int = Field(ge=1, le=4)
    generation_ids: List[str] = Field(default_factory=list, min_length=1)


class StoryPlannerAnchorQueueRequest(BaseModel):
    model_config = {"extra": "forbid"}

    approved_plan: StoryPlannerPlanResponse
    candidate_count: int = Field(default=2, ge=2, le=24)


class StoryPlannerAnchorQueueResponse(BaseModel):
    model_config = {"extra": "forbid"}

    lane: StoryPlannerLane
    requested_shot_count: int = Field(ge=0)
    queued_generation_count: int = Field(ge=0)
    queued_shots: List[StoryPlannerAnchorQueuedShotResponse] = Field(
        default_factory=list
    )
    queued_generations: List["GenerationResponse"] = Field(default_factory=list)


class SequenceAnchorCandidateResponse(BaseModel):
    id: str
    sequence_shot_id: str = Field(min_length=1, max_length=120)
    content_mode: SequenceContentMode
    policy_profile_id: str = Field(min_length=1, max_length=120)
    generation_id: str = Field(min_length=1, max_length=120)
    identity_score: Optional[float] = None
    location_lock_score: Optional[float] = None
    beat_fit_score: Optional[float] = None
    quality_score: Optional[float] = None
    rank_score: Optional[float] = None
    is_selected_primary: bool = False
    is_selected_backup: bool = False
    created_at: str
    updated_at: str


class SequenceShotClipResponse(BaseModel):
    id: str
    sequence_shot_id: str = Field(min_length=1, max_length=120)
    content_mode: SequenceContentMode
    policy_profile_id: str = Field(min_length=1, max_length=120)
    selected_animation_job_id: Optional[str] = Field(default=None, max_length=120)
    clip_path: Optional[str] = Field(default=None, max_length=500)
    clip_duration_sec: Optional[float] = Field(default=None, ge=0.0)
    clip_score: Optional[float] = None
    retry_count: int = Field(ge=0, le=999)
    is_degraded: bool = False
    created_at: str
    updated_at: str


class SequenceRunShotDetailResponse(BaseModel):
    shot: SequenceShotResponse
    anchor_candidates: List[SequenceAnchorCandidateResponse] = Field(default_factory=list)
    clips: List[SequenceShotClipResponse] = Field(default_factory=list)


class SequenceRoughCutCandidateResponse(BaseModel):
    rough_cut: RoughCutResponse
    is_selected: bool = False


class SequenceRunSummaryResponse(BaseModel):
    run: SequenceRunResponse
    shot_count: int = Field(default=0, ge=0)
    rough_cut_candidate_count: int = Field(default=0, ge=0)


class SequenceRunDetailResponse(BaseModel):
    run: SequenceRunResponse
    blueprint: SequenceBlueprintResponse
    shots: List[SequenceRunShotDetailResponse] = Field(default_factory=list)
    rough_cut_candidates: List[SequenceRoughCutCandidateResponse] = Field(default_factory=list)


class ComicEpisodeResponse(ComicEpisodeBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class ComicEpisodeSceneResponse(ComicEpisodeSceneBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class ComicScenePanelResponse(ComicScenePanelBase):
    model_config = {"from_attributes": True}

    id: str
    remote_job_count: int = Field(default=0, ge=0)
    pending_remote_job_count: int = Field(default=0, ge=0)
    created_at: str
    updated_at: str


class ComicPanelDialogueResponse(ComicPanelDialogueBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class ComicPanelRenderAssetResponse(ComicPanelRenderAssetBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class ComicPanelRenderQueueResponse(BaseModel):
    panel: ComicScenePanelResponse
    execution_mode: ComicRenderExecutionMode = "local_preview"
    requested_count: int = Field(ge=1)
    queued_generation_count: int = Field(ge=0)
    materialized_asset_count: int = Field(default=0, ge=0)
    pending_render_job_count: int = Field(default=0, ge=0)
    remote_job_count: int = Field(default=0, ge=0)
    render_assets: List[ComicPanelRenderAssetResponse] = Field(default_factory=list)


class ComicPageAssemblyResponse(ComicPageAssemblyBase):
    model_config = {"from_attributes": True}

    id: str
    created_at: str
    updated_at: str


class ComicCharacterResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    slug: str
    name: str
    status: str
    tier: Optional[str] = None
    created_at: str
    updated_at: str


class ComicCharacterVersionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    character_id: str
    version_name: str
    purpose: str
    checkpoint: str
    workflow_lane: str
    created_at: str
    updated_at: str


class ComicSceneDetailResponse(BaseModel):
    scene: ComicEpisodeSceneResponse
    panels: List[ComicScenePanelResponse] = Field(default_factory=list)


class ComicPanelDetailResponse(BaseModel):
    panel: ComicScenePanelResponse
    dialogues: List[ComicPanelDialogueResponse] = Field(default_factory=list)
    render_assets: List[ComicPanelRenderAssetResponse] = Field(default_factory=list)


class ComicEpisodeDetailResponse(BaseModel):
    episode: ComicEpisodeResponse
    scenes: List[ComicSceneDetailResponse] = Field(default_factory=list)
    pages: List[ComicPageAssemblyResponse] = Field(default_factory=list)


class ComicEpisodeSummaryResponse(BaseModel):
    episode: ComicEpisodeResponse
    scene_count: int = Field(default=0, ge=0)
    page_count: int = Field(default=0, ge=0)


class ComicDialogueGenerationResponse(BaseModel):
    panel: ComicScenePanelResponse
    dialogues: List[ComicPanelDialogueResponse] = Field(default_factory=list)
    generated_count: int = Field(default=0, ge=0)
    overwrite_existing: bool = False
    prompt_provider_profile_id: str = Field(
        default="adult_local_llm", min_length=1, max_length=120
    )


class ComicManuscriptProfileResponse(BaseModel):
    id: ComicManuscriptProfileId
    label: str = Field(min_length=1, max_length=120)
    binding_direction: Literal["right_to_left"]
    finishing_tool: Literal["clip_studio_ex"]
    print_intent: Literal["japanese_manga"]
    trim_reference: str = Field(min_length=1, max_length=200)
    bleed_reference: str = Field(min_length=1, max_length=200)
    safe_area_reference: str = Field(min_length=1, max_length=200)
    naming_pattern: str = Field(min_length=1, max_length=120)


def list_comic_manuscript_profiles() -> list[ComicManuscriptProfileResponse]:
    return [
        ComicManuscriptProfileResponse(
            id="jp_manga_rightbound_v1",
            label="Japanese Manga Right-Bound v1",
            binding_direction="right_to_left",
            finishing_tool="clip_studio_ex",
            print_intent="japanese_manga",
            trim_reference="B5 monochrome manga manuscript preset",
            bleed_reference="CLIP STUDIO EX Japanese comic print bleed preset",
            safe_area_reference="CLIP STUDIO EX default inner safe area guide",
            naming_pattern="page_{page_no:03d}.tif",
        )
    ]


class ComicPageAssemblyBatchResponse(BaseModel):
    episode_id: str = Field(min_length=1, max_length=120)
    layout_template_id: ComicPageLayoutTemplateId
    manuscript_profile: Dict[str, Any] = Field(default_factory=dict)
    pages: List[ComicPageAssemblyResponse] = Field(default_factory=list)
    export_manifest_path: str = Field(min_length=1, max_length=500)
    dialogue_json_path: str = Field(min_length=1, max_length=500)
    panel_asset_manifest_path: str = Field(min_length=1, max_length=500)
    page_assembly_manifest_path: str = Field(min_length=1, max_length=500)
    teaser_handoff_manifest_path: str = Field(min_length=1, max_length=500)
    manuscript_profile_manifest_path: str = Field(min_length=1, max_length=500)
    handoff_readme_path: str = Field(min_length=1, max_length=500)
    production_checklist_path: str = Field(min_length=1, max_length=500)


class ComicPageExportResponse(ComicPageAssemblyBatchResponse):
    export_zip_path: str = Field(min_length=1, max_length=500)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class GenerationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    prompt: str
    negative_prompt: Optional[str] = None
    checkpoint: str
    workflow_lane: Optional[Literal["classic_clip", "sdxl_illustrious"]] = None
    loras: List[LoraInput] = Field(default_factory=list)
    seed: int
    steps: int
    cfg: float
    width: int
    height: int
    sampler: str
    scheduler: str
    clip_skip: Optional[int] = None
    status: str
    image_path: Optional[str] = None
    watermarked_path: Optional[str] = None
    upscaled_image_path: Optional[str] = None
    adetailed_path: Optional[str] = None
    hiresfix_path: Optional[str] = None
    dreamactor_path: Optional[str] = None
    dreamactor_task_id: Optional[str] = None
    dreamactor_status: Optional[str] = None
    upscaled_preview_path: Optional[str] = None
    upscale_model: Optional[str] = None
    thumbnail_path: Optional[str] = None
    workflow_path: Optional[str] = None
    generation_time_sec: Optional[float] = None
    tags: Optional[List[str]] = None
    preset_id: Optional[str] = None
    notes: Optional[str] = None
    source_id: Optional[str] = None
    comfyui_prompt_id: Optional[str] = None
    error_message: Optional[str] = None
    postprocess_kind: Optional[str] = None
    postprocess_status: Optional[str] = None
    postprocess_message: Optional[str] = None
    is_favorite: bool = False
    quality_score: Optional[int] = None
    quality_ai_score: Optional[int] = None
    publish_approved: int = 0
    curated_at: Optional[str] = None
    direction_pinned: int = 0
    created_at: str
    completed_at: Optional[str] = None


class GalleryItem(GenerationResponse):
    pass


class GenerationStatus(BaseModel):
    id: str
    status: str
    generation_time_sec: Optional[float] = None
    estimated_time_sec: Optional[float] = None
    postprocess_kind: Optional[str] = None
    postprocess_status: Optional[str] = None


class GenerationBatchResponse(BaseModel):
    count: int
    base_seed: int
    seed_increment: int
    generations: List[GenerationResponse] = Field(default_factory=list)


class FavoriteUpscaleStatusResponse(BaseModel):
    favorites_total: int
    upscaled_done: int
    queued: int
    running: int
    pending: int
    daily_candidates: int
    completion_pct: float
    daily_enabled: bool
    daily_hour: int
    daily_minute: int
    daily_batch_limit: Optional[int] = None
    backlog_window_start_hour: int
    backlog_window_end_hour: int
    backlog_window_open: bool
    mode: Literal["safe", "quality"]


class BenchmarkResponse(BaseModel):
    id: str
    name: str
    prompt: str
    negative_prompt: Optional[str] = None
    loras: List[LoraInput] = Field(default_factory=list)
    steps: int
    cfg: float
    width: int
    height: int
    sampler: str
    scheduler: str
    seed: Optional[int]
    checkpoints: List[str]
    generation_ids: List[str]
    status: str
    created_at: str
    completed_at: Optional[str] = None
    generations: Optional[List[Any]] = None


class PresetResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    description: Optional[str] = None
    checkpoint: str
    loras: List[LoraInput] = Field(default_factory=list)
    prompt_template: Optional[str] = None
    negative_prompt: Optional[str] = None
    default_params: Dict[str, Any] = Field(default_factory=dict)
    tags: Optional[List[str]] = None
    created_at: str
    updated_at: Optional[str] = None


class LoraProfileResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    display_name: str
    filename: str
    category: str
    default_strength: float
    tags: Optional[str] = None
    notes: Optional[str] = None
    compatible_checkpoints: Optional[List[str]] = None
    created_at: str


class MoodMappingResponse(BaseModel):
    id: str
    mood_keyword: str
    lora_ids: List[str]
    prompt_additions: str
    created_at: str


class MoodSelectResponse(BaseModel):
    loras: List[LoraInput]
    prompt_additions: str


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int


class CollectionResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    description: Optional[str] = None
    cover_image_id: Optional[str] = None
    cover_thumbnail_path: Optional[str] = None
    image_count: int = 0
    contains_generation: bool = False
    created_at: str
    updated_at: Optional[str] = None


class CollectionDetailResponse(BaseModel):
    collection: CollectionResponse
    items: List[GalleryItem]
    total: int
    page: int
    per_page: int
    total_pages: int


class ScheduledJobResponse(BaseModel):
    id: str
    name: str
    preset_id: str
    count: int
    cron_hour: int
    cron_minute: int
    enabled: bool
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str
    updated_at: str


class SystemHealth(BaseModel):
    status: str
    comfyui_connected: bool
    db_ok: bool
    total_generations: int
    completed_generations: int = 0
    failed_generations: int = 0
    cancelled_generations: int = 0


class WatermarkSettings(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    enabled: bool
    text: str
    position: WatermarkPosition
    opacity: float
    font_size: int
    padding: int
    color: str
    updated_at: str


class CaptionGenerateRequest(BaseModel):
    platform: Literal["twitter", "fansly", "pixiv", "generic"] = "twitter"
    tone: Literal["teaser", "clinical", "campaign"] = "teaser"
    channel: Literal["social_short", "post_body", "launch_copy"] = "social_short"
    approved: bool = False


class PromptDirectionBlueprintBase(BaseModel):
    codename_stub: str = Field(min_length=1, max_length=120)
    series: str = Field(min_length=1, max_length=120)
    scene_hook: str = Field(min_length=1, max_length=240)
    camera_plan: str = Field(min_length=1, max_length=240)
    pose_plan: str = Field(min_length=1, max_length=240)
    environment: str = Field(min_length=1, max_length=240)
    device_focus: str = Field(min_length=1, max_length=240)
    lighting_plan: str = Field(min_length=1, max_length=240)
    material_focus: str = Field(min_length=1, max_length=240)
    intensity_hook: str = Field(min_length=1, max_length=240)


class PromptDirectionBlueprintInput(PromptDirectionBlueprintBase):
    pass


class PromptDirectionBlueprintResponse(PromptDirectionBlueprintBase):
    pass


class PromptFactoryCheckpointPreferenceUpdate(BaseModel):
    checkpoint: str = Field(min_length=1, max_length=255)
    mode: PromptFactoryCheckpointPreferenceMode = "default"
    priority_boost: int = Field(default=0, ge=-20, le=20)
    notes: Optional[str] = Field(default=None, max_length=240)


class PromptFactoryCheckpointPreferencesReplaceRequest(BaseModel):
    entries: List[PromptFactoryCheckpointPreferenceUpdate] = Field(
        default_factory=list,
        max_length=400,
    )


class PromptBatchGenerateRequest(BaseModel):
    concept_brief: str = Field(min_length=1, max_length=600)
    creative_brief: Optional[str] = Field(default=None, max_length=600)
    count: int = Field(default=24, ge=1, le=200)
    chunk_size: int = Field(default=20, ge=1, le=25)
    content_mode: Optional[SequenceContentMode] = None
    prompt_provider_profile_id: Optional[str] = Field(default=None, max_length=120)
    workflow_lane: Literal["auto", "classic_clip", "sdxl_illustrious"] = "auto"
    provider: Literal["default", "openrouter", "xai"] = "default"
    model: Optional[str] = Field(default=None, max_length=120)
    tone: Literal["clinical", "campaign", "editorial", "teaser"] = "editorial"
    heat_level: Literal["suggestive", "steamy", "maximal"] = "maximal"
    creative_autonomy: Literal["strict", "hybrid", "director"] = "hybrid"
    direction_pass_enabled: bool = True
    target_lora_count: int = Field(default=2, ge=1, le=4)
    checkpoint_pool_size: int = Field(default=3, ge=1, le=5)
    include_negative_prompt: bool = True
    dedupe: bool = True
    forbidden_elements: List[str] = Field(default_factory=list, max_length=24)
    direction_pack_override: List[PromptDirectionBlueprintInput] = Field(
        default_factory=list,
        max_length=200,
    )
    expansion_axes: List[str] = Field(
        default_factory=lambda: [
            "camera distance",
            "lighting mood",
            "material emphasis",
            "mask design",
            "location",
            "restraint device",
            "story beat",
        ],
        max_length=12,
    )


class PromptBatchRowDraft(BaseModel):
    codename: str = Field(min_length=1, max_length=120)
    series: str = Field(min_length=1, max_length=120)
    checkpoint: str = Field(min_length=1, max_length=255)
    workflow_lane: Optional[Literal["classic_clip", "sdxl_illustrious"]] = None
    loras: List[LoraInput] = Field(default_factory=list, max_length=4)
    sampler: str = Field(default="euler_a", min_length=1, max_length=60)
    steps: int = Field(default=30, ge=1, le=MAX_GENERATION_STEPS)
    cfg: float = Field(default=5.5, ge=1.0, le=MAX_GENERATION_CFG)
    clip_skip: Optional[int] = Field(default=2, ge=1, le=12)
    width: int = Field(default=832, ge=MIN_GENERATION_DIM, le=MAX_GENERATION_DIM)
    height: int = Field(default=1216, ge=MIN_GENERATION_DIM, le=MAX_GENERATION_DIM)
    positive_prompt: str = Field(min_length=1)
    negative_prompt: Optional[str] = None

    @model_validator(mode="after")
    def validate_shape(self) -> "PromptBatchRowDraft":
        if self.width % 8 != 0 or self.height % 8 != 0:
            raise ValueError("width and height must be multiples of 8")
        if self.width * self.height > MAX_GENERATION_PIXELS:
            raise ValueError(
                f"width * height must be <= {MAX_GENERATION_PIXELS} pixels"
            )
        return self


class PromptBatchRowResponse(PromptBatchRowDraft):
    set_no: int = Field(ge=1)


class PromptFactoryBenchmarkResponse(BaseModel):
    favorites_total: int
    workflow_lane: str
    prompt_dialect: str
    top_checkpoints: List[str] = Field(default_factory=list)
    top_loras: List[str] = Field(default_factory=list)
    avg_lora_strength: float
    cfg_values: List[float] = Field(default_factory=list)
    steps_values: List[int] = Field(default_factory=list)
    sampler: str
    scheduler: str
    clip_skip: Optional[int] = None
    width: int
    height: int
    theme_keywords: List[str] = Field(default_factory=list)
    material_cues: List[str] = Field(default_factory=list)
    control_cues: List[str] = Field(default_factory=list)
    camera_cues: List[str] = Field(default_factory=list)
    environment_cues: List[str] = Field(default_factory=list)
    exposure_cues: List[str] = Field(default_factory=list)
    negative_prompt: str


class PromptFactoryContentModeDefaultResponse(BaseModel):
    content_mode: SequenceContentMode
    prompt_provider_profile_id: str
    provider_kind: str
    model: str
    ready: bool


class PromptFactoryCapabilitiesResponse(BaseModel):
    default_prompt_provider_profile_id: Optional[str] = None
    default_provider: Optional[str] = None
    default_model: Optional[str] = None
    content_mode_defaults: List[PromptFactoryContentModeDefaultResponse] = Field(
        default_factory=list
    )
    openrouter_configured: bool
    xai_configured: bool
    ready: Optional[bool] = None
    recommended_lane: str
    supported_lanes: List[str] = Field(default_factory=list)
    batch_import_headers: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)

class PromptFactoryCheckpointPreferenceEntryResponse(BaseModel):
    checkpoint: str
    available: bool = True
    architecture: Optional[str] = None
    favorite_count: int = 0
    mode: PromptFactoryCheckpointPreferenceMode = "default"
    priority_boost: int = 0
    notes: Optional[str] = None
    updated_at: Optional[str] = None


class PromptFactoryCheckpointPreferencesResponse(BaseModel):
    generated_at: str
    entries: List[PromptFactoryCheckpointPreferenceEntryResponse] = Field(
        default_factory=list
    )


class PromptBatchGenerateResponse(BaseModel):
    provider: str
    model: str
    requested_count: int
    generated_count: int
    chunk_count: int
    benchmark: PromptFactoryBenchmarkResponse
    direction_pack: List[PromptDirectionBlueprintResponse] = Field(default_factory=list)
    rows: List[PromptBatchRowResponse] = Field(default_factory=list)


class PromptBatchQueueResponse(BaseModel):
    prompt_batch: PromptBatchGenerateResponse
    queued_generations: List[GenerationResponse] = Field(default_factory=list)


class CaptionVariantResponse(BaseModel):
    id: str
    generation_id: str
    channel: str
    platform: str
    provider: str
    model: str
    prompt_version: str
    tone: str
    story: str
    hashtags: str
    approved: bool
    created_at: str
    updated_at: str


class PublishJobCreate(BaseModel):
    generation_id: str
    caption_variant_id: Optional[str] = None
    platform: Literal["twitter", "fansly", "pixiv", "custom"] = "twitter"
    status: Literal["draft", "queued", "scheduled", "published", "failed"] = "draft"
    scheduled_at: Optional[str] = None
    external_post_id: Optional[str] = None
    external_post_url: Optional[str] = None
    notes: Optional[str] = None


class PublishJobUpdate(BaseModel):
    status: Optional[Literal["draft", "queued", "scheduled", "published", "failed"]] = None
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    external_post_id: Optional[str] = None
    external_post_url: Optional[str] = None
    notes: Optional[str] = None


class PublishJobResponse(BaseModel):
    id: str
    generation_id: str
    caption_variant_id: Optional[str] = None
    platform: str
    status: str
    scheduled_at: Optional[str] = None
    published_at: Optional[str] = None
    external_post_id: Optional[str] = None
    external_post_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class EngagementSnapshotCreate(BaseModel):
    likes: int = Field(default=0, ge=0)
    replies: int = Field(default=0, ge=0)
    reposts: int = Field(default=0, ge=0)
    bookmarks: int = Field(default=0, ge=0)
    impressions: int = Field(default=0, ge=0)
    detail_json: Optional[Dict[str, Any]] = None


class EngagementSnapshotResponse(BaseModel):
    id: int
    publish_job_id: str
    captured_at: str
    likes: int
    replies: int
    reposts: int
    bookmarks: int
    impressions: int
    detail_json: Optional[Dict[str, Any]] = None


class AnimationCandidateUpdate(BaseModel):
    status: Optional[Literal["suggested", "approved", "queued", "processing", "completed", "rejected"]] = None
    target_tool: Optional[AnimationTargetTool] = None
    notes: Optional[str] = None


class AnimationCandidateResponse(BaseModel):
    id: str
    generation_id: str
    publish_job_id: Optional[str] = None
    trigger_source: str
    trigger_score: float
    target_tool: str
    status: str
    notes: Optional[str] = None
    approved_at: Optional[str] = None
    created_at: str
    updated_at: str


class AnimationJobCreate(BaseModel):
    candidate_id: Optional[str] = None
    generation_id: Optional[str] = None
    publish_job_id: Optional[str] = None
    target_tool: Optional[AnimationTargetTool] = None
    executor_mode: Optional[AnimationExecutorMode] = None
    executor_key: Optional[str] = None
    status: Literal[
        "draft",
        "queued",
        "submitted",
        "processing",
        "completed",
        "failed",
        "cancelled",
    ] = "queued"
    request_json: Optional[Dict[str, Any]] = None


class AnimationJobUpdate(BaseModel):
    status: Optional[
        Literal[
            "draft",
            "queued",
            "submitted",
            "processing",
            "completed",
            "failed",
            "cancelled",
        ]
    ] = None
    external_job_id: Optional[str] = None
    external_job_url: Optional[str] = None
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    request_json: Optional[Dict[str, Any]] = None


class AnimationJobCallbackPayload(BaseModel):
    status: Literal["queued", "submitted", "processing", "completed", "failed", "cancelled"]
    external_job_id: Optional[str] = None
    external_job_url: Optional[str] = None
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    request_json: Optional[Dict[str, Any]] = None


class AnimationJobResponse(BaseModel):
    id: str
    candidate_id: Optional[str] = None
    generation_id: str
    publish_job_id: Optional[str] = None
    target_tool: str
    executor_mode: str
    executor_key: str
    status: str
    request_json: Optional[Dict[str, Any]] = None
    external_job_id: Optional[str] = None
    external_job_url: Optional[str] = None
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str


class AnimationExecutorConfigResponse(BaseModel):
    mode: str
    executor_key: str
    remote_base_url: Optional[str] = None
    managed_provider: Optional[str] = None
    supports_direct_submit: bool
    preferred_flow: str
    supported_target_tools: List[str]


class AnimationPresetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    target_tool: AnimationTargetTool
    backend_family: str
    model_profile: str
    request_json: Dict[str, Any] = Field(default_factory=dict)


class AnimationPresetLaunchRequest(BaseModel):
    candidate_id: Optional[str] = None
    generation_id: Optional[str] = None
    publish_job_id: Optional[str] = None
    executor_mode: Optional[AnimationExecutorMode] = None
    executor_key: Optional[str] = None
    dispatch_immediately: bool = True
    request_overrides: Dict[str, Any] = Field(default_factory=dict)


class AnimationJobDispatchResponse(BaseModel):
    animation_job: AnimationJobResponse
    dispatch_mode: str
    remote_request_accepted: bool
    remote_worker_job_id: Optional[str] = None
    remote_worker_job_url: Optional[str] = None


class AnimationPresetLaunchResponse(BaseModel):
    preset: AnimationPresetResponse
    animation_job: AnimationJobResponse
    dispatch: Optional[AnimationJobDispatchResponse] = None
    dispatch_error: Optional[str] = None


class ReadyPublishItemResponse(BaseModel):
    generation_id: str
    image_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    checkpoint: str
    prompt: str
    created_at: str
    approved_caption_id: Optional[str] = None
    caption_count: int = 0
    publish_job_count: int = 0
    latest_publish_status: Optional[str] = None
    latest_animation_status: Optional[str] = None
    latest_animation_score: Optional[float] = None
