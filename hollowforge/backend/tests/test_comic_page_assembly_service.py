from __future__ import annotations

import json
import sqlite3
import zipfile

import pytest
from PIL import Image, ImageFont

from app.config import settings
from app.models import ComicEpisodeCreate
from app.services.comic_page_assembly_service import (
    ComicHandoffReadinessError,
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


def _insert_dialogue_fixture(
    temp_db,
    panel_id: str,
    *,
    dialogue_id: str | None = None,
    dialogue_type: str = "speech",
    text: str = "I know what this invitation means.",
    priority: int = 10,
    placement_hint: str = "upper left",
) -> None:
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
                dialogue_id or f"dialogue_{panel_id}_{priority}",
                panel_id,
                dialogue_type,
                "char_kaede_ren" if dialogue_type == "speech" else None,
                text,
                "measured",
                priority,
                "rounded" if dialogue_type == "speech" else None,
                placement_hint,
                _now(),
                _now(),
            ),
        )
        conn.commit()


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
    assert response.layered_manifest_path.endswith("/manifest.json")
    assert response.handoff_validation_path.endswith("/handoff_validation.json")
    assert response.teaser_handoff_manifest_path.endswith(".json")
    assert response.page_summaries[0].frame_layer_status == "complete"
    assert response.page_summaries[0].balloon_layer_status == "complete"
    assert response.page_summaries[0].text_draft_layer_status == "complete"
    assert response.handoff_validation.page_summaries[0].frame_layer_status == "complete"
    assert response.page_summaries[0].hard_block_count == 0
    assert response.page_summaries[0].soft_warning_count == 0
    assert response.handoff_validation.soft_warnings == []
    assert response.latest_export_summary is None

    export_manifest_path = settings.DATA_DIR / response.export_manifest_path
    assert export_manifest_path.is_file()
    assert (settings.DATA_DIR / response.layered_manifest_path).is_file()
    assert (settings.DATA_DIR / response.handoff_validation_path).is_file()
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
async def test_assemble_episode_pages_writes_canonical_layered_package_tree(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=2)
    _seed_selected_assets(temp_db, panel_count=2)

    response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    package_root = (settings.DATA_DIR / response.layered_manifest_path).parent
    page_dir = package_root / "pages" / "page_001"
    panel_dir = package_root / "panels" / "panel_comic_panel_page_assembly_test_1"

    assert (package_root / "manifest.json").is_file()
    assert (package_root / "handoff_validation.json").is_file()
    assert (package_root / "manuscript_profile.json").is_file()
    assert (package_root / "handoff_readme.md").is_file()
    assert (package_root / "reports" / "production_checklist.json").is_file()
    assert (page_dir / "page_manifest.json").is_file()
    assert (page_dir / "frame_layer.json").is_file()
    assert (page_dir / "balloon_layer.json").is_file()
    assert (page_dir / "text_draft_layer.json").is_file()
    assert (page_dir / "page_preview.png").is_file()
    assert (panel_dir / "panel_manifest.json").is_file()
    assert (panel_dir / "selected_render.png").is_file()

    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    page_manifest = json.loads((page_dir / "page_manifest.json").read_text(encoding="utf-8"))
    frame_layer = json.loads((page_dir / "frame_layer.json").read_text(encoding="utf-8"))
    balloon_layer = json.loads((page_dir / "balloon_layer.json").read_text(encoding="utf-8"))
    text_draft_layer = json.loads((page_dir / "text_draft_layer.json").read_text(encoding="utf-8"))
    panel_manifest = json.loads((panel_dir / "panel_manifest.json").read_text(encoding="utf-8"))

    assert {
        "package_version",
        "episode_id",
        "work_id",
        "series_id",
        "content_mode",
        "layout_template_id",
        "manuscript_profile",
        "page_count",
        "panel_count",
        "pages",
        "panels",
        "warnings",
        "source_lineage",
        "exported_at",
    } <= set(manifest)
    assert manifest["package_version"] == "1.5"
    assert manifest["page_count"] == 1
    assert manifest["panel_count"] == 2
    assert manifest["pages"][0]["status"] == "complete"
    assert manifest["pages"][0]["page_manifest_path"] == "pages/page_001/page_manifest.json"
    assert manifest["pages"][0]["layer_files"]["frame_layer"] == "pages/page_001/frame_layer.json"
    assert manifest["panels"][0]["selected_render_path"] == "panels/panel_comic_panel_page_assembly_test_1/selected_render.png"
    assert manifest["panels"][0]["selected_render_asset_id"] == "comic_panel_render_asset_fixture_comic_panel_page_assembly_test_1"
    assert manifest["panels"][0]["selected_render_generation_id"] == "gen-ready-1"
    assert manifest["panels"][0]["crop_notes"] == {
        "crop_metadata": {"crop_mode": "fit", "anchor": "center"},
        "bubble_safe_zones": [{"x": 12, "y": 24, "w": 240, "h": 180}],
    }
    assert isinstance(manifest["warnings"], list)
    assert all({"code", "page_id", "page_no", "layer"} <= set(warning) for warning in manifest["warnings"])
    assert manifest["source_lineage"]["page_previews"][0]["path"] == "pages/page_001/page_preview.png"
    assert manifest["source_lineage"]["panel_manifests"][0]["path"] == "panels/panel_comic_panel_page_assembly_test_1/panel_manifest.json"

    assert {
        "page_id",
        "page_no",
        "canvas_size",
        "reading_direction",
        "trim_box",
        "bleed_box",
        "safe_box",
        "panel_order",
        "layer_files",
        "status",
    } <= set(page_manifest)
    assert page_manifest["status"] == "complete"
    assert isinstance(page_manifest["status"], str)
    assert page_manifest["canvas_size"] == {"width": 1600, "height": 2400}
    assert page_manifest["reading_direction"] == "right_to_left"
    assert page_manifest["trim_box"] == {"x": 0, "y": 0, "width": 1600, "height": 2400}
    assert page_manifest["bleed_box"] == {"x": 0, "y": 0, "width": 1600, "height": 2400}
    assert page_manifest["safe_box"] == {"x": 72, "y": 72, "width": 1456, "height": 2256}
    assert page_manifest["panel_order"] == [
        "comic_panel_page_assembly_test_1",
        "comic_panel_page_assembly_test_2",
    ]
    assert page_manifest["layer_files"] == {
        "frame_layer": "pages/page_001/frame_layer.json",
        "balloon_layer": "pages/page_001/balloon_layer.json",
        "text_draft_layer": "pages/page_001/text_draft_layer.json",
    }

    assert {
        "episode_id",
        "page_id",
        "page_no",
        "layer",
        "status",
        "items",
    } <= set(frame_layer)
    assert frame_layer["layer"] == "frame"
    assert frame_layer["status"] == "complete"
    assert isinstance(frame_layer["items"], list)
    assert {
        "panel_id",
        "scene_no",
        "panel_no",
        "reading_order",
        "frame_rect",
        "frame_shape_hint",
        "source_render_asset_id",
        "source_generation_id",
    } <= set(frame_layer["items"][0])
    assert frame_layer["items"][0]["source_render_asset_id"] == "comic_panel_render_asset_fixture_comic_panel_page_assembly_test_1"
    assert frame_layer["items"][0]["source_generation_id"] == "gen-ready-1"

    assert balloon_layer["layer"] == "balloon"
    assert balloon_layer["status"] == "complete"
    assert isinstance(balloon_layer["items"], list)
    assert balloon_layer["items"] == []

    assert text_draft_layer["layer"] == "text_draft"
    assert text_draft_layer["status"] == "complete"
    assert isinstance(text_draft_layer["items"], list)
    assert text_draft_layer["items"] == []

    assert {
        "panel_id",
        "page_no",
        "scene_no",
        "panel_no",
        "selected_render_asset_id",
        "selected_render_generation_id",
        "selected_render_path",
        "crop_notes",
    } <= set(panel_manifest)
    assert panel_manifest["selected_render_path"] == "panels/panel_comic_panel_page_assembly_test_1/selected_render.png"
    assert panel_manifest["selected_render_asset_id"] == "comic_panel_render_asset_fixture_comic_panel_page_assembly_test_1"
    assert panel_manifest["selected_render_generation_id"] == "gen-ready-1"
    assert panel_manifest["lineage"]["page_manifest_path"] == "pages/page_001/page_manifest.json"
    assert panel_manifest["crop_notes"] == {
        "crop_metadata": {"crop_mode": "fit", "anchor": "center"},
        "bubble_safe_zones": [{"x": 12, "y": 24, "w": 240, "h": 180}],
    }


@pytest.mark.asyncio
async def test_assemble_episode_pages_blocks_duplicate_reading_order_on_page(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=2)
    _seed_selected_assets(temp_db, panel_count=2)

    with sqlite3.connect(temp_db) as conn:
        conn.execute(
            """
            UPDATE comic_scene_panels
            SET reading_order = 1
            WHERE id = ?
            """,
            ("comic_panel_page_assembly_test_2",),
        )
        conn.commit()

    response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    assert response.page_summaries[0].frame_layer_status == "blocked"
    assert response.page_summaries[0].hard_block_count == 1
    assert response.handoff_validation.hard_blocks[0].code == "reading_order_invalid"
    assert response.handoff_validation.hard_blocks[0].layer == "frame"


@pytest.mark.asyncio
async def test_assemble_episode_pages_generates_dialogue_anchor_mappings_from_placement_hints(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=1)
    _seed_selected_assets(temp_db, panel_count=1)
    _insert_dialogue_fixture(temp_db, "comic_panel_page_assembly_test_1")
    _insert_dialogue_fixture(
        temp_db,
        "comic_panel_page_assembly_test_1",
        dialogue_id="dialogue_caption_top_edge",
        dialogue_type="caption",
        priority=20,
        placement_hint="top edge",
    )
    _insert_dialogue_fixture(
        temp_db,
        "comic_panel_page_assembly_test_1",
        dialogue_id="dialogue_sfx_near_hand",
        dialogue_type="sfx",
        text="tap",
        priority=30,
        placement_hint="near hand",
    )

    response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    assert response.page_summaries[0].art_layer_status == "complete"
    assert response.page_summaries[0].frame_layer_status == "complete"
    assert response.page_summaries[0].balloon_layer_status == "complete"
    assert response.page_summaries[0].text_draft_layer_status == "complete"
    assert response.page_summaries[0].hard_block_count == 0
    assert response.handoff_validation.hard_blocks == []

    layered_package_root = (settings.DATA_DIR / response.layered_manifest_path).parent
    balloon_layer = json.loads(
        (layered_package_root / "pages" / "page_001" / "balloon_layer.json").read_text(
            encoding="utf-8"
        )
    )
    text_draft_layer = json.loads(
        (layered_package_root / "pages" / "page_001" / "text_draft_layer.json").read_text(
            encoding="utf-8"
        )
    )

    assert balloon_layer["status"] == "complete"
    assert text_draft_layer["status"] == "complete"
    assert balloon_layer["items"][0]["dialogues"][0]["anchor_mapping"]["placement_hint"] == "upper left"
    assert balloon_layer["items"][0]["dialogues"][1]["anchor_mapping"]["placement_hint"] == "top edge"
    assert balloon_layer["items"][0]["dialogues"][2]["anchor_mapping"]["placement_hint"] == "near hand"
    assert text_draft_layer["items"][0]["dialogues"][0]["anchor_mapping"]["layer"] == "text_draft"


@pytest.mark.asyncio
async def test_assemble_episode_pages_blocks_dialogue_layers_without_anchor_mapping(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=1)
    _seed_selected_assets(temp_db, panel_count=1)
    _insert_dialogue_fixture(
        temp_db,
        "comic_panel_page_assembly_test_1",
        placement_hint="off-panel mystery zone",
    )

    response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    assert response.page_summaries[0].art_layer_status == "complete"
    assert response.page_summaries[0].frame_layer_status == "complete"
    assert response.page_summaries[0].balloon_layer_status == "blocked"
    assert response.page_summaries[0].text_draft_layer_status == "blocked"
    assert response.page_summaries[0].hard_block_count == 2
    assert {(issue.code, issue.layer) for issue in response.handoff_validation.hard_blocks} == {
        ("missing_anchor_mapping", "balloon"),
        ("missing_anchor_mapping", "text_draft"),
    }


@pytest.mark.asyncio
async def test_assemble_episode_pages_clears_stale_package_root_before_regeneration(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=2)
    _seed_selected_assets(temp_db, panel_count=2)

    first_response = await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )
    package_root = (settings.DATA_DIR / first_response.layered_manifest_path).parent
    stale_file = package_root / "pages" / "page_999" / "orphan.json"
    stale_file.parent.mkdir(parents=True, exist_ok=True)
    stale_file.write_text("stale", encoding="utf-8")

    await assemble_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    assert not stale_file.exists()


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
    assert response.layered_manifest_path.endswith("/manifest.json")
    assert response.handoff_validation_path.endswith("/handoff_validation.json")
    assert response.latest_export_summary is not None
    assert response.latest_export_summary.page_count == len(response.pages)
    assert response.latest_export_summary.layered_manifest_path == response.layered_manifest_path
    assert response.latest_export_summary.soft_warning_count == len(
        response.handoff_validation.soft_warnings
    )
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
        root_manifest = json.loads(archive.read("manifest.json").decode("utf-8"))

    assert "images/comic_panel_page_assembly_test_1.png" in names
    assert response.teaser_handoff_manifest_path in names
    assert response.layered_manifest_path in names
    assert response.handoff_validation_path in names
    assert "manifest.json" in names
    assert "handoff_validation.json" in names
    assert "handoff_readme.md" in names
    assert "manuscript_profile.json" in names
    assert "reports/production_checklist.json" in names
    assert "pages/page_001/page_preview.png" in names
    assert "pages/page_001/page_manifest.json" in names
    assert "pages/page_001/frame_layer.json" in names
    assert "pages/page_001/balloon_layer.json" in names
    assert "pages/page_001/text_draft_layer.json" in names
    assert "panels/panel_comic_panel_page_assembly_test_1/selected_render.png" in names
    assert "panels/panel_comic_panel_page_assembly_test_1/panel_manifest.json" in names
    assert root_manifest["package_version"] == "1.5"
    assert root_manifest["pages"][0]["layer_files"]["frame_layer"] == "pages/page_001/frame_layer.json"
    assert root_manifest["panels"][0]["selected_render_path"] == "panels/panel_comic_panel_page_assembly_test_1/selected_render.png"


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
    assert (settings.DATA_DIR / response.manuscript_profile_manifest_path).is_file()
    assert (settings.DATA_DIR / response.handoff_readme_path).is_file()
    assert (settings.DATA_DIR / response.production_checklist_path).is_file()

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
    assert "manifest.json" in names
    assert "handoff_validation.json" in names
    assert "handoff_readme.md" in names
    assert "manuscript_profile.json" in names
    assert "reports/production_checklist.json" in names
    assert "pages/page_001/page_preview.png" in names
    assert "pages/page_001/page_manifest.json" in names
    assert "pages/page_001/frame_layer.json" in names
    assert "pages/page_001/balloon_layer.json" in names
    assert "pages/page_001/text_draft_layer.json" in names
    assert "panels/panel_comic_panel_page_assembly_test_1/selected_render.png" in names
    assert "panels/panel_comic_panel_page_assembly_test_1/panel_manifest.json" in names


@pytest.mark.asyncio
async def test_export_episode_pages_supports_dialogue_rows_with_anchor_mapping(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=1)
    _seed_selected_assets(temp_db, panel_count=1)
    _insert_dialogue_fixture(temp_db, "comic_panel_page_assembly_test_1")
    response = await export_episode_pages(
        episode_id=episode_id,
        layout_template_id="jp_2x2_v1",
    )

    assert response.export_zip_path.endswith(".zip")
    assert response.handoff_validation.hard_blocks == []


@pytest.mark.asyncio
async def test_export_episode_pages_rejects_dialogue_rows_without_anchor_mapping(
    temp_db,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=1)
    _seed_selected_assets(temp_db, panel_count=1)
    _insert_dialogue_fixture(
        temp_db,
        "comic_panel_page_assembly_test_1",
        placement_hint="off-panel mystery zone",
    )

    with pytest.raises(ComicHandoffReadinessError, match="hard blocks"):
        await export_episode_pages(
            episode_id=episode_id,
            layout_template_id="jp_2x2_v1",
        )


@pytest.mark.asyncio
async def test_export_episode_pages_rejects_hard_blocks_before_zip_creation(
    temp_db,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    episode_id = await _seed_episode_with_panels(temp_db, panel_count=1)
    _seed_selected_assets(temp_db, panel_count=1)

    hard_block = {
        "code": "layer_blocked",
        "page_id": "page_001",
        "page_no": 1,
        "layer": "art_layer_status",
    }
    validation = {
        "episode_id": episode_id,
        "hard_blocks": [hard_block],
        "soft_warnings": [],
        "page_summaries": [],
        "generated_at": _now(),
    }
    fake_page_response = {
        "episode_id": episode_id,
        "layout_template_id": "jp_2x2_v1",
        "manuscript_profile": {},
        "pages": [],
        "export_manifest_path": "comics/manifests/fake_pages.json",
        "layered_manifest_path": "comics/manifests/fake_layered/manifest.json",
        "handoff_validation_path": "comics/manifests/fake_layered/handoff_validation.json",
        "handoff_validation": validation,
        "page_summaries": [],
        "latest_export_summary": None,
        "dialogue_json_path": "comics/manifests/fake_dialogues.json",
        "panel_asset_manifest_path": "comics/manifests/fake_panel_assets.json",
        "page_assembly_manifest_path": "comics/manifests/fake_pages_assembly.json",
        "teaser_handoff_manifest_path": "comics/manifests/fake_teaser.json",
        "manuscript_profile_manifest_path": "comics/manifests/fake_manuscript_profile.json",
        "handoff_readme_path": "comics/manifests/fake_handoff_readme.md",
        "production_checklist_path": "comics/manifests/fake_production_checklist.json",
    }

    async def _fake_assemble_episode_pages(**_: object):  # type: ignore[no-untyped-def]
        from app.models import ComicPageAssemblyBatchResponse, ComicHandoffValidationResponse

        return ComicPageAssemblyBatchResponse.model_validate(
            {
                **fake_page_response,
                "handoff_validation": validation,
            }
        )

    def _fail_if_zip_created(**_: object) -> None:
        raise AssertionError("ZIP creation should not run when hard blocks exist")

    monkeypatch.setattr(
        "app.services.comic_page_assembly_service.assemble_episode_pages",
        _fake_assemble_episode_pages,
    )
    monkeypatch.setattr(
        "app.services.comic_page_assembly_service._zip_manifest_artifacts",
        _fail_if_zip_created,
    )

    with pytest.raises(ComicHandoffReadinessError, match="hard blocks"):
        await export_episode_pages(
            episode_id=episode_id,
            layout_template_id="jp_2x2_v1",
        )


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
