CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    preset_id TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 4,
    cron_hour INTEGER NOT NULL DEFAULT 2,
    cron_minute INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_run_at TEXT,
    last_run_status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
