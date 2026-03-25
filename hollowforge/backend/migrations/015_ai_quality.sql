-- AI-based quality assessment columns on generations table
ALTER TABLE generations ADD COLUMN quality_tags TEXT DEFAULT NULL;     -- JSON array of detected WD14 quality tags
ALTER TABLE generations ADD COLUMN quality_ai_score INTEGER DEFAULT NULL; -- 0-100 AI quality score
ALTER TABLE generations ADD COLUMN hand_count INTEGER DEFAULT NULL;    -- MediaPipe: number of hands detected
ALTER TABLE generations ADD COLUMN finger_anomaly INTEGER DEFAULT 0;   -- 1 if abnormal finger count detected
