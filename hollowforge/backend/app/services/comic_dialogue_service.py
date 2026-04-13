"""Comic panel dialogue generation helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from app.config import settings
from app.db import get_db
from app.models import (
    ComicDialogueGenerationResponse,
    ComicPanelDialogueCreate,
    ComicPanelDialogueResponse,
    ComicScenePanelResponse,
    SequenceContentMode,
)
from app.services.sequence_registry import get_prompt_provider_profile


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dialogue_response(row: dict[str, Any]) -> ComicPanelDialogueResponse:
    return ComicPanelDialogueResponse.model_validate(row)


async def _fetch_panel_context(
    panel_id: str,
) -> tuple[ComicScenePanelResponse, dict[str, Any], SequenceContentMode]:
    async with get_db() as db:
        panel_cursor = await db.execute(
            "SELECT * FROM comic_scene_panels WHERE id = ?",
            (panel_id,),
        )
        panel_row = await panel_cursor.fetchone()
        if panel_row is None:
            raise ValueError(f"Comic panel not found: {panel_id}")

        scene_cursor = await db.execute(
            """
            SELECT s.*, e.content_mode AS episode_content_mode
            FROM comic_episode_scenes s
            JOIN comic_episodes e ON e.id = s.episode_id
            WHERE s.id = ?
            """,
            (panel_row["episode_scene_id"],),
        )
        scene_row = await scene_cursor.fetchone()
        if scene_row is None:
            raise ValueError(
                f"Comic scene not found for panel {panel_id}: {panel_row['episode_scene_id']}"
            )

    scene_payload = dict(scene_row)
    involved_character_ids = scene_payload.get("involved_character_ids")
    if isinstance(involved_character_ids, str):
        try:
            parsed = json.loads(involved_character_ids)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid JSON list in comic_episode_scenes.involved_character_ids"
            ) from exc
        if not isinstance(parsed, list):
            raise ValueError(
                "Invalid JSON list in comic_episode_scenes.involved_character_ids"
            )
        scene_payload["involved_character_ids"] = parsed

    return (
        ComicScenePanelResponse.model_validate(panel_row),
        scene_payload,
        scene_payload.get("episode_content_mode") or "all_ages",
    )


def _resolve_dialogue_profile_id(content_mode: SequenceContentMode) -> str:
    if content_mode == "adult_nsfw":
        return settings.HOLLOWFORGE_SEQUENCE_DEFAULT_ADULT_PROMPT_PROFILE
    return settings.HOLLOWFORGE_SEQUENCE_DEFAULT_SAFE_PROMPT_PROFILE


async def _fetch_existing_dialogues(
    panel_id: str,
) -> list[ComicPanelDialogueResponse]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT *
            FROM comic_panel_dialogues
            WHERE scene_panel_id = ?
            ORDER BY priority ASC, id ASC
            """,
            (panel_id,),
        )
        rows = await cursor.fetchall()
    return [_dialogue_response(dict(row)) for row in rows]


def _draft_panel_dialogue_payloads(
    *,
    panel: ComicScenePanelResponse,
    scene: dict[str, Any],
    prompt_provider_profile: dict[str, Any],
    existing_dialogues: list[ComicPanelDialogueResponse],
) -> list[dict[str, Any]]:
    del existing_dialogues

    lead_speaker = None
    involved_character_ids = scene.get("involved_character_ids")
    if isinstance(involved_character_ids, list) and involved_character_ids:
        lead_speaker = involved_character_ids[0]

    prompt_context = json.dumps(
        {
            "panel_id": panel.id,
            "panel_type": panel.panel_type,
            "framing": panel.framing,
            "camera_intent": panel.camera_intent,
            "action_intent": panel.action_intent,
            "expression_intent": panel.expression_intent,
            "dialogue_intent": panel.dialogue_intent,
            "scene_premise": scene.get("premise"),
            "profile_id": prompt_provider_profile.get("id"),
        },
        ensure_ascii=False,
    )
    del prompt_context

    base_text = panel.dialogue_intent or panel.action_intent or scene.get("premise") or "A quiet beat lands."
    caption_text = scene.get("premise") or "The moment narrows in silence."
    sfx_text = "tap" if "tap" not in base_text.lower() else "tap"

    return [
        {
            "type": "speech",
            "speaker_character_id": lead_speaker,
            "text": f"{base_text}。",
            "tone": "measured",
            "priority": 10,
            "balloon_style_hint": "rounded speech balloon",
            "placement_hint": "upper left",
        },
        {
            "type": "caption",
            "speaker_character_id": None,
            "text": caption_text,
            "tone": "observational",
            "priority": 20,
            "balloon_style_hint": "caption box",
            "placement_hint": "top edge",
        },
        {
            "type": "sfx",
            "speaker_character_id": None,
            "text": sfx_text,
            "tone": "soft",
            "priority": 30,
            "balloon_style_hint": "small sound effect",
            "placement_hint": "near action",
        },
    ]


def _build_dialogue_generation_messages(
    *,
    panel: ComicScenePanelResponse,
    scene: dict[str, Any],
    content_mode: SequenceContentMode,
) -> list[dict[str, Any]]:
    mode_instruction = (
        "adult comic panel dialogue"
        if content_mode == "adult_nsfw"
        else "all-ages comic panel dialogue"
    )
    return [
        {
            "role": "system",
            "content": (
                f"You are drafting {mode_instruction} in Japanese comic format. "
                "Return JSON only with a top-level 'dialogues' array."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "panel": panel.model_dump(mode="json"),
                    "scene": scene,
                    "requirements": [
                        "Generate speech, caption, and sfx lines as separate rows when appropriate.",
                        "Keep output concise and production-ready.",
                    ],
                },
                ensure_ascii=False,
            ),
        },
    ]


def _parse_dialogue_payloads(raw_content: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError("Failed to parse local LLM dialogue response as JSON") from exc

    if isinstance(parsed, dict):
        dialogues = parsed.get("dialogues")
    else:
        dialogues = parsed

    if not isinstance(dialogues, list):
        raise ValueError("Local LLM dialogue response must include a dialogues array")

    return [item for item in dialogues if isinstance(item, dict)]


def _validate_dialogue_payloads(
    *,
    panel_id: str,
    payloads: list[dict[str, Any]],
) -> list[ComicPanelDialogueCreate]:
    validated: list[ComicPanelDialogueCreate] = []
    for payload in payloads:
        validated.append(
            ComicPanelDialogueCreate.model_validate(
                {"scene_panel_id": panel_id, **payload}
            )
        )
    return validated


async def _draft_panel_dialogue_payloads_with_local_llm_profile(
    *,
    panel: ComicScenePanelResponse,
    scene: dict[str, Any],
    prompt_provider_profile: dict[str, Any],
    existing_dialogues: list[ComicPanelDialogueResponse],
) -> list[dict[str, Any]]:
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError:
        return _draft_panel_dialogue_payloads(
            panel=panel,
            scene=scene,
            prompt_provider_profile=prompt_provider_profile,
            existing_dialogues=existing_dialogues,
        )

    try:
        client = AsyncOpenAI(
            base_url=settings.HOLLOWFORGE_SEQUENCE_LOCAL_LLM_BASE_URL,
            api_key="local_llm",
        )
        content_mode = cast(
            SequenceContentMode,
            prompt_provider_profile.get("content_mode") or "all_ages",
        )
        completion = await client.chat.completions.create(
            model=settings.HOLLOWFORGE_SEQUENCE_LOCAL_LLM_MODEL,
            messages=_build_dialogue_generation_messages(
                panel=panel,
                scene=scene,
                content_mode=content_mode,
            ),
        )
        raw_content = ""
        try:
            raw_content = completion.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError) as exc:
            raise ValueError("Local LLM returned an unexpected response format") from exc
        if isinstance(raw_content, list):
            text_parts: list[str] = []
            for part in raw_content:
                text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                if isinstance(text, str):
                    text_parts.append(text)
            raw_content = "".join(text_parts)
        payloads = _parse_dialogue_payloads(str(raw_content).strip())
        if payloads:
            return payloads
    except Exception:  # noqa: BLE001
        pass

    return _draft_panel_dialogue_payloads(
        panel=panel,
        scene=scene,
        prompt_provider_profile=prompt_provider_profile,
        existing_dialogues=existing_dialogues,
    )


async def _persist_dialogue_payloads(
    *,
    panel_id: str,
    payloads: list[ComicPanelDialogueCreate],
    overwrite_existing: bool = False,
) -> list[ComicPanelDialogueResponse]:
    now = _now_iso()
    inserted_ids: list[str] = []

    async with get_db() as db:
        await db.execute("BEGIN")
        try:
            if overwrite_existing:
                await db.execute(
                    "DELETE FROM comic_panel_dialogues WHERE scene_panel_id = ?",
                    (panel_id,),
                )
            for dialogue in payloads:
                dialogue_id = str(uuid.uuid4())
                inserted_ids.append(dialogue_id)
                await db.execute(
                    """
                    INSERT INTO comic_panel_dialogues (
                        id,
                        scene_panel_id,
                        type,
                        speaker_character_id,
                        text,
                        tone,
                        priority,
                        balloon_style_hint,
                        placement_hint,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dialogue_id,
                        dialogue.scene_panel_id,
                        dialogue.type,
                        dialogue.speaker_character_id,
                        dialogue.text,
                        dialogue.tone,
                        dialogue.priority,
                        dialogue.balloon_style_hint,
                        dialogue.placement_hint,
                        now,
                        now,
                    ),
                )
            await db.commit()
        except Exception:
            await db.rollback()
            raise

        rows: list[dict[str, Any]] = []
        if inserted_ids:
            placeholders = ",".join("?" for _ in inserted_ids)
            cursor = await db.execute(
                f"""
                SELECT *
                FROM comic_panel_dialogues
                WHERE id IN ({placeholders})
                ORDER BY priority ASC, id ASC
                """,
                inserted_ids,
            )
            rows = [dict(row) for row in await cursor.fetchall()]

    return [_dialogue_response(row) for row in rows]


async def generate_panel_dialogues(
    *,
    panel_id: str,
    overwrite_existing: bool = False,
) -> ComicDialogueGenerationResponse:
    panel, scene, content_mode = await _fetch_panel_context(panel_id)
    existing_dialogues = await _fetch_existing_dialogues(panel_id)
    prompt_provider_profile_id = _resolve_dialogue_profile_id(content_mode)

    if existing_dialogues and not overwrite_existing:
        return ComicDialogueGenerationResponse(
            panel=panel,
            dialogues=existing_dialogues,
            generated_count=len(existing_dialogues),
            overwrite_existing=overwrite_existing,
            prompt_provider_profile_id=prompt_provider_profile_id,
        )

    profile = get_prompt_provider_profile(
        prompt_provider_profile_id,
        content_mode=content_mode,
    )

    try:
        payloads = await _draft_panel_dialogue_payloads_with_local_llm_profile(
            panel=panel,
            scene=scene,
            prompt_provider_profile=profile,
            existing_dialogues=existing_dialogues,
        )
        validated_payloads = _validate_dialogue_payloads(
            panel_id=panel_id,
            payloads=payloads,
        )
        if not validated_payloads:
            raise ValueError("Local LLM produced no dialogue payloads")
    except Exception:
        fallback_payloads = _draft_panel_dialogue_payloads(
            panel=panel,
            scene=scene,
            prompt_provider_profile=profile,
            existing_dialogues=existing_dialogues,
        )
        validated_payloads = _validate_dialogue_payloads(
            panel_id=panel_id,
            payloads=fallback_payloads,
        )

    dialogues = await _persist_dialogue_payloads(
        panel_id=panel_id,
        payloads=validated_payloads,
        overwrite_existing=overwrite_existing,
    )
    return ComicDialogueGenerationResponse(
        panel=panel,
        dialogues=dialogues,
        generated_count=len(dialogues),
        overwrite_existing=overwrite_existing,
        prompt_provider_profile_id=profile["id"],
    )
