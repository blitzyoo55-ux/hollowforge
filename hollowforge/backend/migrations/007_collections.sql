-- generations에 즐겨찾기 컬럼 추가
ALTER TABLE generations ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0;

-- 컬렉션 테이블
CREATE TABLE IF NOT EXISTS collections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    cover_image_id TEXT,  -- 대표 이미지 (generation id)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

-- 컬렉션-이미지 매핑
CREATE TABLE IF NOT EXISTS collection_items (
    collection_id TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    generation_id TEXT NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (collection_id, generation_id)
);

CREATE INDEX IF NOT EXISTS idx_generations_favorite ON generations(is_favorite);
CREATE INDEX IF NOT EXISTS idx_collection_items_collection ON collection_items(collection_id);
CREATE INDEX IF NOT EXISTS idx_collection_items_generation ON collection_items(generation_id);
