"""LoRA profile listing and smart selection endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, List

from fastapi import APIRouter, Query, Request, status

from app.db import get_db
from app.models import LoraProfileResponse, MoodSelectRequest, MoodSelectResponse
from app.services.lora_selector import MAX_TOTAL_STRENGTH, select_by_moods
from app.services.model_compatibility import (
    build_lora_compatibility_snapshot,
    is_checkpoint_compatible,
    parse_compatible_checkpoints,
)

router = APIRouter(prefix="/api/v1/loras", tags=["loras"])

_RAISE_EFFECT_BY_CATEGORY: dict[str, str] = {
    "style": "스타일 LoRA 영향이 강해져 기본 체크포인트의 톤/선화 성향을 더 빠르게 덮습니다.",
    "eyes": "눈, 하이라이트, 디테일 대비가 강해지지만 과하면 인공적인 이목구비가 생길 수 있습니다.",
    "material": "소재 질감(광택/반사/라텍스)이 강해져 존재감이 커지지만 번들거림이 과해질 수 있습니다.",
    "fetish": "특정 소품/연출 표현이 강해져 콘셉트 고정력은 높아지지만 범용성은 낮아집니다.",
}

_LOWER_EFFECT_BY_CATEGORY: dict[str, str] = {
    "style": "스타일 힌트만 남기고 기본 체크포인트의 구도/명암을 더 살릴 수 있습니다.",
    "eyes": "표정 과장과 디테일 과포화를 줄여 보다 자연스러운 결과를 얻기 쉽습니다.",
    "material": "질감은 유지하되 피부/의상 경계 노이즈를 줄여 안정적인 결과를 만들기 좋습니다.",
    "fetish": "과한 콘셉트 고정을 줄여 프롬프트의 다른 요소를 반영하기 쉬워집니다.",
}

_NEGATIVE_START_BY_CATEGORY: dict[str, float] = {
    "style": 0.2,
    "eyes": 0.15,
    "material": 0.25,
    "fetish": 0.3,
}

_NEGATIVE_LIMIT_BY_CATEGORY: dict[str, float] = {
    "style": 0.9,
    "eyes": 0.7,
    "material": 1.0,
    "fetish": 1.1,
}

_POSITIVE_SPAN_BY_CATEGORY: dict[str, float] = {
    "style": 0.2,
    "eyes": 0.15,
    "material": 0.18,
    "fetish": 0.2,
}

_POSITIVE_HIGH_CAP_BY_CATEGORY: dict[str, float] = {
    "style": 1.1,
    "eyes": 0.95,
    "material": 1.0,
    "fetish": 1.05,
}

_STRENGTH_BUCKETS: list[dict[str, Any]] = [
    {
        "id": "light",
        "label": "0.00 - 0.80 (Light)",
        "min_total": 0.0,
        "max_total": 0.8,
        "target": 0.4,
        "guidance": "기본 체크포인트 질감을 유지하고 LoRA는 약한 힌트만 주는 구간",
    },
    {
        "id": "balanced",
        "label": "0.80 - 1.60 (Balanced)",
        "min_total": 0.8,
        "max_total": 1.6,
        "target": 1.2,
        "guidance": "스타일/질감 효과가 분명하게 보이면서도 안정성이 높은 구간",
    },
    {
        "id": "strong",
        "label": "1.60 - 2.40 (Strong)",
        "min_total": 1.6,
        "max_total": 2.4,
        "target": 2.0,
        "guidance": "의도한 콘셉트를 강하게 밀어붙이는 구간 (현재 권장 상한 포함)",
    },
    {
        "id": "aggressive",
        "label": "2.40 - 3.20 (Aggressive)",
        "min_total": 2.4,
        "max_total": 3.2,
        "target": 2.8,
        "guidance": "충돌/과포화 위험이 증가하는 구간, 세밀한 튜닝이 필요",
    },
    {
        "id": "extreme",
        "label": "3.20+ (Extreme)",
        "min_total": 3.2,
        "max_total": None,
        "target": 3.8,
        "guidance": "실험적 영역. 표현 왜곡/불안정 가능성이 높아 레퍼런스 실험 용도 권장",
    },
]


def _parse_json(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _build_empty_usage() -> dict[str, Any]:
    return {
        "runs": 0,
        "sum_strength": 0.0,
        "sum_abs_strength": 0.0,
        "negative_runs": 0,
        "min_strength": None,
        "max_strength": None,
        "by_checkpoint": {},
    }


def _pick_strength_bucket(total_abs_strength: float) -> dict[str, Any]:
    for bucket in _STRENGTH_BUCKETS:
        max_total = bucket["max_total"]
        if max_total is None:
            if total_abs_strength >= bucket["min_total"]:
                return bucket
            continue
        if bucket["min_total"] <= total_abs_strength < max_total:
            return bucket
    return _STRENGTH_BUCKETS[0]


@router.get("", response_model=List[LoraProfileResponse])
async def list_loras(
    request: Request,
    checkpoint: str | None = Query(default=None),
) -> List[LoraProfileResponse]:
    """Return LoRA profiles, optionally filtered by checkpoint compatibility."""
    client = request.app.state.comfyui_client
    available_files = set(await client.get_lora_files())

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM lora_profiles ORDER BY category, display_name"
        )
        rows = await cursor.fetchall()

    result: list[LoraProfileResponse] = []
    for row in rows:
        if available_files and row["filename"] not in available_files:
            continue
        if checkpoint and not is_checkpoint_compatible(
            row.get("compatible_checkpoints"), checkpoint
        ):
            continue
        result.append(
            LoraProfileResponse(
                id=row["id"],
                display_name=row["display_name"],
                filename=row["filename"],
                category=row["category"],
                default_strength=row["default_strength"],
                tags=row.get("tags"),
                notes=row.get("notes"),
                compatible_checkpoints=parse_compatible_checkpoints(
                    row.get("compatible_checkpoints")
                ),
                created_at=row["created_at"],
            )
        )
    return result


@router.post(
    "/select",
    response_model=MoodSelectResponse,
    status_code=status.HTTP_200_OK,
)
async def select_loras(req: MoodSelectRequest, request: Request) -> MoodSelectResponse:
    """Smart LoRA selection based on mood keywords."""
    client = request.app.state.comfyui_client
    available_files = set(await client.get_lora_files())

    async with get_db() as db:
        loras, prompt_additions = await select_by_moods(
            db,
            req.moods,
            req.checkpoint,
            available_files if available_files else None,
        )
    return MoodSelectResponse(loras=loras, prompt_additions=prompt_additions)


@router.get("/guide")
async def get_lora_guide(
    request: Request,
    checkpoint: str | None = Query(default=None),
) -> dict[str, Any]:
    """Return data-driven LoRA usage guide with compatibility rationale."""
    client = request.app.state.comfyui_client
    checkpoints = await client.get_models()
    lora_files = await client.get_lora_files()
    checkpoint_arches, lora_analysis = build_lora_compatibility_snapshot(
        checkpoints, lora_files
    )

    async with get_db() as db:
        lora_cursor = await db.execute(
            "SELECT * FROM lora_profiles ORDER BY category, display_name"
        )
        lora_rows = await lora_cursor.fetchall()

        gen_cursor = await db.execute(
            """
            SELECT id, checkpoint, loras, thumbnail_path, prompt, created_at
            FROM generations
            WHERE status = 'completed'
            ORDER BY datetime(created_at) DESC
            LIMIT 800
            """
        )
        gen_rows = await gen_cursor.fetchall()

    lora_file_set = set(lora_files)
    lora_profiles: dict[str, dict[str, Any]] = {
        row["filename"]: row
        for row in lora_rows
        if row.get("filename") in lora_file_set
    }
    for lora_file in lora_files:
        lora_profiles.setdefault(
            lora_file,
            {
                "id": lora_file,
                "display_name": lora_file,
                "filename": lora_file,
                "category": lora_analysis.get(lora_file).category
                if lora_analysis.get(lora_file)
                else "style",
                "default_strength": lora_analysis.get(lora_file).default_strength
                if lora_analysis.get(lora_file)
                else 0.7,
                "compatible_checkpoints": None,
            },
        )

    checkpoint_generation_counts: dict[str, int] = {cp: 0 for cp in checkpoints}
    usage_by_lora: dict[str, dict[str, Any]] = {}
    strength_examples: dict[str, dict[str, Any]] = {}

    for row in gen_rows:
        row_checkpoint = row.get("checkpoint")
        if isinstance(row_checkpoint, str):
            checkpoint_generation_counts[row_checkpoint] = (
                checkpoint_generation_counts.get(row_checkpoint, 0) + 1
            )

        parsed_loras: list[dict[str, Any]] = []
        total_abs_strength = 0.0
        raw_loras = _parse_json(row.get("loras"), [])
        if not isinstance(raw_loras, list):
            raw_loras = []

        for item in raw_loras:
            if not isinstance(item, dict):
                continue
            filename = str(item.get("filename", "")).strip()
            if not filename:
                continue
            strength = _to_float(item.get("strength"), 0.0)
            total_abs_strength += abs(strength)
            parsed_loras.append(
                {
                    "filename": filename,
                    "strength": round(strength, 3),
                    "category": item.get("category"),
                }
            )

            usage = usage_by_lora.setdefault(filename, _build_empty_usage())
            usage["runs"] += 1
            usage["sum_strength"] += strength
            usage["sum_abs_strength"] += abs(strength)
            usage["negative_runs"] += 1 if strength < 0 else 0

            min_strength = usage.get("min_strength")
            max_strength = usage.get("max_strength")
            usage["min_strength"] = (
                strength if min_strength is None else min(min_strength, strength)
            )
            usage["max_strength"] = (
                strength if max_strength is None else max(max_strength, strength)
            )

            if isinstance(row_checkpoint, str):
                cp_usage = usage["by_checkpoint"].setdefault(
                    row_checkpoint,
                    {
                        "runs": 0,
                        "sum_strength": 0.0,
                        "sum_abs_strength": 0.0,
                        "negative_runs": 0,
                    },
                )
                cp_usage["runs"] += 1
                cp_usage["sum_strength"] += strength
                cp_usage["sum_abs_strength"] += abs(strength)
                cp_usage["negative_runs"] += 1 if strength < 0 else 0

        thumbnail_path = row.get("thumbnail_path")
        if thumbnail_path:
            bucket = _pick_strength_bucket(total_abs_strength)
            key = bucket["id"]
            distance = abs(total_abs_strength - float(bucket["target"]))
            existing = strength_examples.get(key)
            if existing is None or distance < existing["distance"]:
                strength_examples[key] = {
                    "distance": distance,
                    "generation_id": row["id"],
                    "checkpoint": row.get("checkpoint"),
                    "total_abs_strength": round(total_abs_strength, 3),
                    "thumbnail_path": thumbnail_path,
                    "prompt": row.get("prompt"),
                    "loras": parsed_loras,
                    "created_at": row.get("created_at"),
                }

    checkpoint_entries = [
        {
            "name": checkpoint_name,
            "architecture": checkpoint_arches.get(checkpoint_name, "Unknown"),
            "completed_generations": checkpoint_generation_counts.get(
                checkpoint_name, 0
            ),
        }
        for checkpoint_name in checkpoints
    ]
    checkpoint_entries.sort(
        key=lambda item: (-item["completed_generations"], item["name"])
    )

    lora_entries: list[dict[str, Any]] = []
    for filename, profile in lora_profiles.items():
        analysis = lora_analysis.get(filename)
        category = str(profile.get("category") or (analysis.category if analysis else "style"))
        base_strength = _to_float(
            profile.get("default_strength"),
            analysis.default_strength if analysis else 0.7,
        )
        compatible = parse_compatible_checkpoints(profile.get("compatible_checkpoints"))
        if compatible is None:
            compatible = analysis.compatible_checkpoints if analysis else checkpoints
        compatible = [cp for cp in compatible if cp in checkpoints]

        usage = usage_by_lora.get(filename) or _build_empty_usage()
        runs = int(usage["runs"])
        avg_strength = (
            round(usage["sum_strength"] / runs, 3) if runs > 0 else None
        )

        span = _POSITIVE_SPAN_BY_CATEGORY.get(category, 0.2)
        positive_high_cap = _POSITIVE_HIGH_CAP_BY_CATEGORY.get(category, 1.0)
        low_strength = round(_clamp(base_strength - span, 0.1, 2.0), 2)
        high_strength = round(_clamp(base_strength + span, 0.2, positive_high_cap), 2)
        reverse_start = round(
            -_NEGATIVE_START_BY_CATEGORY.get(category, 0.2),
            2,
        )
        reverse_limit = round(
            -_NEGATIVE_LIMIT_BY_CATEGORY.get(category, 0.9),
            2,
        )

        fit_entries: list[dict[str, Any]] = []
        for checkpoint_name in compatible:
            cp_usage = usage["by_checkpoint"].get(checkpoint_name)
            cp_runs = int(cp_usage["runs"]) if cp_usage else 0
            cp_avg_strength = (
                round(cp_usage["sum_strength"] / cp_runs, 3)
                if cp_usage and cp_runs > 0
                else None
            )

            cp_arch = checkpoint_arches.get(checkpoint_name, "Unknown")
            lora_arch = analysis.architecture if analysis else "Unknown"
            score = 60.0
            reasons = []

            if lora_arch != "Unknown" and cp_arch != "Unknown":
                score += 12.0
                reasons.append(
                    f"아키텍처 정합: {lora_arch} LoRA ↔ {cp_arch} 체크포인트"
                )
            else:
                reasons.append("아키텍처 메타데이터가 불완전하여 파일명/키 패턴 기반으로 추정됨")

            if cp_runs > 0:
                score += min(30.0, cp_runs * 3.5)
                reasons.append(
                    f"로컬 사용 이력: {cp_runs}회, 평균 strength {cp_avg_strength:+.2f}"
                )
            else:
                reasons.append("로컬 사용 이력은 없지만 호환 체크포인트 목록에 포함됨")

            if avg_strength is not None and low_strength <= abs(avg_strength) <= high_strength:
                score += 5.0
                reasons.append("평균 사용 강도가 권장 구간과 근접")
            elif avg_strength is not None and abs(avg_strength) > high_strength + 0.35:
                score -= 6.0
                reasons.append("평균 사용 강도가 높은 편이라 과적용 리스크 점검 필요")

            fit_entries.append(
                {
                    "checkpoint": checkpoint_name,
                    "score": round(score, 1),
                    "runs": cp_runs,
                    "avg_strength": cp_avg_strength,
                    "reasons": reasons,
                }
            )

        fit_entries.sort(key=lambda item: (-item["score"], -item["runs"], item["checkpoint"]))

        if checkpoint:
            fit_entries = [fit for fit in fit_entries if fit["checkpoint"] == checkpoint]
            if not fit_entries:
                continue

        lora_entries.append(
            {
                "id": profile.get("id"),
                "filename": filename,
                "display_name": profile.get("display_name") or filename,
                "category": category,
                "architecture": analysis.architecture if analysis else "Unknown",
                "compatible_checkpoints": compatible,
                "strength": {
                    "low": low_strength,
                    "base": round(base_strength, 2),
                    "high": high_strength,
                    "reverse_start": reverse_start,
                    "reverse_limit": reverse_limit,
                },
                "usage": {
                    "total_runs": runs,
                    "avg_strength": avg_strength,
                    "avg_abs_strength": round(usage["sum_abs_strength"] / runs, 3)
                    if runs > 0
                    else None,
                    "negative_runs": int(usage["negative_runs"]),
                    "min_strength": usage["min_strength"],
                    "max_strength": usage["max_strength"],
                },
                "raise_effect": _RAISE_EFFECT_BY_CATEGORY.get(
                    category, _RAISE_EFFECT_BY_CATEGORY["style"]
                ),
                "lower_effect": _LOWER_EFFECT_BY_CATEGORY.get(
                    category, _LOWER_EFFECT_BY_CATEGORY["style"]
                ),
                "checkpoint_fits": fit_entries,
            }
        )

    lora_entries.sort(
        key=lambda item: (
            item["category"],
            -item["usage"]["total_runs"],
            item["display_name"].lower(),
        )
    )

    strength_example_entries: list[dict[str, Any]] = []
    for bucket in _STRENGTH_BUCKETS:
        picked = strength_examples.get(bucket["id"])
        strength_example_entries.append(
            {
                "bucket_id": bucket["id"],
                "label": bucket["label"],
                "min_total": bucket["min_total"],
                "max_total": bucket["max_total"],
                "guidance": bucket["guidance"],
                "generation_id": picked["generation_id"] if picked else None,
                "checkpoint": picked["checkpoint"] if picked else None,
                "total_abs_strength": picked["total_abs_strength"] if picked else None,
                "thumbnail_path": picked["thumbnail_path"] if picked else None,
                "prompt": picked["prompt"] if picked else None,
                "loras": picked["loras"] if picked else [],
            }
        )

    if checkpoint:
        checkpoint_entries = [item for item in checkpoint_entries if item["name"] == checkpoint]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "max_total_strength": MAX_TOTAL_STRENGTH,
        "checkpoints": checkpoint_entries,
        "loras": lora_entries,
        "strength_examples": strength_example_entries,
    }
