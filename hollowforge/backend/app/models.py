"""Pydantic v2 request / response models."""

import random
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


MAX_GENERATION_STEPS = 150
MAX_GENERATION_CFG = 30.0
MIN_GENERATION_DIM = 256
MAX_GENERATION_DIM = 1536
MAX_GENERATION_PIXELS = 2_359_296  # 1536 * 1536


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
    sort_by: str = "created_at"
    sort_order: str = "desc"


class ReproduceRequest(BaseModel):
    mode: Literal["exact", "variation"]
    seed: Optional[int] = None
    notes: Optional[str] = None


class UpscaleRequest(BaseModel):
    upscale_model: str = "remacri_original.safetensors"


class ComfyUIConfigUpdate(BaseModel):
    url: str


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class GenerationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    prompt: str
    negative_prompt: Optional[str] = None
    checkpoint: str
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
    upscaled_image_path: Optional[str] = None
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
    created_at: str
    completed_at: Optional[str] = None


class GenerationStatus(BaseModel):
    id: str
    status: str
    generation_time_sec: Optional[float] = None
    estimated_time_sec: Optional[float] = None


class GenerationBatchResponse(BaseModel):
    count: int
    base_seed: int
    seed_increment: int
    generations: List[GenerationResponse] = Field(default_factory=list)


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


class MoodSelectResponse(BaseModel):
    loras: List[LoraInput]
    prompt_additions: str


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int


class SystemHealth(BaseModel):
    status: str
    comfyui_connected: bool
    db_ok: bool
    total_generations: int
