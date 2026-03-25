CREATE TABLE IF NOT EXISTS caption_variants (
    id TEXT PRIMARY KEY,
    generation_id TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'social_short',
    platform TEXT NOT NULL DEFAULT 'twitter',
    provider TEXT NOT NULL DEFAULT 'openrouter',
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL DEFAULT 'lab451_social_v1',
    tone TEXT NOT NULL DEFAULT 'teaser',
    story TEXT NOT NULL,
    hashtags TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_caption_variants_generation
    ON caption_variants(generation_id, approved, updated_at DESC);

CREATE TABLE IF NOT EXISTS publish_jobs (
    id TEXT PRIMARY KEY,
    generation_id TEXT NOT NULL,
    caption_variant_id TEXT,
    platform TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    scheduled_at TEXT,
    published_at TEXT,
    external_post_id TEXT,
    external_post_url TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    FOREIGN KEY (caption_variant_id) REFERENCES caption_variants(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_publish_jobs_generation
    ON publish_jobs(generation_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS engagement_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    publish_job_id TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    likes INTEGER NOT NULL DEFAULT 0,
    replies INTEGER NOT NULL DEFAULT 0,
    reposts INTEGER NOT NULL DEFAULT 0,
    bookmarks INTEGER NOT NULL DEFAULT 0,
    impressions INTEGER NOT NULL DEFAULT 0,
    detail_json TEXT,
    FOREIGN KEY (publish_job_id) REFERENCES publish_jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_engagement_snapshots_job
    ON engagement_snapshots(publish_job_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS animation_candidates (
    id TEXT PRIMARY KEY,
    generation_id TEXT NOT NULL,
    publish_job_id TEXT,
    trigger_source TEXT NOT NULL DEFAULT 'engagement',
    trigger_score REAL NOT NULL DEFAULT 0,
    target_tool TEXT NOT NULL DEFAULT 'dreamactor',
    status TEXT NOT NULL DEFAULT 'suggested',
    notes TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE,
    FOREIGN KEY (publish_job_id) REFERENCES publish_jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_animation_candidates_generation
    ON animation_candidates(generation_id, status, updated_at DESC);
