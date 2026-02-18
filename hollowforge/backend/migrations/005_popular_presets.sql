-- Additional production presets based on local benchmark reports.
-- Source: docs/phase0_benchmark_v2_report_20260217.md

INSERT OR IGNORE INTO presets (
    id,
    name,
    description,
    checkpoint,
    loras,
    prompt_template,
    negative_prompt,
    default_params,
    tags,
    created_at
)
VALUES
(
    'hf_main_series_e_hood',
    'HF Main - Series E Hood Signature',
    'Faceless hood signature look tuned for high-contrast latex editorial output.',
    'waiIllustriousSDXL_v160.safetensors',
    '[
      {"filename":"incase_new_style_red_ill.safetensors","strength":0.7,"category":"style"},
      {"filename":"DetailedEyes_V3.safetensors","strength":0.45,"category":"eyes"},
      {"filename":"Shiny_Clothes_and_Skin_Latex_Illustrious.safetensors","strength":0.6,"category":"material"},
      {"filename":"Proper_Latex_Catsuit.safetensors","strength":0.55,"category":"material"}
    ]',
    'masterpiece, best quality, absurdres, ultra detailed, 1girl, solo, mature_female, voluptuous, athletic_build, full latex hood, faceless, glossy black latex catsuit, orange accent reflection, laboratory mood, cinematic rim light, fetish fashion editorial',
    'child, loli, teen, underage, lowres, blurry, bad anatomy, bad hands, extra digits, text, logo, watermark, jpeg artifacts, censored, mosaic censoring',
    '{"steps":28,"cfg":7.0,"width":832,"height":1216,"sampler":"euler","scheduler":"normal","clip_skip":null}',
    '["hf-main","production","series-e","hood","faceless","incase"]',
    '2026-02-18T00:00:00Z'
),
(
    'hf_main_series_c_silent',
    'HF Main - Series C Silent Neon',
    'Cyberpunk neon bondage direction optimized for viral visual impact.',
    'waiIllustriousSDXL_v160.safetensors',
    '[
      {"filename":"incase_new_style_red_ill.safetensors","strength":0.7,"category":"style"},
      {"filename":"DetailedEyes_V3.safetensors","strength":0.5,"category":"eyes"},
      {"filename":"Shiny_Clothes_and_Skin_Latex_Illustrious.safetensors","strength":0.55,"category":"material"},
      {"filename":"Harness_Panel_Gag_IL.safetensors","strength":0.65,"category":"fetish"}
    ]',
    'masterpiece, best quality, absurdres, ultra detailed, 1girl, solo, mature_female, glossy latex catsuit, harness, ball gag, blindfold, cyberpunk neon street, rain, dramatic backlight, high contrast, cinematic fetish editorial',
    'child, loli, teen, underage, lowres, blurry, bad anatomy, bad hands, extra digits, text, logo, watermark, jpeg artifacts, censored, mosaic censoring',
    '{"steps":28,"cfg":7.0,"width":832,"height":1216,"sampler":"euler","scheduler":"normal","clip_skip":null}',
    '["hf-main","production","series-c","cyberpunk","bondage","incase"]',
    '2026-02-18T00:00:00Z'
),
(
    'hf_main_series_b_gaze',
    'HF Main - Series B Gaze Focus',
    'Eye-impact focused dungeon composition with balanced style/material control.',
    'waiIllustriousSDXL_v160.safetensors',
    '[
      {"filename":"incase_new_style_red_ill.safetensors","strength":0.68,"category":"style"},
      {"filename":"DetailedEyes_V3.safetensors","strength":0.55,"category":"eyes"},
      {"filename":"Shiny_Clothes_and_Skin_Latex_Illustrious.safetensors","strength":0.55,"category":"material"},
      {"filename":"Proper_Latex_Catsuit.safetensors","strength":0.45,"category":"material"}
    ]',
    'masterpiece, best quality, absurdres, ultra detailed, 1girl, solo, mature_female, intense eye contact, half mask, mouth covered, glossy latex catsuit, concrete dungeon, hard studio light, moody atmosphere, fetish editorial portrait',
    'child, loli, teen, underage, lowres, blurry, bad anatomy, bad hands, extra digits, text, logo, watermark, jpeg artifacts, censored, mosaic censoring',
    '{"steps":28,"cfg":7.0,"width":832,"height":1216,"sampler":"euler","scheduler":"normal","clip_skip":null}',
    '["hf-main","production","series-b","gaze","dungeon","incase"]',
    '2026-02-18T00:00:00Z'
);
