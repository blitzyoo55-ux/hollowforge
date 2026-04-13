from __future__ import annotations

import json
import sqlite3

import pytest

from app.models import ComicEpisodeCreate
from app.services.comic_dialogue_service import generate_panel_dialogues
from app.services.comic_repository import create_comic_episode


def _now() -> str:
    return "2026-04-04T00:00:00+00:00"


async def _seed_panel(
    temp_db,
    *,
    involved_character_ids: list[str] | None = None,
    content_mode: str = "all_ages",
) -> str:
    if involved_character_ids is None:
        involved_character_ids = ["char_kaede_ren"]

    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="After Hours Entry",
            synopsis="Kaede studies a sealed invitation after closing.",
            content_mode=content_mode,
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_dialogue_test",
    )

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO comic_episode_scenes (
                id,
                episode_id,
                scene_no,
                premise,
                location_label,
                continuity_notes,
                involved_character_ids,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comic_scene_dialogue_test",
                episode.id,
                1,
                "Kaede studies the invitation.",
                "Private Lounge",
                "Stay restrained and intimate.",
                json.dumps(involved_character_ids),
                _now(),
                _now(),
            ),
        )
        conn.execute(
            """
            INSERT INTO comic_scene_panels (
                id,
                episode_scene_id,
                panel_no,
                panel_type,
                framing,
                camera_intent,
                action_intent,
                expression_intent,
                dialogue_intent,
                continuity_lock,
                page_target_hint,
                reading_order,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "comic_panel_dialogue_test",
                "comic_scene_dialogue_test",
                1,
                "beat",
                "tight waist-up portrait",
                "slightly low camera",
                "Kaede turns the invitation over in her hand.",
                "measured curiosity",
                "Placeholder dialogue intent for the generator.",
                "Stay on brand.",
                1,
                1,
                _now(),
                _now(),
            ),
        )
        conn.commit()

    return "comic_panel_dialogue_test"


@pytest.mark.asyncio
async def test_generate_panel_dialogues_uses_local_llm_profile_first_and_decodes_scene_cast(
    temp_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel_id = await _seed_panel(
        temp_db,
        involved_character_ids=["char_kaede_ren", "char_imani_adebayo"],
        content_mode="adult_nsfw",
    )

    call_state = {"called": False}

    async def _local_llm_helper(*, panel, scene, prompt_provider_profile, existing_dialogues):
        call_state["called"] = True
        assert prompt_provider_profile["id"] == "adult_local_llm"
        assert scene["involved_character_ids"] == [
            "char_kaede_ren",
            "char_imani_adebayo",
        ]
        assert existing_dialogues == []
        return [
            {
                "type": "speech",
                "speaker_character_id": "char_kaede_ren",
                "text": "The invitation is real.",
                "tone": "measured",
                "priority": 10,
                "balloon_style_hint": "rounded",
                "placement_hint": "upper left",
            }
        ]

    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads_with_local_llm_profile",
        _local_llm_helper,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads",
        lambda **_: [
            {
                "type": "speech",
                "speaker_character_id": "char_kaede_ren",
                "text": "Fallback text that should not be used.",
                "tone": "measured",
                "priority": 10,
                "balloon_style_hint": "rounded",
                "placement_hint": "upper left",
            }
        ],
    )

    response = await generate_panel_dialogues(panel_id=panel_id)

    assert call_state["called"] is True
    assert response.dialogues[0].text == "The invitation is real."
    assert response.prompt_provider_profile_id == "adult_local_llm"


@pytest.mark.asyncio
async def test_generate_panel_dialogues_uses_safe_profile_for_all_ages(
    temp_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel_id = await _seed_panel(temp_db)
    recorder: dict[str, object] = {}

    def _fake_get_prompt_provider_profile(profile_id: str, *, content_mode=None):
        recorder["profile_id"] = profile_id
        recorder["content_mode"] = content_mode
        return {"id": profile_id}

    async def _local_llm_helper(*, panel, scene, prompt_provider_profile, existing_dialogues):
        return [
            {
                "type": "speech",
                "speaker_character_id": "char_kaede_ren",
                "text": "Keep this line safe.",
                "tone": "measured",
                "priority": 10,
                "balloon_style_hint": "rounded",
                "placement_hint": "upper left",
            }
        ]

    monkeypatch.setattr(
        "app.services.comic_dialogue_service.get_prompt_provider_profile",
        _fake_get_prompt_provider_profile,
    )
    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads_with_local_llm_profile",
        _local_llm_helper,
        raising=False,
    )

    response = await generate_panel_dialogues(panel_id=panel_id)

    assert recorder["profile_id"] == "safe_hosted_grok"
    assert recorder["content_mode"] == "all_ages"
    assert response.prompt_provider_profile_id == "safe_hosted_grok"


@pytest.mark.asyncio
async def test_generate_panel_dialogues_persists_three_separate_rows(
    temp_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel_id = await _seed_panel(temp_db, content_mode="adult_nsfw")

    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads",
        lambda **_: [
            {
                "type": "speech",
                "speaker_character_id": "char_kaede_ren",
                "text": "I know what this invitation means.",
                "tone": "measured",
                "priority": 10,
                "balloon_style_hint": "rounded",
                "placement_hint": "upper left",
            },
            {
                "type": "caption",
                "speaker_character_id": None,
                "text": "The lounge stays quiet after closing.",
                "tone": "observational",
                "priority": 20,
                "balloon_style_hint": None,
                "placement_hint": "top edge",
            },
            {
                "type": "sfx",
                "speaker_character_id": None,
                "text": "tap",
                "tone": "soft",
                "priority": 30,
                "balloon_style_hint": None,
                "placement_hint": "near hand",
            },
        ],
    )

    response = await generate_panel_dialogues(panel_id=panel_id)

    assert response.panel.id == panel_id
    assert response.generated_count == 3
    assert [dialogue.type for dialogue in response.dialogues] == [
        "speech",
        "caption",
        "sfx",
    ]

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """
            SELECT type, speaker_character_id, text
            FROM comic_panel_dialogues
            WHERE scene_panel_id = ?
            ORDER BY priority ASC, id ASC
            """,
            (panel_id,),
        ).fetchall()

    assert rows == [
        ("speech", "char_kaede_ren", "I know what this invitation means."),
        ("caption", None, "The lounge stays quiet after closing."),
        ("sfx", None, "tap"),
    ]


@pytest.mark.asyncio
async def test_generate_panel_dialogues_overwrite_existing_still_uses_local_llm_first(
    temp_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel_id = await _seed_panel(temp_db, content_mode="adult_nsfw")

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
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
                "comic_dialogue_existing_1",
                panel_id,
                "speech",
                "char_kaede_ren",
                "Existing line",
                "measured",
                10,
                "rounded",
                "upper left",
                _now(),
                _now(),
            ),
        )
        conn.commit()

    call_state = {"called": False}

    async def _local_llm_helper(*, panel, scene, prompt_provider_profile, existing_dialogues):
        call_state["called"] = True
        assert prompt_provider_profile["id"] == "adult_local_llm"
        assert len(existing_dialogues) == 1
        return [
            {
                "type": "speech",
                "speaker_character_id": "char_kaede_ren",
                "text": "Regenerated via local profile.",
                "tone": "measured",
                "priority": 10,
                "balloon_style_hint": "rounded",
                "placement_hint": "upper left",
            }
        ]

    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads_with_local_llm_profile",
        _local_llm_helper,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads",
        lambda **_: [
            {
                "type": "speech",
                "speaker_character_id": "char_kaede_ren",
                "text": "Fallback regen text that should not be used.",
                "tone": "measured",
                "priority": 10,
                "balloon_style_hint": "rounded",
                "placement_hint": "upper left",
            }
        ],
    )

    response = await generate_panel_dialogues(
        panel_id=panel_id,
        overwrite_existing=True,
    )

    assert call_state["called"] is True
    assert response.dialogues[0].text == "Regenerated via local profile."


@pytest.mark.asyncio
async def test_generate_panel_dialogues_invalid_local_payload_falls_back_without_losing_existing_rows(
    temp_db, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel_id = await _seed_panel(temp_db, content_mode="adult_nsfw")

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
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
                "comic_dialogue_existing_badflow_1",
                panel_id,
                "speech",
                "char_kaede_ren",
                "Existing line",
                "measured",
                10,
                "rounded",
                "upper left",
                _now(),
                _now(),
            ),
        )
        conn.commit()

    call_state = {"local_called": False, "fallback_called": False}

    async def _local_llm_helper(*, panel, scene, prompt_provider_profile, existing_dialogues):
        call_state["local_called"] = True
        assert prompt_provider_profile["id"] == "adult_local_llm"
        assert len(existing_dialogues) == 1
        return [
            {
                "type": "speech",
                "speaker_character_id": "char_kaede_ren",
                "priority": 10,
            }
        ]

    def _fallback_helper(**_):
        call_state["fallback_called"] = True
        raise ValueError("fallback failed")

    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads_with_local_llm_profile",
        _local_llm_helper,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.comic_dialogue_service._draft_panel_dialogue_payloads",
        _fallback_helper,
    )

    with pytest.raises(ValueError, match="fallback failed"):
        await generate_panel_dialogues(
            panel_id=panel_id,
            overwrite_existing=True,
        )

    assert call_state["local_called"] is True
    assert call_state["fallback_called"] is True

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """
            SELECT text
            FROM comic_panel_dialogues
            WHERE scene_panel_id = ?
            ORDER BY priority ASC, id ASC
            """,
            (panel_id,),
        ).fetchall()

    assert rows == [("Existing line",)]
