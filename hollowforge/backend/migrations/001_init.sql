-- HollowForge initial schema
-- Applied automatically by app.db.init_db()

CREATE TABLE IF NOT EXISTS presets (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    checkpoint      TEXT NOT NULL,
    loras           TEXT NOT NULL DEFAULT '[]',       -- JSON array of LoraInput
    prompt_template TEXT,
    negative_prompt TEXT,
    default_params  TEXT NOT NULL DEFAULT '{}',       -- JSON dict
    tags            TEXT,                              -- JSON array
    created_at      TEXT NOT NULL,
    updated_at      TEXT
);

CREATE TABLE IF NOT EXISTS generations (
    id                  TEXT PRIMARY KEY,
    prompt              TEXT NOT NULL,
    negative_prompt     TEXT,
    checkpoint          TEXT NOT NULL,
    loras               TEXT NOT NULL DEFAULT '[]',   -- JSON array of LoraInput
    seed                INTEGER NOT NULL,
    steps               INTEGER NOT NULL DEFAULT 28,
    cfg                 REAL NOT NULL DEFAULT 7.0,
    width               INTEGER NOT NULL DEFAULT 832,
    height              INTEGER NOT NULL DEFAULT 1216,
    sampler             TEXT NOT NULL DEFAULT 'euler',
    scheduler           TEXT NOT NULL DEFAULT 'normal',
    status              TEXT NOT NULL DEFAULT 'queued',
    image_path          TEXT,
    thumbnail_path      TEXT,
    workflow_path       TEXT,
    generation_time_sec REAL,
    tags                TEXT,                          -- JSON array
    preset_id           TEXT REFERENCES presets(id) ON DELETE SET NULL,
    notes               TEXT,
    source_id           TEXT,
    comfyui_prompt_id   TEXT,
    error_message       TEXT,
    created_at          TEXT NOT NULL,
    completed_at        TEXT
);

CREATE TABLE IF NOT EXISTS lora_profiles (
    id                      TEXT PRIMARY KEY,
    display_name            TEXT NOT NULL,
    filename                TEXT NOT NULL UNIQUE,
    category                TEXT NOT NULL,
    default_strength        REAL NOT NULL DEFAULT 0.7,
    tags                    TEXT,
    notes                   TEXT,
    compatible_checkpoints  TEXT,
    created_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mood_mappings (
    id                TEXT PRIMARY KEY,
    mood_keyword      TEXT NOT NULL UNIQUE,
    lora_ids          TEXT NOT NULL DEFAULT '[]',   -- JSON array of lora_profile ids
    prompt_additions  TEXT,
    created_at        TEXT NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_generations_status     ON generations(status);
CREATE INDEX IF NOT EXISTS idx_generations_created_at  ON generations(created_at);
CREATE INDEX IF NOT EXISTS idx_generations_checkpoint  ON generations(checkpoint);

-- =========================================================================
-- Seed data: lora_profiles
-- =========================================================================

INSERT OR IGNORE INTO lora_profiles (id, display_name, filename, category, default_strength, tags, notes, compatible_checkpoints, created_at)
VALUES
    ('incase',       'Incase Style',    'incase_new_style_red_ill.safetensors',                 'style',    0.7, NULL, NULL, NULL, '2026-02-17T00:00:00Z'),
    ('ickpot',       'Ickpot Style',    'IckpotIXL_v1.safetensors',                             'style',    0.7, NULL, NULL, NULL, '2026-02-17T00:00:00Z'),
    ('detailed_eyes','Detailed Eyes',   'DetailedEyes_V3.safetensors',                          'eyes',     0.5, NULL, NULL, NULL, '2026-02-17T00:00:00Z'),
    ('shiny_clothes','Shiny Clothes',   'Shiny_Clothes_and_Skin_Latex_Illustrious.safetensors', 'material', 0.6, NULL, NULL, NULL, '2026-02-17T00:00:00Z'),
    ('proper_latex', 'Proper Latex',    'Proper_Latex_Catsuit.safetensors',                     'material', 0.6, NULL, NULL, NULL, '2026-02-17T00:00:00Z'),
    ('harness_gag',  'Harness Gag',     'Harness_Panel_Gag_IL.safetensors',                    'fetish',   0.7, NULL, NULL, NULL, '2026-02-17T00:00:00Z'),
    ('latex_huger',  'Latex Huger',     'latex_huger_c7-1+76-1+64-4.safetensors',              'fetish',   0.5, NULL, NULL, NULL, '2026-02-17T00:00:00Z'),
    ('wan_nsfw',     'WAN NSFW',        'wan-nsfw.safetensors',                                 'fetish',   0.6, NULL, NULL, NULL, '2026-02-17T00:00:00Z');

-- =========================================================================
-- Seed data: mood_mappings
-- =========================================================================

INSERT OR IGNORE INTO mood_mappings (id, mood_keyword, lora_ids, prompt_additions, created_at)
VALUES
    ('mood_cyberpunk', 'cyberpunk',  '["shiny_clothes","harness_gag"]',    'cyberpunk neon street, rain, neon backlight, dramatic mood',           '2026-02-17T00:00:00Z'),
    ('mood_dungeon',   'dungeon',    '["proper_latex","latex_huger"]',     'concrete dungeon, hard studio light, moody atmosphere',                '2026-02-17T00:00:00Z'),
    ('mood_lab',       'lab',        '["proper_latex","shiny_clothes"]',   'laboratory, white tile wall, scientific equipment, cinematic rim light','2026-02-17T00:00:00Z'),
    ('mood_latex',     'latex',      '["shiny_clothes","proper_latex"]',   'glossy latex catsuit, full body latex, fetish fashion editorial',      '2026-02-17T00:00:00Z'),
    ('mood_bondage',   'bondage',    '["harness_gag","latex_huger"]',      'restrained aesthetic, harness, dramatic mood',                        '2026-02-17T00:00:00Z');

-- =========================================================================
-- Seed data: presets (Series A-E from benchmark_runner_v2)
-- =========================================================================

INSERT OR IGNORE INTO presets (id, name, description, checkpoint, loras, prompt_template, negative_prompt, default_params, tags, created_at)
VALUES
    ('series_a', 'Series A - Gas Mask Lab',
     'Full-face gas mask in laboratory setting',
     'waiIllustriousSDXL_v160.safetensors',
     '[{"filename":"Proper_Latex_Catsuit.safetensors","strength":0.6,"category":"material"}]',
     'masterpiece, best quality, ultra detailed, absurdres, highres, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, beautiful detailed eyes, expressive eyes, thick eyelashes, glossy latex catsuit, full body latex, full-face gas mask, sealed mask, faceless, orange accent straps, black bodysuit, laboratory, white tile wall, scientific equipment, standing, full body, cinematic rim light, dramatic shadows, high contrast, fetish fashion editorial',
     'child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, bad hands, extra fingers, extra digits, malformed limbs, deformed face, text, logo, watermark, jpeg artifacts, mosaic censoring, censored, bar censor, light censor, censoring',
     '{"steps":28,"cfg":7.0,"width":832,"height":1216,"sampler":"euler","scheduler":"normal"}',
     '["benchmark","series_a","gas_mask","lab"]',
     '2026-02-17T00:00:00Z'),

    ('series_b', 'Series B - Dungeon Half Mask',
     'Half mask in concrete dungeon',
     'waiIllustriousSDXL_v160.safetensors',
     '[{"filename":"Proper_Latex_Catsuit.safetensors","strength":0.5,"category":"material"}]',
     'masterpiece, best quality, ultra detailed, absurdres, highres, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, beautiful detailed eyes, intense eye contact, half mask, mouth covered, visible eyes only, glossy latex catsuit, full body latex, black and orange palette, concrete dungeon, kneeling, cowboy shot, hard studio light, moody atmosphere, fetish editorial',
     'child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, bad hands, extra fingers, extra digits, malformed limbs, deformed face, text, logo, watermark, jpeg artifacts, mosaic censoring, censored, bar censor, light censor, censoring',
     '{"steps":28,"cfg":7.0,"width":832,"height":1216,"sampler":"euler","scheduler":"normal"}',
     '["benchmark","series_b","dungeon","half_mask"]',
     '2026-02-17T00:00:00Z'),

    ('series_c', 'Series C - Cyberpunk Bondage',
     'Ball gag + blindfold in cyberpunk neon street',
     'waiIllustriousSDXL_v160.safetensors',
     '[{"filename":"Harness_Panel_Gag_IL.safetensors","strength":0.7,"category":"fetish"}]',
     'masterpiece, best quality, ultra detailed, absurdres, highres, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, beautiful detailed eyes, ball gag, blindfold, restrained aesthetic, glossy latex catsuit, black latex straps, harness, orange neon light, cyberpunk neon street, rain, standing, full body, neon backlight, dramatic mood, fetish editorial',
     'child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, bad hands, extra fingers, extra digits, malformed limbs, deformed face, text, logo, watermark, jpeg artifacts, mosaic censoring, censored, bar censor, light censor, censoring',
     '{"steps":28,"cfg":7.0,"width":832,"height":1216,"sampler":"euler","scheduler":"normal"}',
     '["benchmark","series_c","cyberpunk","bondage"]',
     '2026-02-17T00:00:00Z'),

    ('series_d', 'Series D - Kigurumi Dungeon',
     'Kigurumi mask in dungeon',
     'waiIllustriousSDXL_v160.safetensors',
     '[{"filename":"latex_huger_c7-1+76-1+64-4.safetensors","strength":0.5,"category":"fetish"}]',
     'masterpiece, best quality, ultra detailed, absurdres, highres, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, beautiful detailed eyes, kigurumi mask, expressionless doll face mask, glossy latex catsuit, black and orange accents, concrete dungeon, kneeling, full body, spotlight, surreal fashion, clean composition',
     'child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, bad hands, extra fingers, extra digits, malformed limbs, deformed face, text, logo, watermark, jpeg artifacts, mosaic censoring, censored, bar censor, light censor, censoring',
     '{"steps":28,"cfg":7.0,"width":832,"height":1216,"sampler":"euler","scheduler":"normal"}',
     '["benchmark","series_d","kigurumi","dungeon"]',
     '2026-02-17T00:00:00Z'),

    ('series_e', 'Series E - Full Hood Lab',
     'Full latex hood in laboratory',
     'waiIllustriousSDXL_v160.safetensors',
     '[{"filename":"Proper_Latex_Catsuit.safetensors","strength":0.7,"category":"material"}]',
     'masterpiece, best quality, ultra detailed, absurdres, highres, 1girl, solo, mature_female, voluptuous, athletic_build, tall, long_legs, full latex hood, completely covered head, no hair visible, faceless, glossy latex catsuit, black latex shine, orange reflected light, laboratory, white tile wall, standing, low angle full body, cinematic rim light, atmospheric haze, fetish fashion editorial',
     'child, loli, teen, underage, flat_chest, school_uniform, lowres, blurry, bad anatomy, bad hands, extra fingers, extra digits, malformed limbs, deformed face, text, logo, watermark, jpeg artifacts, mosaic censoring, censored, bar censor, light censor, censoring',
     '{"steps":28,"cfg":7.0,"width":832,"height":1216,"sampler":"euler","scheduler":"normal"}',
     '["benchmark","series_e","full_hood","lab"]',
     '2026-02-17T00:00:00Z');
