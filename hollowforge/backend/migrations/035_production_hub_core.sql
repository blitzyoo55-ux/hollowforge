CREATE TABLE IF NOT EXISTS works (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    format_family TEXT NOT NULL,
    default_content_mode TEXT NOT NULL CHECK (
        default_content_mode IN ('all_ages', 'adult_nsfw')
    ),
    status TEXT NOT NULL DEFAULT 'draft',
    canon_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS series (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    delivery_mode TEXT NOT NULL,
    audience_mode TEXT NOT NULL,
    visual_identity_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS production_episodes (
    id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL REFERENCES works(id) ON DELETE CASCADE,
    series_id TEXT REFERENCES series(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    synopsis TEXT NOT NULL,
    content_mode TEXT NOT NULL CHECK (content_mode IN ('all_ages', 'adult_nsfw')),
    target_outputs TEXT NOT NULL DEFAULT '[]',
    continuity_summary TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

ALTER TABLE comic_episodes
    ADD COLUMN content_mode TEXT NOT NULL DEFAULT 'all_ages';

ALTER TABLE comic_episodes
    ADD COLUMN work_id TEXT;

ALTER TABLE comic_episodes
    ADD COLUMN series_id TEXT;

ALTER TABLE comic_episodes
    ADD COLUMN production_episode_id TEXT;

ALTER TABLE sequence_blueprints
    ADD COLUMN work_id TEXT;

ALTER TABLE sequence_blueprints
    ADD COLUMN series_id TEXT;

ALTER TABLE sequence_blueprints
    ADD COLUMN production_episode_id TEXT;
