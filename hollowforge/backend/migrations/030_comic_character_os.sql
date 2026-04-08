CREATE TABLE IF NOT EXISTS comic_episodes (
    id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    character_version_id TEXT NOT NULL,
    title TEXT NOT NULL,
    synopsis TEXT NOT NULL,
    source_story_plan_json TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    continuity_summary TEXT,
    canon_delta TEXT,
    target_output TEXT NOT NULL DEFAULT 'oneshot_manga',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
    FOREIGN KEY (character_version_id) REFERENCES character_versions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comic_episodes_character_status
    ON comic_episodes(character_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_comic_episodes_character_version
    ON comic_episodes(character_version_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS comic_episode_scenes (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    scene_no INTEGER NOT NULL,
    premise TEXT NOT NULL,
    location_label TEXT,
    tension TEXT,
    reveal TEXT,
    continuity_notes TEXT,
    involved_character_ids TEXT NOT NULL DEFAULT '[]',
    target_panel_count INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES comic_episodes(id) ON DELETE CASCADE,
    UNIQUE (episode_id, scene_no)
);

CREATE INDEX IF NOT EXISTS idx_comic_episode_scenes_episode_no
    ON comic_episode_scenes(episode_id, scene_no);

CREATE TABLE IF NOT EXISTS comic_scene_panels (
    id TEXT PRIMARY KEY,
    episode_scene_id TEXT NOT NULL,
    panel_no INTEGER NOT NULL,
    panel_type TEXT NOT NULL DEFAULT 'beat',
    framing TEXT,
    camera_intent TEXT,
    action_intent TEXT,
    expression_intent TEXT,
    dialogue_intent TEXT,
    continuity_lock TEXT,
    page_target_hint INTEGER,
    reading_order INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (episode_scene_id) REFERENCES comic_episode_scenes(id) ON DELETE CASCADE,
    UNIQUE (episode_scene_id, panel_no)
);

CREATE INDEX IF NOT EXISTS idx_comic_scene_panels_scene_reading
    ON comic_scene_panels(episode_scene_id, reading_order, page_target_hint);

CREATE TABLE IF NOT EXISTS comic_panel_dialogues (
    id TEXT PRIMARY KEY,
    scene_panel_id TEXT NOT NULL,
    type TEXT NOT NULL,
    speaker_character_id TEXT,
    text TEXT NOT NULL,
    tone TEXT,
    priority INTEGER NOT NULL DEFAULT 100,
    balloon_style_hint TEXT,
    placement_hint TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (scene_panel_id) REFERENCES comic_scene_panels(id) ON DELETE CASCADE,
    FOREIGN KEY (speaker_character_id) REFERENCES characters(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_comic_panel_dialogues_panel_priority
    ON comic_panel_dialogues(scene_panel_id, priority, id);

CREATE TABLE IF NOT EXISTS comic_panel_render_assets (
    id TEXT PRIMARY KEY,
    scene_panel_id TEXT NOT NULL,
    generation_id TEXT,
    asset_role TEXT NOT NULL DEFAULT 'candidate',
    storage_path TEXT,
    prompt_snapshot TEXT,
    quality_score REAL,
    bubble_safe_zones TEXT NOT NULL DEFAULT '[]',
    crop_metadata TEXT,
    render_notes TEXT,
    is_selected INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (scene_panel_id) REFERENCES comic_scene_panels(id) ON DELETE CASCADE,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_comic_panel_render_assets_panel_selection
    ON comic_panel_render_assets(scene_panel_id, is_selected, quality_score DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS comic_page_assemblies (
    id TEXT PRIMARY KEY,
    episode_id TEXT NOT NULL,
    page_no INTEGER NOT NULL,
    layout_template_id TEXT,
    ordered_panel_ids TEXT NOT NULL DEFAULT '[]',
    export_state TEXT NOT NULL DEFAULT 'draft',
    preview_path TEXT,
    master_path TEXT,
    export_manifest TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES comic_episodes(id) ON DELETE CASCADE,
    UNIQUE (episode_id, page_no)
);

CREATE INDEX IF NOT EXISTS idx_comic_page_assemblies_episode_page
    ON comic_page_assemblies(episode_id, page_no, updated_at DESC);
