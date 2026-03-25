"""Workflow lane registry for HollowForge generation pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

WorkflowLane = Literal["classic_clip", "sdxl_illustrious"]
PromptDialect = Literal["natural_language", "tag_stack"]


@dataclass(frozen=True)
class WorkflowLaneSpec:
    key: WorkflowLane
    label: str
    description: str
    prompt_dialect: PromptDialect
    recommended_lora_count: int
    defaults: dict[str, Any]
    checkpoint_hints: tuple[str, ...]


_WORKFLOW_LANES: dict[WorkflowLane, WorkflowLaneSpec] = {
    "classic_clip": WorkflowLaneSpec(
        key="classic_clip",
        label="Classic CLIP",
        description="Single-encoder fallback workflow for generic checkpoint families.",
        prompt_dialect="natural_language",
        recommended_lora_count=2,
        defaults={
            "steps": 28,
            "cfg": 7.0,
            "width": 832,
            "height": 1216,
            "sampler": "euler",
            "scheduler": "normal",
            "clip_skip": None,
        },
        checkpoint_hints=(),
    ),
    "sdxl_illustrious": WorkflowLaneSpec(
        key="sdxl_illustrious",
        label="SDXL Illustrious Production",
        description="Dual-encoder SDXL lane tuned for anime / illustration checkpoint stacks.",
        prompt_dialect="tag_stack",
        recommended_lora_count=2,
        defaults={
            "steps": 30,
            "cfg": 5.5,
            "width": 832,
            "height": 1216,
            "sampler": "euler_ancestral",
            "scheduler": "normal",
            "clip_skip": 2,
        },
        checkpoint_hints=(
            "illustrious",
            "sdxl",
            "pony",
            "hassaku",
            "prefect",
            "wai",
            "animayhem",
            "illustrij",
            "obsession",
            "rx",
            "akiumlumen",
            "autismmix",
            "xl",
        ),
    ),
}


def get_workflow_lane_spec(lane: WorkflowLane) -> WorkflowLaneSpec:
    return _WORKFLOW_LANES[lane]


def list_workflow_lanes() -> list[dict[str, Any]]:
    return [
        {
            "key": spec.key,
            "label": spec.label,
            "description": spec.description,
            "prompt_dialect": spec.prompt_dialect,
            "recommended_lora_count": spec.recommended_lora_count,
            "defaults": dict(spec.defaults),
        }
        for spec in _WORKFLOW_LANES.values()
    ]


def resolve_workflow_lane(
    checkpoint: str,
    requested_lane: str | None = None,
) -> WorkflowLane:
    lane = (requested_lane or "").strip().lower()
    if lane and lane != "auto" and lane in _WORKFLOW_LANES:
        return lane  # type: ignore[return-value]

    return infer_workflow_lane(checkpoint)


def infer_workflow_lane(checkpoint: str) -> WorkflowLane:
    checkpoint_name = checkpoint.strip().lower()
    if checkpoint_name:
        sdxl_hints = _WORKFLOW_LANES["sdxl_illustrious"].checkpoint_hints
        if any(hint in checkpoint_name for hint in sdxl_hints):
            return "sdxl_illustrious"

    return "classic_clip"
