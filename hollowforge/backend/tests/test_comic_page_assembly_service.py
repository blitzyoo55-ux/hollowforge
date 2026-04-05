from __future__ import annotations

import json
import sqlite3
import zipfile

import pytest
from PIL import Image, ImageFont

from app.config import settings
from app.models import ComicEpisodeCreate
from app.services.comic_page_assembly_service import (
    _load_font,
    _wrap_text,
    assemble_episode_pages,
    export_episode_pages,
)
from app.services.comic_repository import create_comic_episode


def _now() -> str:
    return "2026-04-04T00:00:00+00:00"


async def _seed_episode_with_panels(
    temp_db,
    panel_count: int = 5,
    page_target_hints: list[int | None] | None = None,
) -> str:
    episode = await create_comic_episode(
        ComicEpisodeCreate(
            character_id="char_kaede_ren",
            character_version_id="charver_kaede_ren_still_v1",
            title="After Hours Entry",
            synopsis="Kaede studies a sealed invitation after closing.",
            target_output="oneshot_manga",
        ),
        episode_id="comic_ep_page_assembly_test",
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
                "comic_scene_page_assembly_test",
                episode.id,
                1,
                "Kaede studies the invitation.",
                "Private Lounge",
                "Stay restrained and intimate.",
                '["char_kaede_ren"]',
                _now(),
                _now(),
            ),
        )
        for index in range(panel_count):
            panel_no = index + 1
            page_target_hint = (
                page_target_hints[index]
                if page_target_hints is not None
                else 1
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
                    f"comic_panel_page_assembly_test_{panel_no}",
                    "comic_scene_page_assembly_test",
                    panel_no,
                    "beat",
                    f"framing {panel_no}",
                    "slightly low camera",
                    f"Action {panel_no}",
                    f"Expression {panel_no}",
                    f"Dialogue intent {panel_no}",
                    "Stay on brand.",
                    page_target_hint,
                    panel_no,
                    _now(),
                    _now(),
                ),
            )
        conn.commit()

    return episode.id


def _insert_panel_asset_fixture(temp_db, panel_id: str) -> None:
    fixture_path = settings.IMAGES_DIR / f"{panel_id}.png"
    Image.new("RGB", (64, 64), "#6b4eff").save(fixture_path, format="PNG")
    relative_path = fixture_path.resolve().relative_to(settings.DATA_DIR.resolve()).as_posix()

    with sqlite3.connect(temp_db) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            INSERT INTO comic_panel_render_assets (
                id,
                scene_panel_id,
                generation_id,
                asset_role,
                storage_path,
                prompt_snapshot,
                quality_score,
                bubble_safe_zones,
                crop_metadata,
                render_notes,
                is_selected,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"comic_panel_render_asset_fixture_{panel_id}",
                panel_id,
                "gen-ready-1",
                "selected",
                relative_path,
                json.dumps({"prompt": "panel", "style": ["jp", "local"]}),
                0.95,
                json.dumps([{"x": 12, "y": 24, "w": 240, "h": 180}]),
                json.dumps({"crop_mode": "fit", "anchor": "center"}),
                "Selected asset for manifest normalization.",
                1,
                _now(),
                _now(),
            ),
        )
        conn.commit()


def _seed_selected_assets(temp_db, *, panel_count: int) -> None:
    for index in range(panel_count):
        _insert_panel_asset_fixture(temp_db, f"comic_panel_page_assembly_test_{index + 1}")


@pytest.mark.asyncio
async def test_assemble_episode_pages_creates_preview_files_and_manifest(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=5)
    _seed_selected_assets(temp_db, panel_count=5)

    response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    assert response.layout_template_id == "jp_2x2_v1"
    assert len(response.pages) == 2
    assert response.pages[0].page_no == 1
    assert response.export_manifest_path.endswith(".json")
    assert response.teaser_handoff_manifest_path.endswith(".json")

    export_manifest_path = settings.DATA_DIR / response.export_manifest_path
    assert export_manifest_path.is_file()
    assert (settings.DATA_DIR / response.teaser_handoff_manifest_path).is_file()
    assert (settings.DATA_DIR / response.pages[0].preview_path).is_file()
    assert (settings.DATA_DIR / response.pages[1].preview_path).is_file()

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """
            SELECT page_no, layout_template_id, export_state, preview_path
            FROM comic_page_assemblies
            WHERE episode_id = ?
            ORDER BY page_no ASC
            """,
            (episode_id,),
        ).fetchall()

    assert len(rows) == 2
    assert rows[0][1] == "jp_2x2_v1"
    assert rows[0][2] == "preview_ready"
    assert rows[0][3] == response.pages[0].preview_path


@pytest.mark.asyncio
async def test_assemble_episode_pages_decodes_panel_asset_manifest_fields(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=1)
    _insert_panel_asset_fixture(temp_db, "comic_panel_page_assembly_test_1")

    response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    manifest_path = settings.DATA_DIR / response.panel_asset_manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    panel_entry = next(
        entry
        for entry in manifest["panels"]
        if entry["panel_id"] == "comic_panel_page_assembly_test_1"
    )

    asset = panel_entry["assets"][0]
    assert isinstance(asset["prompt_snapshot"], dict)
    assert isinstance(asset["bubble_safe_zones"], list)
    assert isinstance(asset["crop_metadata"], dict)
    assert asset["prompt_snapshot"]["style"] == ["jp", "local"]

    teaser_manifest_path = settings.DATA_DIR / response.teaser_handoff_manifest_path
    teaser_manifest = json.loads(teaser_manifest_path.read_text(encoding="utf-8"))
    assert teaser_manifest["derivative_target"] == "teaser_animation"
    assert teaser_manifest["selected_panel_assets"][0]["storage_path"] == "images/comic_panel_page_assembly_test_1.png"


@pytest.mark.asyncio
async def test_assemble_episode_pages_groups_panels_by_page_target_hint(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(
        temp_db,
        panel_count=5,
        page_target_hints=[1, 1, 2, 2, 2],
    )
    _seed_selected_assets(temp_db, panel_count=5)

    response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    assert [page.ordered_panel_ids for page in response.pages] == [
        [
            "comic_panel_page_assembly_test_1",
            "comic_panel_page_assembly_test_2",
        ],
        [
            "comic_panel_page_assembly_test_3",
            "comic_panel_page_assembly_test_4",
            "comic_panel_page_assembly_test_5",
        ],
    ]


@pytest.mark.asyncio
async def test_assemble_episode_pages_requires_selected_asset_for_every_panel(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=2)
    _insert_panel_asset_fixture(temp_db, "comic_panel_page_assembly_test_1")

    with pytest.raises(
        ValueError,
        match="requires a selected render asset for every panel before page assembly",
    ):
        await assemble_episode_pages(
            episode_id=episode_id,
            layout_template_id="jp_2x2_v1",
        )


@pytest.mark.asyncio
async def test_export_episode_pages_persists_exported_state(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=2)
    _seed_selected_assets(temp_db, panel_count=2)

    response = await export_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    assert all(page.export_state == "exported" for page in response.pages)
    assert response.export_zip_path.endswith(".zip")
    assert response.teaser_handoff_manifest_path.endswith(".json")

    with sqlite3.connect(temp_db) as conn:
        states = conn.execute(
            """
            SELECT export_state
            FROM comic_page_assemblies
            WHERE episode_id = ?
            ORDER BY page_no ASC
            """,
            (episode_id,),
        ).fetchall()

    assert [row[0] for row in states] == ["exported"]

    export_zip_path = settings.DATA_DIR / response.export_zip_path
    with zipfile.ZipFile(export_zip_path) as archive:
        names = set(archive.namelist())

    assert "images/comic_panel_page_assembly_test_1.png" in names
    assert response.teaser_handoff_manifest_path in names


@pytest.mark.asyncio
async def test_export_episode_pages_writes_manuscript_profile_artifacts(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=2)
    _seed_selected_assets(temp_db, panel_count=2)

    response = await export_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
        manuscript_profile_id="jp_manga_rightbound_v1",
    )

    assert response.manuscript_profile["id"] == "jp_manga_rightbound_v1"
    assert response.manuscript_profile_manifest_path.endswith("_manuscript_profile.json")
    assert response.handoff_readme_path.endswith("_handoff_readme.md")
    assert response.production_checklist_path.endswith("_production_checklist.json")

    with sqlite3.connect(temp_db) as conn:
        rows = conn.execute(
            """
            SELECT manuscript_profile_id
            FROM comic_page_assemblies
            WHERE episode_id = ?
            ORDER BY page_no ASC
            """,
            (episode_id,),
        ).fetchall()

    assert [row[0] for row in rows] == [
        "jp_manga_rightbound_v1",
    ]

    export_zip_path = settings.DATA_DIR / response.export_zip_path
    with zipfile.ZipFile(export_zip_path) as archive:
        names = set(archive.namelist())

    assert response.manuscript_profile_manifest_path in names
    assert response.handoff_readme_path in names
    assert response.production_checklist_path in names


class _DummyDraw:
    def textbbox(self, xy, text, font):  # noqa: ANN001, ANN002
        del xy, font
        width = max(1, len(text)) * 8
        return (0, 0, width, 12)


def test_wrap_text_handles_no_space_japanese_text() -> None:
    lines = _wrap_text(
        _DummyDraw(),
        "あいうえおかきくけこ",
        ImageFont.load_default(),
        24,
    )

    assert len(lines) > 1


def test_wrap_text_handles_mixed_prefix_and_japanese_text() -> None:
    lines = _wrap_text(
        _DummyDraw(),
        "speech: あいうえおかきくけこ",
        ImageFont.load_default(),
        24,
    )

    assert len(lines) > 2
    assert lines[0] == "speech:"
    assert lines[1] != "あいうえおかきくけこ"
    assert lines[-1]


def test_load_font_prefers_cjk_font_path_before_arial(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    sentinel = object()

    def fake_truetype(font, size):  # noqa: ANN001, ANN201
        calls.append(str(font))
        if "Hiragino Sans GB.ttc" in str(font):
            return sentinel
        raise OSError("missing font")

    monkeypatch.setattr(
        "app.services.comic_page_assembly_service.ImageFont.truetype",
        fake_truetype,
    )

    font = _load_font(32)

    assert font is sentinel
    assert any("Hiragino Sans GB.ttc" in call for call in calls[:2])
