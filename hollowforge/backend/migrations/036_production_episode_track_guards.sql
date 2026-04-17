CREATE INDEX IF NOT EXISTS idx_sequence_blueprints_production_episode_id
ON sequence_blueprints (production_episode_id)
WHERE production_episode_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_comic_episodes_production_episode_id
ON comic_episodes (production_episode_id)
WHERE production_episode_id IS NOT NULL;

CREATE TRIGGER IF NOT EXISTS trg_sequence_blueprints_production_episode_insert_guard
BEFORE INSERT ON sequence_blueprints
FOR EACH ROW
WHEN NEW.production_episode_id IS NOT NULL
 AND EXISTS (
    SELECT 1
    FROM sequence_blueprints
    WHERE production_episode_id = NEW.production_episode_id
 )
BEGIN
    SELECT RAISE(ABORT, 'sequence_blueprints.production_episode_id already linked');
END;

CREATE TRIGGER IF NOT EXISTS trg_sequence_blueprints_production_episode_update_guard
BEFORE UPDATE OF production_episode_id ON sequence_blueprints
FOR EACH ROW
WHEN NEW.production_episode_id IS NOT NULL
 AND EXISTS (
    SELECT 1
    FROM sequence_blueprints
    WHERE production_episode_id = NEW.production_episode_id
      AND id <> NEW.id
 )
BEGIN
    SELECT RAISE(ABORT, 'sequence_blueprints.production_episode_id already linked');
END;

CREATE TRIGGER IF NOT EXISTS trg_comic_episodes_production_episode_insert_guard
BEFORE INSERT ON comic_episodes
FOR EACH ROW
WHEN NEW.production_episode_id IS NOT NULL
 AND EXISTS (
    SELECT 1
    FROM comic_episodes
    WHERE production_episode_id = NEW.production_episode_id
 )
BEGIN
    SELECT RAISE(ABORT, 'comic_episodes.production_episode_id already linked');
END;

CREATE TRIGGER IF NOT EXISTS trg_comic_episodes_production_episode_update_guard
BEFORE UPDATE OF production_episode_id ON comic_episodes
FOR EACH ROW
WHEN NEW.production_episode_id IS NOT NULL
 AND EXISTS (
    SELECT 1
    FROM comic_episodes
    WHERE production_episode_id = NEW.production_episode_id
      AND id <> NEW.id
 )
BEGIN
    SELECT RAISE(ABORT, 'comic_episodes.production_episode_id already linked');
END;
