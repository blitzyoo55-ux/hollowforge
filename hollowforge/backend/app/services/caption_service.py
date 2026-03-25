"""Reusable image-to-caption generation helpers."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from app.config import settings

_MIME_TYPES_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}

_PLATFORM_BRIEFS = {
    "twitter": "Write for X/Twitter: concise, punchy, teaser-like, ideally 1-2 short sentences.",
    "fansly": "Write for subscriber feed copy: short, seductive, worldbuilding-forward, with mild CTA energy.",
    "pixiv": "Write for artwork post copy: slightly more descriptive, but still concise and atmospheric.",
    "generic": "Write for a short social/media post: concise, evocative, and easy to remix across channels.",
}

_TONE_BRIEFS = {
    "teaser": "Keep it steamy and suggestive, but avoid explicit anatomy or explicit sexual actions.",
    "clinical": "Lean into Lab-451 bureaucratic/clinical diction with fetish-coded implication.",
    "campaign": "Position the image as a lore drop or campaign teaser for the Lab-451 universe.",
}


def mime_type_from_image_path(image_path: str) -> str:
    return _MIME_TYPES_BY_SUFFIX.get(Path(image_path).suffix.lower(), "image/png")


def build_caption_system_prompt(
    *,
    platform: str = "twitter",
    tone: str = "teaser",
) -> str:
    platform_brief = _PLATFORM_BRIEFS.get(platform, _PLATFORM_BRIEFS["generic"])
    tone_brief = _TONE_BRIEFS.get(tone, _TONE_BRIEFS["teaser"])

    return (
        "You are the Head Archivist of Lab-451, a fictional dystopian black-site research facility. "
        "You analyze synthetic fetish-fashion imagery and produce polished social copy.\n\n"
        "Requirements:\n"
        f"1. {platform_brief}\n"
        f"2. {tone_brief}\n"
        "3. Keep the prose anchored in the Lab-451 universe: containment, compliance, sealed materials, "
        "classified protocols, unit/specimen language, and ominous procedural desire.\n"
        "4. Make the copy evocative and imagination-triggering; leave negative space rather than over-explaining.\n"
        "5. Avoid explicit mention of genitals, penetration, bodily fluids, or direct sexual acts.\n"
        "6. Include 8-16 relevant hashtags, mixing brand, mood, material, and AI-art tags.\n\n"
        "Output ONLY valid JSON with this exact structure:\n"
        '{"story":"...","hashtags":"#Tag1 #Tag2 ..."}'
    )


def _extract_response_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Marketing API returned an unexpected response format",
        ) from exc

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for part in content:
            text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
            if isinstance(text, str):
                text_parts.append(text)
        combined = "".join(text_parts).strip()
        if combined:
            return combined

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Marketing API returned empty content",
    )


def _parse_caption_json(raw_content: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to parse model response as JSON",
        ) from exc

    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Model response JSON must be an object",
        )

    story = parsed.get("story")
    hashtags = parsed.get("hashtags")
    if not isinstance(story, str) or not isinstance(hashtags, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Model response JSON must include string fields: story, hashtags",
        )

    return {"story": story.strip(), "hashtags": hashtags.strip()}


async def generate_caption_from_image_bytes(
    image_bytes: bytes,
    mime_type: str,
    *,
    platform: str = "twitter",
    tone: str = "teaser",
) -> dict[str, str]:
    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OPENROUTER_API_KEY is not configured",
        )
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image is empty",
        )

    encoded_image = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{encoded_image}"

    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="openai package is not installed in backend/.venv",
        ) from exc

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )

    try:
        completion = await client.chat.completions.create(
            model=settings.MARKETING_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": build_caption_system_prompt(platform=platform, tone=tone),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this image and return JSON output.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                },
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Marketing API request failed: {exc}",
        ) from exc

    raw_content = _extract_response_content(completion).strip()
    return _parse_caption_json(raw_content)
