CREATE TABLE IF NOT EXISTS comic_verification_runs (
    id TEXT PRIMARY KEY,
    run_mode TEXT NOT NULL CHECK (
        run_mode IN ('preflight', 'suite', 'full_only', 'remote_only')
    ),
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
    overall_success INTEGER NOT NULL CHECK (overall_success IN (0, 1)),
    failure_stage TEXT,
    error_summary TEXT,
    base_url TEXT NOT NULL,
    total_duration_sec REAL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    stage_status_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
