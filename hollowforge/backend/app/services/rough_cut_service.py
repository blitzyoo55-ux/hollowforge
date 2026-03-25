"""Rough-cut timeline assembly for ordered shot clips."""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.config import settings
from app.models import RoughCutCreate
from app.services.sequence_repository import (
    create_rough_cut,
    get_run,
    list_shot_clips,
    list_shots,
    select_rough_cut_for_run,
)


class RoughCutAssemblyError(RuntimeError):
    """Raised when a rough cut cannot be assembled."""


def sort_shot_clips(clips: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(clip) for clip in clips), key=lambda clip: int(clip["shot_no"]))


def build_rough_cut_timeline(clips: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    cursor = 0.0
    for clip in sort_shot_clips(clips):
        duration = float(clip.get("clip_duration_sec") or 0.0)
        timeline.append(
            {
                "sequence_shot_id": clip.get("sequence_shot_id"),
                "shot_no": int(clip["shot_no"]),
                "clip_path": str(clip["clip_path"]),
                "clip_duration_sec": duration,
                "start_sec": round(cursor, 6),
            }
        )
        cursor += duration
    return timeline


def _resolve_clip_path(clip_path: str) -> Path:
    path = Path(clip_path)
    if path.is_absolute():
        return path
    return settings.DATA_DIR / clip_path


def _manifest_line(path: Path) -> str:
    return "file '{}'\n".format(str(path).replace("'", "'\\''"))


def build_concat_manifest(timeline: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        _manifest_line(_resolve_clip_path(str(entry["clip_path"]))) for entry in timeline
    )


async def _run_ffmpeg(manifest_path: Path, output_path: Path) -> None:
    cmd = [
        settings.HOLLOWFORGE_SEQUENCE_FFMPEG_BIN,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest_path),
        "-c",
        "copy",
        str(output_path),
    ]

    def _invoke() -> None:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )

    try:
        await asyncio.to_thread(_invoke)
    except FileNotFoundError as exc:
        raise RoughCutAssemblyError(
            f"ffmpeg binary not found: {settings.HOLLOWFORGE_SEQUENCE_FFMPEG_BIN}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "ffmpeg failed"
        raise RoughCutAssemblyError(stderr) from exc


class RoughCutService:
    """Build and persist an ordered rough cut for a sequence run."""

    async def assemble(self, *, sequence_run_id: str) -> dict[str, Any]:
        run = await get_run(sequence_run_id)
        if run is None:
            raise ValueError(f"Unknown sequence run: {sequence_run_id}")

        ordered_clips: list[dict[str, Any]] = []
        for shot in await list_shots(sequence_run_id):
            clip_rows = await list_shot_clips(shot.id)
            selected = next((row for row in clip_rows if row.get("clip_path")), None)
            if selected is None:
                raise RoughCutAssemblyError(
                    f"Shot {shot.shot_no} has no rendered clip for rough-cut assembly"
                )
            ordered_clips.append(
                {
                    **selected,
                    "sequence_shot_id": shot.id,
                    "shot_no": shot.shot_no,
                }
            )

        timeline = build_rough_cut_timeline(ordered_clips)
        output_dir = settings.DATA_DIR / "sequence_runs" / sequence_run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "rough_cut_manifest.txt"
        output_path = output_dir / "rough_cut.mp4"
        manifest_path.write_text(build_concat_manifest(timeline), encoding="utf-8")

        await _run_ffmpeg(manifest_path, output_path)

        try:
            output_rel_path = str(output_path.relative_to(settings.DATA_DIR))
        except ValueError:
            output_rel_path = str(output_path)

        total_duration = round(
            sum(float(entry["clip_duration_sec"]) for entry in timeline),
            6,
        )
        rough_cut = await create_rough_cut(
            RoughCutCreate(
                sequence_run_id=run.id,
                content_mode=run.content_mode,
                policy_profile_id=run.policy_profile_id,
                output_path=output_rel_path,
                timeline_json=timeline,
                total_duration_sec=total_duration,
            )
        )
        await select_rough_cut_for_run(run.id, rough_cut.id)
        return {
            "rough_cut": rough_cut,
            "manifest_path": str(manifest_path),
            "timeline": timeline,
        }
