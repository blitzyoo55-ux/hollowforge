CREATE TABLE IF NOT EXISTS benchmark_jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prompt TEXT NOT NULL,
    negative_prompt TEXT,
    loras TEXT NOT NULL DEFAULT '[]',
    steps INTEGER NOT NULL DEFAULT 28,
    cfg REAL NOT NULL DEFAULT 7.0,
    width INTEGER NOT NULL DEFAULT 832,
    height INTEGER NOT NULL DEFAULT 1216,
    sampler TEXT NOT NULL DEFAULT 'euler',
    scheduler TEXT NOT NULL DEFAULT 'normal',
    seed INTEGER,
    checkpoints TEXT NOT NULL DEFAULT '[]',
    generation_ids TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','completed','failed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    completed_at TEXT
);
