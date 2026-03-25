CREATE TABLE IF NOT EXISTS animation_jobs (
    id TEXT PRIMARY KEY,
    candidate_id TEXT,
    generation_id TEXT NOT NULL,
    publish_job_id TEXT,
    target_tool TEXT NOT NULL,
    executor_mode TEXT NOT NULL DEFAULT 'remote_worker',
    executor_key TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'queued',
    request_json TEXT,
    external_job_id TEXT,
    external_job_url TEXT,
    output_path TEXT,
    error_message TEXT,
    submitted_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(candidate_id) REFERENCES animation_candidates(id) ON DELETE SET NULL,
    FOREIGN KEY(generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    FOREIGN KEY(publish_job_id) REFERENCES publish_jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_animation_jobs_status_updated
    ON animation_jobs(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_animation_jobs_candidate
    ON animation_jobs(candidate_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_animation_jobs_generation
    ON animation_jobs(generation_id, updated_at DESC);
