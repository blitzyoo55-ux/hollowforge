-- Quality gate columns on generations table
ALTER TABLE generations ADD COLUMN quality_score INTEGER DEFAULT NULL;
ALTER TABLE generations ADD COLUMN publish_approved INTEGER DEFAULT 0; -- 0=pending, 1=approved, 2=rejected
ALTER TABLE generations ADD COLUMN curated_at TEXT DEFAULT NULL;
ALTER TABLE generations ADD COLUMN direction_pinned INTEGER DEFAULT 0; -- pinned to direction board

-- Direction board references table
CREATE TABLE IF NOT EXISTS direction_references (
    id TEXT PRIMARY KEY,
    external_url TEXT,          -- Rule34 or other external image URL
    generation_id TEXT,         -- or link to internal generation
    title TEXT,
    notes TEXT,
    tags TEXT,                  -- JSON array of tags
    source TEXT DEFAULT 'external', -- 'external' or 'internal'
    created_at TEXT DEFAULT (datetime('now'))
);
