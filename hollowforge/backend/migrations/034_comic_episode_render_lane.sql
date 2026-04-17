ALTER TABLE comic_episodes
    ADD COLUMN render_lane TEXT NOT NULL DEFAULT 'legacy';

ALTER TABLE comic_episodes
    ADD COLUMN series_style_id TEXT;

ALTER TABLE comic_episodes
    ADD COLUMN character_series_binding_id TEXT;
