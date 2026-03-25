ALTER TABLE characters
ADD COLUMN natural_shot_overrides TEXT NOT NULL DEFAULT '{}';

UPDATE characters
SET natural_shot_overrides = json('{
  "scene_01_close_anchor": {
    "checkpoint": "prefectIllustriousXL_v70.safetensors",
    "loras": [],
    "cfg": 4.8,
    "prompt_prefix": "masterpiece, best quality, original character, adult woman, solo, single subject only, one woman only, fully clothed, natural character portrait, calm expression, subtle skin texture, soft ambient light, delicate linework, painterly shading, quiet lived-in realism",
    "scene_brief": "quiet product-note review at a work desk, one consistent hairstyle and one consistent face, grounded studio realism with no outfit split or second body",
    "camera": "tight chest-up portrait, one consistent face dominating the frame, no side-by-side body, no split composition",
    "depth": "desk edge or notebook in the foreground, one clear subject in the midground, shallow but readable room depth behind",
    "interaction": "one hand on a notebook, pen, or cup so the body reads as one continuous pose",
    "background": "single-room work setting with no doorway reveal, no reflective duplication, no mirrored centerline",
    "negative_prompt_extra": "split face, split hair color, dual hairstyle, two-tone face, composite portrait, two outfits in one body, duplicate torso, second woman"
  },
  "scene_05_exterior_transition": {
    "checkpoint": "prefectIllustriousXL_v70.safetensors",
    "loras": [],
    "cfg": 4.8,
    "prompt_prefix": "masterpiece, best quality, original character, adult woman, solo, single subject only, one woman only, fully clothed, natural city portrait, relaxed expression, subtle skin texture, soft daylight, delicate linework, painterly shading, grounded urban realism",
    "scene_brief": "solo transition between meetings, one woman checking her phone while moving through a quiet exterior passage, understated weekday realism without pair-fashion energy",
    "camera": "50mm waist-up exterior portrait, one heroine occupying most of the frame, no second body or companion in view",
    "depth": "simple walkway or wall edge in the foreground, one clear subject in the midground, soft exterior depth behind without pedestrians",
    "interaction": "one hand holding a phone or tote, the other hand in a pocket or on a coat edge, single-body motion only",
    "background": "quiet exterior wall or passage with minimal foot traffic, no second silhouette, no paired street-fashion composition",
    "negative_prompt_extra": "fashion duo, two-shot fashion pose, side-by-side women, second coat, second handbag, conversation pose, street-style pair, extra pedestrian"
  }
}')
WHERE slug = 'hana_seo';

