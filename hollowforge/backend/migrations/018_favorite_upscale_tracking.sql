ALTER TABLE generations ADD COLUMN favorited_at TEXT;
ALTER TABLE generations ADD COLUMN favorite_upscale_queued_at TEXT;

UPDATE generations
SET favorited_at = COALESCE(favorited_at, created_at)
WHERE is_favorite = 1
  AND favorited_at IS NULL;
