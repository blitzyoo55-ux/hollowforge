CREATE TABLE IF NOT EXISTS animation_shots (
    id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL DEFAULT 'comic_selected_render'
        CHECK (source_kind = 'comic_selected_render'),
    episode_id TEXT NOT NULL REFERENCES comic_episodes(id) ON DELETE CASCADE,
    scene_panel_id TEXT NOT NULL REFERENCES comic_scene_panels(id) ON DELETE CASCADE,
    selected_render_asset_id TEXT NOT NULL REFERENCES comic_panel_render_assets(id) ON DELETE CASCADE,
    generation_id TEXT REFERENCES generations(id) ON DELETE SET NULL,
    is_current INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_animation_shots_selected_render_asset_id
    ON animation_shots(selected_render_asset_id);

CREATE TRIGGER IF NOT EXISTS trg_animation_shots_validate_episode_scene_panel_insert
BEFORE INSERT ON animation_shots
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM comic_scene_panels AS panel
    JOIN comic_episode_scenes AS scene ON scene.id = panel.episode_scene_id
    WHERE panel.id = NEW.scene_panel_id
      AND scene.episode_id = NEW.episode_id
)
BEGIN
    SELECT RAISE(ABORT, 'animation_shots.scene_panel_id must belong to episode_id');
END;

CREATE TRIGGER IF NOT EXISTS trg_animation_shots_validate_episode_scene_panel_update
BEFORE UPDATE OF episode_id, scene_panel_id ON animation_shots
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM comic_scene_panels AS panel
    JOIN comic_episode_scenes AS scene ON scene.id = panel.episode_scene_id
    WHERE panel.id = NEW.scene_panel_id
      AND scene.episode_id = NEW.episode_id
)
BEGIN
    SELECT RAISE(ABORT, 'animation_shots.scene_panel_id must belong to episode_id');
END;

CREATE TRIGGER IF NOT EXISTS trg_animation_shots_validate_scene_panel_asset_insert
BEFORE INSERT ON animation_shots
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM comic_panel_render_assets AS asset
    WHERE asset.id = NEW.selected_render_asset_id
      AND asset.scene_panel_id = NEW.scene_panel_id
)
BEGIN
    SELECT RAISE(ABORT, 'animation_shots.selected_render_asset_id must belong to scene_panel_id');
END;

CREATE TRIGGER IF NOT EXISTS trg_animation_shots_validate_scene_panel_asset_update
BEFORE UPDATE OF scene_panel_id, selected_render_asset_id ON animation_shots
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM comic_panel_render_assets AS asset
    WHERE asset.id = NEW.selected_render_asset_id
      AND asset.scene_panel_id = NEW.scene_panel_id
)
BEGIN
    SELECT RAISE(ABORT, 'animation_shots.selected_render_asset_id must belong to scene_panel_id');
END;

CREATE TRIGGER IF NOT EXISTS trg_animation_shots_validate_selected_asset_insert
BEFORE INSERT ON animation_shots
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM comic_panel_render_assets AS asset
    WHERE asset.id = NEW.selected_render_asset_id
      AND asset.asset_role = 'selected'
      AND asset.is_selected = 1
)
BEGIN
    SELECT RAISE(ABORT, 'animation_shots.selected_render_asset_id must point to selected render asset');
END;

CREATE TRIGGER IF NOT EXISTS trg_animation_shots_validate_selected_asset_update
BEFORE UPDATE OF selected_render_asset_id ON animation_shots
FOR EACH ROW
WHEN NOT EXISTS (
    SELECT 1
    FROM comic_panel_render_assets AS asset
    WHERE asset.id = NEW.selected_render_asset_id
      AND asset.asset_role = 'selected'
      AND asset.is_selected = 1
)
BEGIN
    SELECT RAISE(ABORT, 'animation_shots.selected_render_asset_id must point to selected render asset');
END;

CREATE TRIGGER IF NOT EXISTS trg_animation_shots_validate_generation_match_insert
BEFORE INSERT ON animation_shots
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM comic_panel_render_assets AS asset
    WHERE asset.id = NEW.selected_render_asset_id
      AND asset.generation_id IS NOT NEW.generation_id
)
BEGIN
    SELECT RAISE(ABORT, 'animation_shots.generation_id must match selected_render_asset_id.generation_id');
END;

CREATE TRIGGER IF NOT EXISTS trg_animation_shots_validate_generation_match_update
BEFORE UPDATE OF generation_id, selected_render_asset_id ON animation_shots
FOR EACH ROW
WHEN (
    NEW.generation_id IS NOT NULL
    AND EXISTS (
        SELECT 1
        FROM comic_panel_render_assets AS asset
        WHERE asset.id = NEW.selected_render_asset_id
          AND asset.generation_id IS NOT NEW.generation_id
    )
) OR (
    NEW.generation_id IS NULL
    AND OLD.generation_id IS NOT NULL
    AND EXISTS (
        SELECT 1
        FROM generations
        WHERE id = OLD.generation_id
    )
)
BEGIN
    SELECT RAISE(ABORT, 'animation_shots.generation_id must match selected_render_asset_id.generation_id');
END;

CREATE TRIGGER IF NOT EXISTS trg_comic_scene_panels_block_animation_shot_reparent
BEFORE UPDATE OF episode_scene_id ON comic_scene_panels
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM animation_shots AS shot
    JOIN comic_episode_scenes AS new_scene ON new_scene.id = NEW.episode_scene_id
    WHERE shot.scene_panel_id = OLD.id
      AND shot.episode_id != new_scene.episode_id
)
BEGIN
    SELECT RAISE(ABORT, 'comic_scene_panels.episode_scene_id would invalidate animation_shots lineage');
END;

CREATE TRIGGER IF NOT EXISTS trg_comic_episode_scenes_block_animation_shot_reparent
BEFORE UPDATE OF episode_id ON comic_episode_scenes
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM comic_scene_panels AS panel
    JOIN animation_shots AS shot ON shot.scene_panel_id = panel.id
    WHERE panel.episode_scene_id = OLD.id
      AND shot.episode_id != NEW.episode_id
)
BEGIN
    SELECT RAISE(ABORT, 'comic_episode_scenes.episode_id would invalidate animation_shots lineage');
END;

CREATE TRIGGER IF NOT EXISTS trg_comic_panel_render_assets_block_animation_shot_reparent
BEFORE UPDATE OF scene_panel_id ON comic_panel_render_assets
FOR EACH ROW
WHEN EXISTS (
    SELECT 1
    FROM animation_shots AS shot
    WHERE shot.selected_render_asset_id = OLD.id
      AND shot.scene_panel_id != NEW.scene_panel_id
)
BEGIN
    SELECT RAISE(ABORT, 'comic_panel_render_assets.scene_panel_id would invalidate animation_shots lineage');
END;

CREATE TRIGGER IF NOT EXISTS trg_comic_panel_render_assets_block_animation_shot_generation_drift
BEFORE UPDATE OF generation_id ON comic_panel_render_assets
FOR EACH ROW
WHEN (
    NEW.generation_id IS NOT NULL
    AND EXISTS (
        SELECT 1
        FROM animation_shots AS shot
        WHERE shot.selected_render_asset_id = OLD.id
          AND shot.generation_id IS NOT NEW.generation_id
    )
) OR (
    NEW.generation_id IS NULL
    AND OLD.generation_id IS NOT NULL
    AND EXISTS (
        SELECT 1
        FROM generations
        WHERE id = OLD.generation_id
    )
)
BEGIN
    SELECT RAISE(ABORT, 'comic_panel_render_assets.generation_id would invalidate animation_shots lineage');
END;

CREATE TABLE IF NOT EXISTS animation_shot_variants (
    id TEXT PRIMARY KEY,
    animation_shot_id TEXT NOT NULL REFERENCES animation_shots(id) ON DELETE CASCADE,
    animation_job_id TEXT NOT NULL REFERENCES animation_jobs(id) ON DELETE CASCADE,
    preset_id TEXT NOT NULL,
    launch_reason TEXT NOT NULL,
    status TEXT NOT NULL,
    output_path TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_animation_shot_variants_animation_job_id
    ON animation_shot_variants(animation_job_id);

CREATE INDEX IF NOT EXISTS idx_animation_shot_variants_animation_shot_id_created_at
    ON animation_shot_variants(animation_shot_id, created_at DESC);
