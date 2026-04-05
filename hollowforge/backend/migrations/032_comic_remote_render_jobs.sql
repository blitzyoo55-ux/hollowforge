CREATE TABLE IF NOT EXISTS comic_render_jobs (
    id TEXT PRIMARY KEY,
    scene_panel_id TEXT NOT NULL REFERENCES comic_scene_panels(id) ON DELETE CASCADE,
    render_asset_id TEXT NOT NULL REFERENCES comic_panel_render_assets(id) ON DELETE CASCADE,
    generation_id TEXT NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    request_index INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    target_tool TEXT NOT NULL,
    executor_mode TEXT NOT NULL,
    executor_key TEXT NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT,
    external_job_id TEXT,
    external_job_url TEXT,
    output_path TEXT,
    error_message TEXT,
    submitted_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_comic_render_jobs_render_asset_id
    ON comic_render_jobs(render_asset_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_comic_render_jobs_generation_id
    ON comic_render_jobs(generation_id);

CREATE INDEX IF NOT EXISTS idx_comic_render_jobs_scene_panel_id_updated_at
    ON comic_render_jobs(scene_panel_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_comic_render_jobs_status_updated_at
    ON comic_render_jobs(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_comic_render_jobs_external_job_id
    ON comic_render_jobs(external_job_id);
