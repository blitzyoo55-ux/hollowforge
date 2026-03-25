CREATE TABLE IF NOT EXISTS prompt_factory_checkpoint_preferences (
    checkpoint TEXT PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 'default',
    priority_boost INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
