ALTER TABLE characters ADD COLUMN profession TEXT;
ALTER TABLE characters ADD COLUMN natural_scene_briefs TEXT NOT NULL DEFAULT '[]';

UPDATE characters
SET
    profession = 'Luxury gallery brand strategist',
    natural_scene_briefs = '[
        "opening-hour gallery walkthrough in a black knit top and tailored skirt, clipboard and coffee in hand, quiet museum light, composed professional calm",
        "subway platform commute in a long charcoal coat and headphones, city morning realism, reserved eye line, precise bob silhouette",
        "bookstore design-reference browse with a slim tote and phone, half-turn glance, understated weekday elegance",
        "home desk moodboard review with swatches and a laptop, late-afternoon apartment light, calm and detail-focused energy",
        "convenience-store umbrella stop after light rain, fitted knit and coat, ordinary neighborhood realism, unforced beauty",
        "balcony workday closeout with a mug and open laptop, soft dusk light, controlled posture, quiet city-life intimacy"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_kaede_ren';

UPDATE characters
SET
    profession = 'Boutique hospitality creative director',
    natural_scene_briefs = '[
        "hotel lobby pre-opening walkthrough in a structured blazer over luxe basics, tablet in hand, warm early light, grounded authority",
        "elevator mirror pause before a client meeting, simple jewelry, relaxed but self-possessed expression, believable workday tension",
        "florist pickup for an event installation, bouquet against dark skin, natural street daylight, strong everyday charisma",
        "cafe corner reviewing venue sketches and voice notes, composed posture, lived-in urban calm, not glamorized",
        "quiet apartment kitchen reset after work, glass of water and blazer draped nearby, rich skin texture, intimate realism",
        "rooftop decompression after a long day, soft evening air in the curls, city lights beginning to glow, mature calm"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_imani_adebayo';

UPDATE characters
SET
    profession = 'Motorsport partnership producer',
    natural_scene_briefs = '[
        "paddock-side planning check in a clean bomber and tailored trousers, credential lanyard, candid between-meetings realism",
        "metro stairwell commute with a tablet and coffee, textured curls visible, brisk weekday movement without fashion posing",
        "trackside cafe break reviewing sponsor notes, sporty-luxury wardrobe, relaxed shoulders, everyday focus",
        "office whiteboard session with event maps and marker notes, polished posture, natural work intensity",
        "night bus stop after an event, long coat over practical layers, cool urban atmosphere, slightly tired but composed",
        "rooftop cooldown after a race-day schedule, one hand on the rail, loosened jacket, city-night air, confident realism"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_nia_laurent';

UPDATE characters
SET
    profession = 'Resort lifestyle content editor',
    natural_scene_briefs = '[
        "seaside cafe morning planning in a linen shirt and fitted shorts, iced coffee and notebook, bright but gentle coastal light",
        "produce market stop with a woven bag and fruit, chestnut hair moving naturally, everyday warmth over polished glamour",
        "apartment kitchen fruit slicing and playlist moment, open window breeze, casual domestic ease, unforced smile",
        "balcony plant care in a soft knit tank and loose shirt, bronzed skin in daylight, relaxed neighborhood realism",
        "ride-share wait outside a corner store in an easy summer layer, natural stance, warm late-afternoon street tone",
        "boardwalk sunset walk with a light cardigan over a simple dress, easygoing charm, believable vacation-town calm"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_camila_duarte';

UPDATE characters
SET
    profession = 'Fashion magazine features editor',
    natural_scene_briefs = '[
        "editorial desk proof review with magazines and marked pages, tailored blouse, soft office light, approachable focus",
        "bookstore magazine shelf check in a blazer and skirt, half-turn glance, polished but ordinary city routine",
        "train window seat commute with earbuds and tote bag, warm reflected light, quiet weekday introspection",
        "small studio prep corner before a beauty shoot, simple mirror and notes, soft expression, commercial-natural polish",
        "convenience-store lunch run in clean citywear, realistic fluorescent light, casual public-facing charm",
        "evening laundry fold with music playing in the apartment, comfortable knitwear, lived-in softness, warm personality"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_mina_sato';

UPDATE characters
SET
    profession = 'Independent art patron and gallery donor liaison',
    natural_scene_briefs = '[
        "townhouse window breakfast with letters and tea, oversized shirt over fitted shorts, old-home calm, understated elegance",
        "florist counter choosing stems for an event, auburn hair in soft daylight, natural decision-making posture",
        "museum afternoon with audio guide and long coat, quiet cultural routine, refined but unforced presence",
        "home library reading chair with cardigan and glasses nearby, gentle room light, personality-first stillness",
        "bakery morning run with paper bag and knit dress, neighborhood realism, luminous but not polished to excess",
        "raincoat doorway return at dusk, one hand on the keys, quiet-luxury mood grounded in everyday life"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_celeste_moretti';

UPDATE characters
SET
    profession = 'Interior styling consultant',
    natural_scene_briefs = '[
        "material swatch review at a home studio desk, rolled samples and coffee nearby, practical design-day realism",
        "fruit market grocery run in a light shirt and fitted shorts, warm street life, relaxed modern charm",
        "laundromat wait with a paperback and tote, ordinary neighborhood scene, playful but believable posture",
        "balcony hair-dry moment in lounge knitwear, warm daylight, soft athletic silhouette, unforced apartment intimacy",
        "corner cafe laptop check between client visits, honey-brown eye line slightly off-camera, grounded weekday rhythm",
        "late-night fridge-light snack pause in an oversized tee and shorts, cinematic domestic realism, warm expression"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_mireya_solis';

UPDATE characters
SET
    profession = 'Fine jewelry brand director',
    natural_scene_briefs = '[
        "showroom inventory check in a soft cashmere top and tailored skirt, trays of jewelry nearby, cool natural light",
        "airport lounge reading between meetings, long coat and carry-on, restrained luxury in a believable transit scene",
        "overcast city commute with a coffee and gloves, platinum hair under a clean coat collar, realistic cold-weather mood",
        "apartment kitchen moment in an oversized shirt, quiet breakfast prep, crisp daylight, less staged elegance",
        "glass desk sketch review for a product launch, focused expression, believable work posture, premium but grounded",
        "flower kiosk stop after work with wrapped stems, cool evening light, calm high-status realism"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_freya_lindholm';

UPDATE characters
SET
    profession = 'Independent film actress and voice coach',
    natural_scene_briefs = '[
        "rehearsal room script markup with a pencil and mug, relaxed shoulders, expressive face at rest, studio realism",
        "tram ride home with a folded coat and annotated pages, green eyes turned toward the window, lived-in city mood",
        "small cafe reading corner between auditions, simple blouse and skirt, natural afternoon light, unforced charm",
        "record player shelf pause in the apartment, one hand on a vinyl sleeve, classic personal taste, grounded intimacy",
        "bakery morning stop with a paper bag and sunglasses in hand, Mediterranean softness, neighborhood routine",
        "late practice room cleanup near a piano bench, warm lamp light, quiet after-hours calm, classic beauty without stage glamour"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_lucia_moreau';

UPDATE characters
SET
    profession = 'Skincare brand product strategist',
    natural_scene_briefs = '[
        "product note review at a clean studio desk, sample jars and a laptop nearby, precise workday calm",
        "office elevator mirror hair tuck before a meeting, monochrome workwear, natural fluorescent realism",
        "beauty aisle product comparison with a basket in hand, ordinary retail lighting, understated polish",
        "apartment sink tea rinse and handwashing moment, soft shirt sleeves rolled, domestic realism, quiet composure",
        "rooftop air break after meetings in a camel coat, obsidian bob edges visible, evening cool-down without posing",
        "bookstore design shelf browse with a simple tote, precise silhouette, calm off-duty elegance"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_hana_seo';

UPDATE characters
SET
    profession = 'Couture atelier consultant',
    natural_scene_briefs = '[
        "atelier fitting notes beside a garment rack, pencil and fabric tags in hand, practical work realism over runway polish",
        "morning window reading in a long coat and knit top, cool daylight, composed aristocratic calm made ordinary",
        "museum archive corridor walk with a document folder, quiet institutional light, believable weekday elegance",
        "tram stop with gloves and tote after work, ash-brown hair moving slightly in the cold, grounded city realism",
        "tea at the kitchen counter in a fitted knit and relaxed trousers, simple domestic stillness, not editorialized",
        "desk lamp sketch edit with swatches and notes, steel-blue gaze focused downward, graceful realism over couture drama"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_elena_petrov';

UPDATE characters
SET
    profession = 'Fashion casting director',
    natural_scene_briefs = '[
        "casting board review with printed headshots and sticky notes, relaxed blazer, purposeful work energy, believable office light",
        "corner cafe between meetings with a phone and planner, rich skin and curl silhouette in natural daylight, mature calm",
        "night bus exit in a long trench after a late workday, city sodium light, grounded nightlife-adjacent realism",
        "studio staircase break with tote and water bottle, practical pause, fashion-world routine rather than glam posing",
        "dry cleaner pickup after work with garment bag over one arm, ordinary street moment, understated confidence",
        "apartment speaker setup with vinyl sleeves on the floor, comfortable knitwear, off-duty personality, quiet evening realism"
    ]',
    updated_at = '2026-03-22T00:00:00Z'
WHERE id = 'char_keira_okafor';
