"""Pydantic models for the animation worker."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, HttpUrl, model_validator


class WorkerJobCreate(BaseModel):
    hollowforge_job_id: str
    candidate_id: Optional[str] = None
    generation_id: str
    publish_job_id: Optional[str] = None
    target_tool: str
    executor_mode: Literal["local", "remote_worker", "managed_api"] = "remote_worker"
    executor_key: str = "default"
    source_image_url: Optional[HttpUrl] = None
    generation_metadata: Optional[Dict[str, Any]] = None
    request_json: Optional[Dict[str, Any]] = None
    callback_url: Optional[HttpUrl] = None
    callback_token: Optional[str] = None

    @model_validator(mode="after")
    def _validate_source_image_url(self) -> "WorkerJobCreate":
        if self.target_tool == "comic_panel_still":
            if self.request_json is None:
                raise ValueError("request_json is required when target_tool='comic_panel_still'")
            backend_family = self.request_json.get("backend_family")
            normalized_family = (
                backend_family.strip().lower() if isinstance(backend_family, str) else None
            )
            if normalized_family not in {"sdxl_still", "sdxl_ipadapter_still"}:
                raise ValueError(
                    "comic_panel_still requires request_json.backend_family in "
                    "{'sdxl_still', 'sdxl_ipadapter_still'}"
                )
        if self.target_tool != "comic_panel_still" and self.source_image_url is None:
            raise ValueError(
                "source_image_url is required unless target_tool='comic_panel_still'"
            )
        return self


class WorkerJobResponse(BaseModel):
    id: str
    hollowforge_job_id: str
    candidate_id: Optional[str] = None
    generation_id: str
    publish_job_id: Optional[str] = None
    target_tool: str
    executor_mode: str
    executor_key: str
    status: str
    source_image_url: Optional[str] = None
    generation_metadata: Optional[Dict[str, Any]] = None
    request_json: Optional[Dict[str, Any]] = None
    callback_url: Optional[str] = None
    external_job_id: Optional[str] = None
    external_job_url: Optional[str] = None
    output_url: Optional[str] = None
    error_message: Optional[str] = None
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str
    job_url: str


class WorkerHealthResponse(BaseModel):
    status: str
    executor_backend: str


class HollowForgeCallbackPayload(BaseModel):
    status: Literal["queued", "submitted", "processing", "completed", "failed", "cancelled"]
    external_job_id: Optional[str] = None
    external_job_url: Optional[str] = None
    output_path: Optional[str] = None
    output_url: Optional[str] = None
    error_message: Optional[str] = None
    request_json: Optional[Dict[str, Any]] = None
