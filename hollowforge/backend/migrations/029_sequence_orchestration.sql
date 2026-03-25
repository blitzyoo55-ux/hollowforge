CREATE TABLE IF NOT EXISTS sequence_blueprints (
    id TEXT PRIMARY KEY,
    content_mode TEXT NOT NULL,
    policy_profile_id TEXT NOT NULL,
    character_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    beat_grammar_id TEXT NOT NULL,
    target_duration_sec INTEGER NOT NULL,
    shot_count INTEGER NOT NULL,
    tone TEXT,
    executor_policy TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (id, content_mode, policy_profile_id)
);

CREATE TABLE IF NOT EXISTS sequence_runs (
    id TEXT PRIMARY KEY,
    sequence_blueprint_id TEXT NOT NULL,
    content_mode TEXT NOT NULL,
    policy_profile_id TEXT NOT NULL,
    prompt_provider_profile_id TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    selected_rough_cut_id TEXT,
    total_score REAL,
    error_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (
        sequence_blueprint_id,
        content_mode,
        policy_profile_id
    ) REFERENCES sequence_blueprints(id, content_mode, policy_profile_id) ON DELETE CASCADE,
    FOREIGN KEY (
        id,
        selected_rough_cut_id,
        content_mode,
        policy_profile_id
    ) REFERENCES rough_cuts(sequence_run_id, id, content_mode, policy_profile_id),
    UNIQUE (id, content_mode, policy_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_sequence_runs_blueprint
    ON sequence_runs(sequence_blueprint_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_sequence_runs_status
    ON sequence_runs(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS sequence_shots (
    id TEXT PRIMARY KEY,
    sequence_run_id TEXT NOT NULL,
    content_mode TEXT NOT NULL,
    policy_profile_id TEXT NOT NULL,
    shot_no INTEGER NOT NULL,
    beat_type TEXT NOT NULL,
    camera_intent TEXT NOT NULL,
    emotion_intent TEXT NOT NULL,
    action_intent TEXT NOT NULL,
    target_duration_sec INTEGER NOT NULL,
    continuity_rules TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (
        sequence_run_id,
        content_mode,
        policy_profile_id
    ) REFERENCES sequence_runs(id, content_mode, policy_profile_id) ON DELETE CASCADE,
    UNIQUE (sequence_run_id, shot_no),
    UNIQUE (id, content_mode, policy_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_sequence_shots_run
    ON sequence_shots(sequence_run_id, shot_no);

CREATE TABLE IF NOT EXISTS shot_anchor_candidates (
    id TEXT PRIMARY KEY,
    sequence_shot_id TEXT NOT NULL,
    content_mode TEXT NOT NULL,
    policy_profile_id TEXT NOT NULL,
    generation_id TEXT NOT NULL,
    identity_score REAL,
    location_lock_score REAL,
    beat_fit_score REAL,
    quality_score REAL,
    is_selected_primary INTEGER NOT NULL DEFAULT 0,
    is_selected_backup INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (
        sequence_shot_id,
        content_mode,
        policy_profile_id
    ) REFERENCES sequence_shots(id, content_mode, policy_profile_id) ON DELETE CASCADE,
    FOREIGN KEY (generation_id) REFERENCES generations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_shot_anchor_candidates_shot
    ON shot_anchor_candidates(sequence_shot_id, quality_score DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS shot_clips (
    id TEXT PRIMARY KEY,
    sequence_shot_id TEXT NOT NULL,
    content_mode TEXT NOT NULL,
    policy_profile_id TEXT NOT NULL,
    selected_animation_job_id TEXT,
    clip_path TEXT,
    clip_duration_sec REAL,
    clip_score REAL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    is_degraded INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (
        sequence_shot_id,
        content_mode,
        policy_profile_id
    ) REFERENCES sequence_shots(id, content_mode, policy_profile_id) ON DELETE CASCADE,
    FOREIGN KEY (selected_animation_job_id) REFERENCES animation_jobs(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_shot_clips_shot
    ON shot_clips(sequence_shot_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS rough_cuts (
    id TEXT PRIMARY KEY,
    sequence_run_id TEXT NOT NULL,
    content_mode TEXT NOT NULL,
    policy_profile_id TEXT NOT NULL,
    output_path TEXT,
    timeline_json TEXT,
    total_duration_sec REAL,
    continuity_score REAL,
    story_score REAL,
    overall_score REAL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (
        sequence_run_id,
        content_mode,
        policy_profile_id
    ) REFERENCES sequence_runs(id, content_mode, policy_profile_id) ON DELETE CASCADE,
    UNIQUE (sequence_run_id, id),
    UNIQUE (sequence_run_id, id, content_mode, policy_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_rough_cuts_run
    ON rough_cuts(sequence_run_id, overall_score DESC, updated_at DESC);
