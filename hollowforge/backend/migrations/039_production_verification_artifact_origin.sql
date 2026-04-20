ALTER TABLE works ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator';
ALTER TABLE works ADD COLUMN verification_run_id TEXT;

ALTER TABLE series ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator';
ALTER TABLE series ADD COLUMN verification_run_id TEXT;

ALTER TABLE production_episodes ADD COLUMN record_origin TEXT NOT NULL DEFAULT 'operator';
ALTER TABLE production_episodes ADD COLUMN verification_run_id TEXT;
