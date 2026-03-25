-- Optional analytics column: stores full WD14 tag dictionary (tag -> confidence)
ALTER TABLE generations ADD COLUMN all_tags_json TEXT DEFAULT NULL;
