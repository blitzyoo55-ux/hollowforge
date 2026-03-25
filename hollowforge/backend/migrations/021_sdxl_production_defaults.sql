UPDATE presets
SET default_params = '{"steps":30,"cfg":5.5,"width":832,"height":1216,"sampler":"euler_ancestral","scheduler":"normal","clip_skip":2}'
WHERE id IN (
    'hf_main_series_e_hood',
    'hf_main_series_c_silent',
    'hf_main_series_b_gaze'
);
