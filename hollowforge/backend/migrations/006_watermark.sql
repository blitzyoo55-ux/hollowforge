-- 워터마크 설정 테이블
CREATE TABLE IF NOT EXISTS watermark_settings (
    id INTEGER PRIMARY KEY DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 0,
    text TEXT DEFAULT 'Lab-XX',
    position TEXT NOT NULL DEFAULT 'bottom-right',  -- top-left/top-right/bottom-left/bottom-right/center
    opacity REAL NOT NULL DEFAULT 0.6,
    font_size INTEGER NOT NULL DEFAULT 36,
    padding INTEGER NOT NULL DEFAULT 20,
    color TEXT NOT NULL DEFAULT '#FFFFFF',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO watermark_settings (id) VALUES (1);

-- generations 테이블에 watermarked_path 컬럼 추가
ALTER TABLE generations ADD COLUMN watermarked_path TEXT;
