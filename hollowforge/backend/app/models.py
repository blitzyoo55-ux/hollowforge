"""Pydantic v2 request / response models."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


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


class SequenceBlueprintBase(BaseModel):
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


class PromptFactoryCapabilitiesResponse(BaseModel):
    default_provider: str
    default_model: str
    openrouter_configured: bool
    xai_configured: bool
    ready: bool
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
