CREATE TABLE IF NOT EXISTS seedance_jobs (
    id TEXT PRIMARY KEY,
    task_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    prompt TEXT,
    duration_sec INTEGER DEFAULT 8,
    files_meta TEXT,
    output_path TEXT,
    error_msg TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);
