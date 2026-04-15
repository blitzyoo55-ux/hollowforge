"""Comic page assembly and export helpers."""

from __future__ import annotations

import json
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.config import settings
from app.db import get_db
from app.models import (
    ComicManuscriptProfileId,
    ComicHandoffExportSummaryResponse,
    ComicHandoffPageSummaryResponse,
    ComicHandoffValidationIssueResponse,
    ComicHandoffValidationResponse,
    ComicPageAssemblyBatchResponse,
    ComicPageAssemblyResponse,
    ComicPageExportResponse,
    list_comic_manuscript_profiles,
)
from app.services.comic_repository import get_comic_episode_detail


_PAGE_LAYOUT_TEMPLATES: dict[str, dict[str, Any]] = {
    "jp_2x2_v1": {
        "panels_per_page": 4,
        "grid": (2, 2),
        "size": (1600, 2400),
        "margin": 72,
        "gap": 36,
    },
    "jp_3row_v1": {
        "panels_per_page": 3,
        "grid": (1, 3),
        "size": (1600, 2400),
        "margin": 80,
        "gap": 40,
    },
}

_PANEL_ASSET_SELECT_COLUMNS = """
    a.id,
    a.scene_panel_id,
    a.generation_id,
    a.asset_role,
    COALESCE(a.storage_path, g.upscaled_image_path, g.image_path) AS storage_path,
    a.prompt_snapshot,
    a.quality_score,
    a.bubble_safe_zones,
    a.crop_metadata,
    a.render_notes,
    a.is_selected,
    a.created_at,
    a.updated_at
"""

_CJK_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans W3.ttc"),
    Path("/System/Library/Fonts/Hiragino Sans W6.ttc"),
    Path("/Library/Fonts/AppleGothic.ttf"),
    Path("/System/Library/Fonts/AppleSDGothicNeo.ttc"),
    Path("/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"),
    "Noto Sans CJK JP",
    "Noto Sans JP",
    "NotoSansCJK-Regular.ttc",
    "Source Han Sans JP",
    "Yu Gothic",
    "YuGothic",
    "Hiragino Sans",
    "Hiragino Kaku Gothic ProN",
    "TakaoPGothic",
    "IPAGothic",
    "DejaVuSans.ttf",
    "Arial.ttf",
    "LiberationSans-Regular.ttf",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_font(font_size: int) -> ImageFont.ImageFont:
    for font_name in _CJK_FONT_CANDIDATES:
        if isinstance(font_name, Path) and not font_name.exists():
            continue
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _relative_data_path(path: Path) -> str:
    return str(path.resolve().relative_to(settings.DATA_DIR.resolve())).replace("\\", "/")


def _resolve_data_path(path_value: str) -> Path:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    return (settings.DATA_DIR / candidate).resolve()


def _resolve_layout_template(layout_template_id: str) -> dict[str, Any]:
    template = _PAGE_LAYOUT_TEMPLATES.get(layout_template_id)
    if template is None:
        raise ValueError(f"Unknown comic page layout template: {layout_template_id}")
    return template


def _resolve_manuscript_profile(
    profile_id: ComicManuscriptProfileId,
) -> dict[str, Any]:
    for profile in list_comic_manuscript_profiles():
        payload = profile.model_dump()
        if payload["id"] == profile_id:
            return payload
    raise ValueError(f"Unknown comic manuscript profile: {profile_id}")


def _decode_json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return value
    if isinstance(decoded, (dict, list)):
        return decoded
    return value


def _normalize_render_asset_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    payload["prompt_snapshot"] = _decode_json_value(payload.get("prompt_snapshot"))
    payload["bubble_safe_zones"] = _decode_json_value(payload.get("bubble_safe_zones"))
    payload["crop_metadata"] = _decode_json_value(payload.get("crop_metadata"))
    payload["is_selected"] = bool(payload.get("is_selected"))
    return payload


async def _fetch_dialogues_for_panels(
    panel_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not panel_ids:
        return {}

    placeholders = ",".join("?" for _ in panel_ids)
    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT *
            FROM comic_panel_dialogues
            WHERE scene_panel_id IN ({placeholders})
            ORDER BY scene_panel_id ASC, priority ASC, id ASC
            """,
            panel_ids,
        )
        rows = await cursor.fetchall()

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["scene_panel_id"], []).append(
            row
        )
    return grouped


async def _fetch_assets_for_panels(panel_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not panel_ids:
        return {}

    placeholders = ",".join("?" for _ in panel_ids)
    async with get_db() as db:
        cursor = await db.execute(
            f"""
            SELECT {_PANEL_ASSET_SELECT_COLUMNS}
            FROM comic_panel_render_assets a
            LEFT JOIN generations g ON g.id = a.generation_id
            WHERE a.scene_panel_id IN ({placeholders})
            ORDER BY a.scene_panel_id ASC, a.is_selected DESC, a.quality_score DESC, a.updated_at DESC, a.id ASC
            """,
            panel_ids,
        )
        rows = await cursor.fetchall()

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["scene_panel_id"], []).append(
            _normalize_render_asset_row(row)
        )
    return grouped


def _selected_asset_for_panel(panel_assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for asset in panel_assets:
        if bool(asset.get("is_selected")):
            return asset
    return None


def _resolve_selected_assets_for_panels(
    *,
    episode_id: str,
    panels: list[dict[str, Any]],
    assets_by_panel: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    selected_assets: dict[str, dict[str, Any]] = {}
    panels_missing_selection: list[str] = []
    panels_missing_files: list[str] = []

    for panel in panels:
        panel_id = str(panel["id"])
        selected_asset = _selected_asset_for_panel(assets_by_panel.get(panel_id, []))
        if selected_asset is None:
            panels_missing_selection.append(panel_id)
            continue

        storage_path = str(selected_asset.get("storage_path") or "").strip()
        if not storage_path:
            panels_missing_files.append(f"{panel_id}:pending_render")
            continue

        file_path = _resolve_data_path(storage_path)
        if not file_path.is_file():
            panels_missing_files.append(f"{panel_id}:{storage_path}")
            continue

        selected_assets[panel_id] = {
            **selected_asset,
            "storage_path": (
                _relative_data_path(file_path)
                if file_path.is_relative_to(settings.DATA_DIR.resolve())
                else str(file_path)
            ),
        }

    if panels_missing_selection:
        raise ValueError(
            "Comic episode "
            f"{episode_id} requires a selected render asset for every panel before page assembly: "
            + ", ".join(panels_missing_selection)
        )
    if panels_missing_files:
        raise ValueError(
            "Comic episode "
            f"{episode_id} requires materialized render files for selected assets before page assembly: "
            + ", ".join(panels_missing_files)
        )

    return selected_assets


def _split_panels_into_pages(
    panels: list[dict[str, Any]],
    panels_per_page: int,
) -> list[list[dict[str, Any]]]:
    pages: list[list[dict[str, Any]]] = []
    current_page: list[dict[str, Any]] = []
    current_page_target_hint: int | None = None

    for panel in panels:
        panel_target_hint = panel.get("page_target_hint")
        if current_page:
            page_is_full = len(current_page) >= panels_per_page
            target_break = (
                panel_target_hint is not None
                and current_page_target_hint is not None
                and panel_target_hint != current_page_target_hint
            )
            if page_is_full or target_break:
                pages.append(current_page)
                current_page = []
                current_page_target_hint = None

        if not current_page:
            current_page_target_hint = panel_target_hint
        elif current_page_target_hint is None and panel_target_hint is not None:
            current_page_target_hint = panel_target_hint

        current_page.append(panel)

    if current_page:
        pages.append(current_page)

    return pages


def _measure_text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return max(1, bbox[2] - bbox[0])


def _wrap_paragraph_words(
    draw: ImageDraw.ImageDraw,
    paragraph: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = paragraph.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _measure_text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        lines.append(current)
        if _measure_text_width(draw, word, font) <= max_width:
            current = word
            continue
        lines.extend(_wrap_paragraph_chars(draw, word, font, max_width))
        current = ""
    if current:
        lines.append(current)
    return lines


def _wrap_paragraph_chars(
    draw: ImageDraw.ImageDraw,
    paragraph: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    if not paragraph:
        return [""]

    lines: list[str] = []
    current = ""
    for char in paragraph:
        candidate = f"{current}{char}"
        if current and _measure_text_width(draw, candidate, font) > max_width:
            lines.append(current)
            current = char
            continue
        current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    paragraphs = text.splitlines() or [text]
    lines: list[str] = []
    for paragraph in paragraphs:
        if not paragraph:
            lines.append("")
            continue
        if " " in paragraph:
            lines.extend(_wrap_paragraph_words(draw, paragraph, font, max_width))
        else:
            lines.extend(_wrap_paragraph_chars(draw, paragraph, font, max_width))
    return lines or [""]


def _normalize_panel_asset_manifest_entries(
    panel_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_entries: list[dict[str, Any]] = []
    for entry in panel_entries:
        normalized_assets = [
            _normalize_render_asset_row(asset)
            for asset in entry.get("assets", [])
            if isinstance(asset, dict)
        ]
        normalized_entries.append(
            {
                "panel_id": entry.get("panel_id"),
                "page_no": entry.get("page_no"),
                "assets": normalized_assets,
            }
        )
    return normalized_entries


def _render_page_preview(
    *,
    episode_id: str,
    page_no: int,
    layout_template_id: str,
    page_panels: list[dict[str, Any]],
    dialogues_by_panel: dict[str, list[dict[str, Any]]],
    selected_assets_by_panel: dict[str, dict[str, Any]],
) -> str:
    template = _resolve_layout_template(layout_template_id)
    page_size = template["size"]
    margin = template["margin"]
    gap = template["gap"]
    columns, rows = template["grid"]
    panel_width = int((page_size[0] - margin * 2 - gap * (columns - 1)) / columns)
    panel_height = int((page_size[1] - margin * 2 - gap * (rows - 1)) / rows)

    image = Image.new("RGB", page_size, "#F7F1E4")
    draw = ImageDraw.Draw(image)
    title_font = _load_font(42)
    body_font = _load_font(28)
    small_font = _load_font(22)

    draw.text(
        (margin, 26),
        f"Episode {episode_id} - Page {page_no:02d} - {layout_template_id}",
        fill="#2c2319",
        font=title_font,
    )

    for index, panel in enumerate(page_panels):
        row = index // columns
        col = index % columns
        x0 = margin + col * (panel_width + gap)
        y0 = margin + 90 + row * (panel_height + gap)
        x1 = x0 + panel_width
        y1 = y0 + panel_height

        selected_asset = selected_assets_by_panel[panel["id"]]
        asset_path = _resolve_data_path(str(selected_asset["storage_path"]))

        with Image.open(asset_path) as asset_image:
            fitted = ImageOps.fit(asset_image.convert("RGB"), (panel_width - 8, panel_height - 8))
        image.paste(fitted, (x0 + 4, y0 + 4))

        draw.rounded_rectangle((x0, y0, x1, y1), radius=26, outline="#3d2e1f", width=4)

        header = f"P{panel['panel_no']} · {panel['panel_type']}"
        overlay_top = max(y0 + 52, y1 - 220)
        draw.rounded_rectangle(
            (x0 + 16, overlay_top, x1 - 16, y1 - 16),
            radius=18,
            fill="#fffdf8",
            outline="#3d2e1f",
            width=2,
        )
        draw.text((x0 + 28, overlay_top + 18), header, fill="#5a4633", font=small_font)

        body_y = overlay_top + 58
        lines = [
            panel.get("framing") or "",
            panel.get("action_intent") or "",
            panel.get("expression_intent") or "",
        ]
        panel_dialogues = dialogues_by_panel.get(panel["id"], [])
        if panel_dialogues:
            lines.extend(
                f"{dialogue['type']}: {dialogue['text']}" for dialogue in panel_dialogues[:3]
            )

        for raw_line in lines:
            if not raw_line:
                continue
            wrapped_lines = _wrap_text(draw, raw_line, body_font, panel_width - 48)
            for line in wrapped_lines[:4]:
                draw.text((x0 + 24, body_y), line, fill="#1f1a15", font=body_font)
                body_y += 34
            body_y += 8

    preview_dir = settings.COMICS_PREVIEWS_DIR
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / f"{episode_id}_{layout_template_id}_page_{page_no:02d}.png"
    image.save(preview_path, format="PNG")
    return _relative_data_path(preview_path)


def _page_row_payload(
    *,
    episode_id: str,
    page_no: int,
    layout_template_id: str,
    manuscript_profile_id: ComicManuscriptProfileId,
    ordered_panel_ids: list[str],
    preview_path: str,
    manifest_entry: dict[str, Any],
) -> dict[str, Any]:
    now = _now_iso()
    return {
        "id": str(uuid.uuid4()),
        "episode_id": episode_id,
        "page_no": page_no,
        "layout_template_id": layout_template_id,
        "manuscript_profile_id": manuscript_profile_id,
        "ordered_panel_ids": ordered_panel_ids,
        "export_state": "preview_ready",
        "preview_path": preview_path,
        "master_path": None,
        "export_manifest": manifest_entry,
        "created_at": now,
        "updated_at": now,
    }


def _write_json_manifest(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return _relative_data_path(path)


def _write_markdown_artifact(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return _relative_data_path(path)


def _write_handoff_readme(
    path: Path,
    *,
    episode_detail,
    layout_template_id: str,
    manuscript_profile: dict[str, Any],
    page_count: int,
) -> str:
    content = "\n".join(
        [
            f"# Comic Handoff: {episode_detail.episode.title}",
            "",
            f"- Episode ID: `{episode_detail.episode.id}`",
            f"- Character ID: `{episode_detail.episode.character_id}`",
            f"- Character Version ID: `{episode_detail.episode.character_version_id}`",
            f"- Layout Template: `{layout_template_id}`",
            f"- Manuscript Profile: `{manuscript_profile['id']}`",
            f"- Finishing Tool: `{manuscript_profile['finishing_tool']}`",
            f"- Binding Direction: `{manuscript_profile['binding_direction']}`",
            f"- Page Count: `{page_count}`",
            "",
            "## Included Artifacts",
            "",
            "- Page assembly manifest",
            "- Dialogue JSON",
            "- Panel asset manifest",
            "- Teaser handoff manifest",
            "- Manuscript profile manifest",
            "- Production checklist",
            "- Page preview images",
            "- Selected render asset files",
        ]
    )
    return _write_markdown_artifact(path, content)


def _write_production_checklist(
    path: Path,
    *,
    episode_id: str,
    layout_template_id: str,
    manuscript_profile: dict[str, Any],
    page_count: int,
) -> str:
    payload = {
        "episode_id": episode_id,
        "layout_template_id": layout_template_id,
        "manuscript_profile_id": manuscript_profile["id"],
        "page_count": page_count,
        "checks": [
            {
                "id": "verify-page-order",
                "label": "Confirm right-to-left page order and exported page count.",
                "status": "pending",
            },
            {
                "id": "import-clip-studio",
                "label": "Import final selected assets into CLIP STUDIO EX manuscript pages.",
                "status": "pending",
            },
            {
                "id": "apply-dialogue",
                "label": "Rebuild dialogue balloons and SFX using the exported dialogue JSON as reference.",
                "status": "pending",
            },
            {
                "id": "print-safe-review",
                "label": f"Check trim/bleed/safe area against {manuscript_profile['trim_reference']}.",
                "status": "pending",
            },
        ],
    }
    return _write_json_manifest(path, payload)


def _count_layer_statuses(
    page_summary: ComicHandoffPageSummaryResponse,
) -> tuple[int, int]:
    hard_block_count = sum(
        1
        for status in (
            page_summary.art_layer_status,
            page_summary.frame_layer_status,
            page_summary.balloon_layer_status,
            page_summary.text_draft_layer_status,
        )
        if status == "blocked"
    )
    soft_warning_count = sum(
        1
        for status in (
            page_summary.art_layer_status,
            page_summary.frame_layer_status,
            page_summary.balloon_layer_status,
            page_summary.text_draft_layer_status,
        )
        if status == "warning"
    )
    return hard_block_count, soft_warning_count


def _build_handoff_page_summary(
    *,
    page_no: int,
    preview_path: str,
    ordered_panel_ids: list[str],
) -> ComicHandoffPageSummaryResponse:
    art_layer_status = (
        "complete"
        if (settings.DATA_DIR / preview_path).is_file()
        else "blocked"
    )
    frame_layer_status = "complete" if ordered_panel_ids else "blocked"
    balloon_layer_status = "warning" if ordered_panel_ids else "blocked"
    text_draft_layer_status = "warning" if ordered_panel_ids else "blocked"

    summary = ComicHandoffPageSummaryResponse(
        page_id=f"page_{page_no:03d}",
        page_no=page_no,
        art_layer_status=art_layer_status,
        frame_layer_status=frame_layer_status,
        balloon_layer_status=balloon_layer_status,
        text_draft_layer_status=text_draft_layer_status,
        hard_block_count=0,
        soft_warning_count=0,
    )
    hard_block_count, soft_warning_count = _count_layer_statuses(summary)
    return summary.model_copy(
        update={
            "hard_block_count": hard_block_count,
            "soft_warning_count": soft_warning_count,
        }
    )


def _write_layered_package(
    *,
    episode_id: str,
    layout_template_id: str,
    manuscript_profile_id: ComicManuscriptProfileId,
    page_rows: list[dict[str, Any]],
    page_groups: list[list[dict[str, Any]]],
    selected_assets_by_panel: dict[str, dict[str, Any]],
) -> tuple[
    str,
    str,
    list[ComicHandoffPageSummaryResponse],
    ComicHandoffValidationResponse,
]:
    package_root = (
        settings.COMICS_MANIFESTS_DIR
        / f"{episode_id}_{layout_template_id}_layered_handoff"
    )
    package_root.mkdir(parents=True, exist_ok=True)

    layered_manifest_file = package_root / "manifest.json"
    handoff_validation_file = package_root / "handoff_validation.json"
    layered_manifest_path = _relative_data_path(layered_manifest_file)
    handoff_validation_path = _relative_data_path(handoff_validation_file)

    page_summaries: list[ComicHandoffPageSummaryResponse] = []
    hard_blocks: list[ComicHandoffValidationIssueResponse] = []
    soft_warnings: list[ComicHandoffValidationIssueResponse] = []

    for page_row, page_panels in zip(page_rows, page_groups):
        page_no = int(page_row["page_no"])
        page_id = f"page_{page_no:03d}"
        ordered_panel_ids = [panel["id"] for panel in page_panels]
        summary = _build_handoff_page_summary(
            page_no=page_no,
            preview_path=str(page_row["preview_path"]),
            ordered_panel_ids=ordered_panel_ids,
        )
        page_summaries.append(summary)

        page_dir = package_root / "pages" / page_id
        page_manifest_payload = {
            "episode_id": episode_id,
            "layout_template_id": layout_template_id,
            "manuscript_profile_id": manuscript_profile_id,
            "page_id": page_id,
            "page_no": page_no,
            "preview_path": page_row["preview_path"],
            "page_summary": summary.model_dump(),
            "panel_ids": ordered_panel_ids,
            "selected_asset_paths": [
                selected_assets_by_panel[panel_id]["storage_path"]
                for panel_id in ordered_panel_ids
            ],
        }
        _write_json_manifest(page_dir / "page_manifest.json", page_manifest_payload)
        _write_json_manifest(
            page_dir / "frame_layer.json",
            {
                "page_id": page_id,
                "page_no": page_no,
                "status": summary.frame_layer_status,
                "panel_ids": ordered_panel_ids,
            },
        )
        _write_json_manifest(
            page_dir / "balloon_layer.json",
            {
                "page_id": page_id,
                "page_no": page_no,
                "status": summary.balloon_layer_status,
                "panel_ids": ordered_panel_ids,
            },
        )
        _write_json_manifest(
            page_dir / "text_draft_layer.json",
            {
                "page_id": page_id,
                "page_no": page_no,
                "status": summary.text_draft_layer_status,
                "panel_ids": ordered_panel_ids,
            },
        )

        for panel in page_panels:
            panel_id = str(panel["id"])
            panel_dir = package_root / "panels" / f"panel_{panel_id}"
            selected_asset = selected_assets_by_panel[panel_id]
            _write_json_manifest(
                panel_dir / "panel_manifest.json",
                {
                    "episode_id": episode_id,
                    "layout_template_id": layout_template_id,
                    "page_id": page_id,
                    "page_no": page_no,
                    "panel_id": panel_id,
                    "panel_no": panel["panel_no"],
                    "generation_id": selected_asset.get("generation_id"),
                    "asset_id": selected_asset.get("id"),
                    "storage_path": selected_asset.get("storage_path"),
                },
            )

        for layer_name, status in (
            ("art_layer_status", summary.art_layer_status),
            ("frame_layer_status", summary.frame_layer_status),
            ("balloon_layer_status", summary.balloon_layer_status),
            ("text_draft_layer_status", summary.text_draft_layer_status),
        ):
            if status == "blocked":
                hard_blocks.append(
                    ComicHandoffValidationIssueResponse(
                        code="layer_blocked",
                        page_id=page_id,
                        page_no=page_no,
                        layer=layer_name,
                    )
                )
            elif status == "warning":
                soft_warnings.append(
                    ComicHandoffValidationIssueResponse(
                        code="layer_warning",
                        page_id=page_id,
                        page_no=page_no,
                        layer=layer_name,
                    )
                )

    validation = ComicHandoffValidationResponse(
        episode_id=episode_id,
        hard_blocks=hard_blocks,
        soft_warnings=soft_warnings,
        page_summaries=page_summaries,
        generated_at=_now_iso(),
    )
    _write_json_manifest(
        layered_manifest_file,
        {
            "episode_id": episode_id,
            "layout_template_id": layout_template_id,
            "manuscript_profile_id": manuscript_profile_id,
            "page_count": len(page_summaries),
            "page_summaries": [summary.model_dump() for summary in page_summaries],
            "handoff_validation_path": handoff_validation_path,
            "generated_at": validation.generated_at,
        },
    )
    _write_json_manifest(handoff_validation_file, validation.model_dump())
    return layered_manifest_path, handoff_validation_path, page_summaries, validation


async def assemble_episode_pages(
    *,
    episode_id: str,
    layout_template_id: str = "jp_2x2_v1",
    manuscript_profile_id: ComicManuscriptProfileId = "jp_manga_rightbound_v1",
) -> ComicPageAssemblyBatchResponse:
    template = _resolve_layout_template(layout_template_id)
    manuscript_profile = _resolve_manuscript_profile(manuscript_profile_id)
    episode_detail = await get_comic_episode_detail(episode_id)
    if episode_detail is None:
        raise ValueError(f"Comic episode not found: {episode_id}")

    panels: list[dict[str, Any]] = []
    for scene_detail in episode_detail.scenes:
        for panel in scene_detail.panels:
            panels.append(panel.model_dump())

    if not panels:
        raise ValueError(f"Comic episode {episode_id} has no panels to assemble")

    panel_ids = [panel["id"] for panel in panels]
    dialogues_by_panel = await _fetch_dialogues_for_panels(panel_ids)
    assets_by_panel = await _fetch_assets_for_panels(panel_ids)
    selected_assets_by_panel = _resolve_selected_assets_for_panels(
        episode_id=episode_id,
        panels=panels,
        assets_by_panel=assets_by_panel,
    )
    page_groups = _split_panels_into_pages(panels, template["panels_per_page"])

    settings.COMICS_PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    settings.COMICS_MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    async with get_db() as db:
        await db.execute(
            "DELETE FROM comic_page_assemblies WHERE episode_id = ?",
            (episode_id,),
        )

        page_rows: list[dict[str, Any]] = []
        page_manifest_pages: list[dict[str, Any]] = []
        dialogue_entries: list[dict[str, Any]] = []
        panel_asset_entries: list[dict[str, Any]] = []
        teaser_handoff_entries: list[dict[str, Any]] = []

        for page_no, page_panels in enumerate(page_groups, start=1):
            ordered_panel_ids = [panel["id"] for panel in page_panels]
            preview_path = _render_page_preview(
                episode_id=episode_id,
                page_no=page_no,
                layout_template_id=layout_template_id,
                page_panels=page_panels,
                dialogues_by_panel=dialogues_by_panel,
                selected_assets_by_panel=selected_assets_by_panel,
            )
            manifest_entry = {
                "page_no": page_no,
                "panel_ids": ordered_panel_ids,
                "preview_path": preview_path,
                "template": layout_template_id,
                "manuscript_profile_id": manuscript_profile_id,
                "selected_asset_paths": [
                    selected_assets_by_panel[panel_id]["storage_path"]
                    for panel_id in ordered_panel_ids
                ],
            }
            page_row = _page_row_payload(
                episode_id=episode_id,
                page_no=page_no,
                layout_template_id=layout_template_id,
                manuscript_profile_id=manuscript_profile_id,
                ordered_panel_ids=ordered_panel_ids,
                preview_path=preview_path,
                manifest_entry=manifest_entry,
            )
            page_rows.append(page_row)
            page_manifest_pages.append(manifest_entry)

            await db.execute(
                """
                INSERT INTO comic_page_assemblies (
                    id,
                    episode_id,
                    page_no,
                    layout_template_id,
                    manuscript_profile_id,
                    ordered_panel_ids,
                    export_state,
                    preview_path,
                    master_path,
                    export_manifest,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page_row["id"],
                    page_row["episode_id"],
                    page_row["page_no"],
                    page_row["layout_template_id"],
                    page_row["manuscript_profile_id"],
                    json.dumps(page_row["ordered_panel_ids"], ensure_ascii=False),
                    page_row["export_state"],
                    page_row["preview_path"],
                    page_row["master_path"],
                    json.dumps(page_row["export_manifest"], ensure_ascii=False),
                    page_row["created_at"],
                    page_row["updated_at"],
                ),
            )

            for panel in page_panels:
                dialogue_entries.append(
                    {
                        "panel_id": panel["id"],
                        "page_no": page_no,
                        "dialogues": dialogues_by_panel.get(panel["id"], []),
                    }
                )
                panel_asset_entries.append(
                    {
                        "panel_id": panel["id"],
                        "page_no": page_no,
                        "assets": assets_by_panel.get(panel["id"], []),
                    }
                )
                selected_asset = selected_assets_by_panel[panel["id"]]
                teaser_handoff_entries.append(
                    {
                        "page_no": page_no,
                        "panel_id": panel["id"],
                        "panel_no": panel["panel_no"],
                        "generation_id": selected_asset.get("generation_id"),
                        "asset_id": selected_asset.get("id"),
                        "storage_path": selected_asset.get("storage_path"),
                    }
                )

        await db.commit()

    dialogue_json_path = _write_json_manifest(
        settings.COMICS_MANIFESTS_DIR / f"{episode_id}_{layout_template_id}_dialogues.json",
        {
            "episode_id": episode_id,
            "layout_template_id": layout_template_id,
            "manuscript_profile_id": manuscript_profile_id,
            "dialogues": dialogue_entries,
        },
    )
    panel_asset_manifest_path = _write_json_manifest(
        settings.COMICS_MANIFESTS_DIR / f"{episode_id}_{layout_template_id}_panel_assets.json",
        {
            "episode_id": episode_id,
            "layout_template_id": layout_template_id,
            "manuscript_profile_id": manuscript_profile_id,
            "panels": _normalize_panel_asset_manifest_entries(panel_asset_entries),
        },
    )
    page_assembly_manifest_path = _write_json_manifest(
        settings.COMICS_MANIFESTS_DIR / f"{episode_id}_{layout_template_id}_pages.json",
        {
            "episode_id": episode_id,
            "layout_template_id": layout_template_id,
            "manuscript_profile_id": manuscript_profile_id,
            "pages": page_manifest_pages,
            "created_at": _now_iso(),
        },
    )
    teaser_handoff_manifest_path = _write_json_manifest(
        settings.COMICS_MANIFESTS_DIR / f"{episode_id}_{layout_template_id}_teaser_handoff.json",
        {
            "episode_id": episode_id,
            "character_id": episode_detail.episode.character_id,
            "character_version_id": episode_detail.episode.character_version_id,
            "target_output": episode_detail.episode.target_output,
            "derivative_target": "teaser_animation",
            "layout_template_id": layout_template_id,
            "manuscript_profile_id": manuscript_profile_id,
            "selected_panel_assets": teaser_handoff_entries,
            "created_at": _now_iso(),
        },
    )
    manuscript_profile_manifest_path = _write_json_manifest(
        settings.COMICS_MANIFESTS_DIR
        / f"{episode_id}_{layout_template_id}_manuscript_profile.json",
        {
            "episode_id": episode_id,
            "layout_template_id": layout_template_id,
            "manuscript_profile": manuscript_profile,
            "created_at": _now_iso(),
        },
    )
    handoff_readme_path = _write_handoff_readme(
        settings.COMICS_MANIFESTS_DIR
        / f"{episode_id}_{layout_template_id}_handoff_readme.md",
        episode_detail=episode_detail,
        layout_template_id=layout_template_id,
        manuscript_profile=manuscript_profile,
        page_count=len(page_rows),
    )
    production_checklist_path = _write_production_checklist(
        settings.COMICS_MANIFESTS_DIR
        / f"{episode_id}_{layout_template_id}_production_checklist.json",
        episode_id=episode_id,
        layout_template_id=layout_template_id,
        manuscript_profile=manuscript_profile,
        page_count=len(page_rows),
    )

    (
        layered_manifest_path,
        handoff_validation_path,
        page_summaries,
        handoff_validation,
    ) = _write_layered_package(
        episode_id=episode_id,
        layout_template_id=layout_template_id,
        manuscript_profile_id=manuscript_profile_id,
        page_rows=page_rows,
        page_groups=page_groups,
        selected_assets_by_panel=selected_assets_by_panel,
    )

    pages = [
        ComicPageAssemblyResponse.model_validate(row)
        for row in page_rows
    ]
    return ComicPageAssemblyBatchResponse(
        episode_id=episode_id,
        layout_template_id=layout_template_id,
        manuscript_profile=manuscript_profile,
        pages=pages,
        export_manifest_path=page_assembly_manifest_path,
        layered_manifest_path=layered_manifest_path,
        handoff_validation_path=handoff_validation_path,
        handoff_validation=handoff_validation,
        page_summaries=page_summaries,
        latest_export_summary=None,
        dialogue_json_path=dialogue_json_path,
        panel_asset_manifest_path=panel_asset_manifest_path,
        page_assembly_manifest_path=page_assembly_manifest_path,
        teaser_handoff_manifest_path=teaser_handoff_manifest_path,
        manuscript_profile_manifest_path=manuscript_profile_manifest_path,
        handoff_readme_path=handoff_readme_path,
        production_checklist_path=production_checklist_path,
    )


def _collect_selected_asset_paths(teaser_handoff_manifest_path: str) -> list[str]:
    manifest_path = settings.DATA_DIR / teaser_handoff_manifest_path
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = payload.get("selected_panel_assets") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    selected_paths: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        storage_path = entry.get("storage_path")
        if isinstance(storage_path, str) and storage_path.strip():
            selected_paths.append(storage_path)
    return selected_paths


def _zip_manifest_artifacts(
    *,
    export_zip_path: Path,
    page_response: ComicPageAssemblyBatchResponse,
) -> None:
    export_zip_path.parent.mkdir(parents=True, exist_ok=True)

    artifact_paths = [
        page_response.dialogue_json_path,
        page_response.panel_asset_manifest_path,
        page_response.page_assembly_manifest_path,
        page_response.teaser_handoff_manifest_path,
        page_response.manuscript_profile_manifest_path,
        page_response.handoff_readme_path,
        page_response.production_checklist_path,
        page_response.layered_manifest_path,
        page_response.handoff_validation_path,
    ]

    layered_package_root = (settings.DATA_DIR / page_response.layered_manifest_path).parent
    archived_paths: set[str] = set()

    with zipfile.ZipFile(export_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path in artifact_paths:
            file_path = settings.DATA_DIR / relative_path
            if file_path.is_file():
                archive.write(file_path, arcname=relative_path)
                archived_paths.add(relative_path)

        if layered_package_root.is_dir():
            for file_path in sorted(
                path for path in layered_package_root.rglob("*") if path.is_file()
            ):
                relative_path = _relative_data_path(file_path)
                if relative_path in archived_paths:
                    continue
                archive.write(file_path, arcname=relative_path)
                archived_paths.add(relative_path)

        for page in page_response.pages:
            preview_path = settings.DATA_DIR / (page.preview_path or "")
            if preview_path.is_file():
                archive.write(preview_path, arcname=page.preview_path or preview_path.name)

        for storage_path in sorted(set(_collect_selected_asset_paths(page_response.teaser_handoff_manifest_path))):
            file_path = _resolve_data_path(storage_path)
            if not file_path.is_file():
                continue
            arcname = (
                storage_path
                if not Path(storage_path).is_absolute()
                else f"selected-assets/{file_path.name}"
            )
            archive.write(file_path, arcname=arcname)


async def export_episode_pages(
    *,
    episode_id: str,
    layout_template_id: str = "jp_2x2_v1",
    manuscript_profile_id: ComicManuscriptProfileId = "jp_manga_rightbound_v1",
) -> ComicPageExportResponse:
    page_response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id=layout_template_id,
        manuscript_profile_id=manuscript_profile_id,
    )
    hard_block_count = len(page_response.handoff_validation.hard_blocks)
    soft_warning_count = len(page_response.handoff_validation.soft_warnings)
    export_zip_path = settings.COMICS_EXPORTS_DIR / f"{episode_id}_{layout_template_id}_handoff.zip"
    _zip_manifest_artifacts(
        export_zip_path=export_zip_path,
        page_response=page_response,
    )
    exported_pages = [
        page.model_copy(update={"export_state": "exported"})
        for page in page_response.pages
    ]
    async with get_db() as db:
        await db.execute(
            """
            UPDATE comic_page_assemblies
            SET export_state = ?, updated_at = ?
            WHERE episode_id = ?
            """,
            ("exported", _now_iso(), episode_id),
        )
        await db.commit()
    exported_batch = page_response.model_copy(update={"pages": exported_pages})
    latest_export_summary = ComicHandoffExportSummaryResponse(
        export_zip_path=_relative_data_path(export_zip_path),
        layered_manifest_path=page_response.layered_manifest_path,
        handoff_validation_path=page_response.handoff_validation_path,
        page_count=len(exported_pages),
        hard_block_count=hard_block_count,
        soft_warning_count=soft_warning_count,
        exported_at=_now_iso(),
    )
    return ComicPageExportResponse(
        **exported_batch.model_dump(exclude={"latest_export_summary"}),
        export_zip_path=_relative_data_path(export_zip_path),
        latest_export_summary=latest_export_summary,
    )
