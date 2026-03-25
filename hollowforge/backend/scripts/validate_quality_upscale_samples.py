#!/usr/bin/env python3
"""Validate staged quality upscale workflow against Hollow Forge samples."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.services.comfyui_client import ComfyUIClient  # noqa: E402
from app.services.upscaler import recommend_upscale_model  # noqa: E402
from app.services.workflow_builder import (  # noqa: E402
    QUALITY_UPSCALE_REQUIRED_NODES,
    build_quality_upscale_workflow,
    compute_quality_redraw_dimensions,
)

DEFAULT_IDS = [
    "c996c2ef-049c-4afd-b816-40cc29ceaac9",
    "8c3fb245-658b-4c03-8b51-db25aa2d2d31",
    "0e6c5bb8-d9c3-4366-abcf-da9939c0432c",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", default=DEFAULT_IDS)
    parser.add_argument("--recent-limit", type=int, default=0)
    parser.add_argument("--max-per-checkpoint", type=int, default=2)
    parser.add_argument("--pause-seconds", type=float, default=5.0)
    parser.add_argument("--output", default="")
    return parser.parse_args()


def _fetch_rows_by_ids(conn: sqlite3.Connection, ids: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for gen_id in ids:
        row = conn.execute(
            """
            SELECT id, checkpoint, prompt, negative_prompt, seed, cfg, image_path
            FROM generations
            WHERE id = ?
            """,
            (gen_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Generation not found: {gen_id}")
        rows.append(dict(row))
    return rows


def _fetch_recent_rows(
    conn: sqlite3.Connection,
    recent_limit: int,
    max_per_checkpoint: int,
) -> list[dict[str, object]]:
    query = """
        SELECT id, checkpoint, prompt, negative_prompt, seed, cfg, image_path
        FROM generations
        WHERE status = 'completed'
          AND image_path IS NOT NULL
        ORDER BY created_at DESC
        LIMIT ?
    """
    selected: list[dict[str, object]] = []
    per_checkpoint: dict[str, int] = {}
    for row in conn.execute(query, (max(recent_limit * 4, recent_limit),)):
        item = dict(row)
        checkpoint = str(item.get("checkpoint") or "")
        used = per_checkpoint.get(checkpoint, 0)
        if used >= max_per_checkpoint:
            continue
        selected.append(item)
        per_checkpoint[checkpoint] = used + 1
        if len(selected) >= recent_limit:
            break
    return selected


def load_rows(ids: list[str], recent_limit: int, max_per_checkpoint: int) -> list[dict[str, object]]:
    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if recent_limit > 0:
            rows = _fetch_recent_rows(conn, recent_limit, max_per_checkpoint)
            if not rows:
                raise RuntimeError("No recent completed generations found for validation")
            return rows
        return _fetch_rows_by_ids(conn, ids)


def build_output_path(raw: str) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (
        settings.DATA_DIR
        / "validation"
        / "upscale_quality"
        / f"quality_validation_{stamp}.json"
    )


def write_result(out_path: Path, result: dict[str, object]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


async def main() -> int:
    args = parse_args()
    rows = load_rows(args.ids, args.recent_limit, args.max_per_checkpoint)
    result_path = build_output_path(args.output)
    client = ComfyUIClient()
    result: dict[str, object] = {
        "comfyui_url": client.base_url,
        "health": await client.check_health(),
        "required_nodes": list(QUALITY_UPSCALE_REQUIRED_NODES),
        "missing_nodes": await client.missing_nodes(QUALITY_UPSCALE_REQUIRED_NODES),
        "pause_seconds": args.pause_seconds,
        "output_path": str(result_path),
        "sample_count": len(rows),
        "sample_ids": [str(row["id"]) for row in rows],
        "samples": [],
    }
    write_result(result_path, result)

    if not result["health"] or result["missing_nodes"]:
        for row in rows:
            model, profile = recommend_upscale_model(str(row.get("checkpoint")))
            result["samples"].append(
                {
                    "id": row["id"],
                    "checkpoint": row["checkpoint"],
                    "recommended_model": model,
                    "recommended_profile": profile,
                    "status": "blocked",
                }
            )
        write_result(result_path, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        await client.close()
        return 0

    output_dir = settings.DATA_DIR / "validation" / "upscale_quality"
    output_dir.mkdir(parents=True, exist_ok=True)

    for row in rows:
        checkpoint = str(row.get("checkpoint") or settings.DEFAULT_CHECKPOINT)
        recommended_model, profile = recommend_upscale_model(checkpoint)
        if not recommended_model:
            result["samples"].append(
                {
                    "id": row["id"],
                    "checkpoint": checkpoint,
                    "status": "blocked",
                    "reason": "No recommended upscale model available",
                }
            )
            continue

        source_path = (settings.DATA_DIR / str(row["image_path"])).resolve()
        if not source_path.is_file():
            result["samples"].append(
                {
                    "id": row["id"],
                    "checkpoint": checkpoint,
                    "recommended_model": recommended_model,
                    "recommended_profile": profile,
                    "status": "missing_source",
                    "source_path": str(source_path),
                }
            )
            continue

        try:
            upload_filename = f"hollowforge_quality_{row['id']}.png"
            comfy_filename = await client.upload_image(str(source_path), upload_filename)
            with Image.open(source_path) as source_image:
                redraw_width, redraw_height = compute_quality_redraw_dimensions(
                    source_image.width,
                    source_image.height,
                    max_side=1024,
                )
            workflow, save_node = build_quality_upscale_workflow(
                image_filename=comfy_filename,
                upscale_model=recommended_model,
                checkpoint=checkpoint,
                positive_prompt=str(row.get("prompt") or ""),
                negative_prompt=str(row.get("negative_prompt") or ""),
                seed=int(row.get("seed") or 42),
                cfg=min(float(row.get("cfg") or 5.5), 5.0),
                steps=10,
                denoise=0.16,
                redraw_width=redraw_width,
                redraw_height=redraw_height,
                filename_prefix=f"hollowforge_quality_validation_{str(row['id'])[:8]}",
            )
            prompt_id = await client.submit_prompt(workflow)
            images = await client.wait_for_completion(prompt_id, save_node, timeout=300.0)
            if not images:
                result["samples"].append(
                    {
                        "id": row["id"],
                        "checkpoint": checkpoint,
                        "recommended_model": recommended_model,
                        "recommended_profile": profile,
                        "status": "no_output",
                        "redraw_width": redraw_width,
                        "redraw_height": redraw_height,
                    }
                )
                write_result(result_path, result)
                if args.pause_seconds > 0:
                    await asyncio.sleep(args.pause_seconds)
                continue
            image_bytes = await client.download_image(images[0])
            image_out_path = output_dir / f"{row['id']}_quality.png"
            image_out_path.write_bytes(image_bytes)
            result["samples"].append(
                {
                    "id": row["id"],
                    "checkpoint": checkpoint,
                    "recommended_model": recommended_model,
                    "recommended_profile": profile,
                    "status": "ok",
                    "output_rel": str(image_out_path.relative_to(settings.DATA_DIR)),
                    "redraw_width": redraw_width,
                    "redraw_height": redraw_height,
                }
            )
        except Exception as exc:
            result["samples"].append(
                {
                    "id": row["id"],
                    "checkpoint": checkpoint,
                    "recommended_model": recommended_model,
                    "recommended_profile": profile,
                    "status": "error",
                    "error": str(exc),
                }
            )
        write_result(result_path, result)
        if args.pause_seconds > 0:
            await asyncio.sleep(args.pause_seconds)

    await client.close()
    write_result(result_path, result)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
