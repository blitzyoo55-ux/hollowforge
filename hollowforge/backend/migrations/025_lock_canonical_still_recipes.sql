INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_kaede_ren_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_kaede_ren' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_imani_adebayo_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_imani_adebayo' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_nia_laurent_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_nia_laurent' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_camila_duarte_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_camila_duarte' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_mina_sato_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_mina_sato' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_celeste_moretti_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_celeste_moretti' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_mireya_solis_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_mireya_solis' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_freya_lindholm_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_freya_lindholm' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_lucia_moreau_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_lucia_moreau' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_hana_seo_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_hana_seo' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_elena_petrov_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_elena_petrov' AND purpose = 'still_default';

INSERT OR IGNORE INTO character_versions (
    id, character_id, version_name, purpose, checkpoint, workflow_lane, loras,
    steps, cfg, sampler, scheduler, clip_skip, width, height, negative_prompt,
    prompt_prefix, prompt_suffix_guidance, created_at, updated_at
)
SELECT
    'charver_keira_okafor_canonical_still_v1',
    character_id,
    'canonical_still_v1',
    'canonical_still',
    checkpoint,
    workflow_lane,
    loras,
    steps,
    cfg,
    sampler,
    scheduler,
    clip_skip,
    width,
    height,
    negative_prompt,
    prompt_prefix,
    prompt_suffix_guidance,
    '2026-03-21T00:00:00Z',
    '2026-03-21T00:00:00Z'
FROM character_versions
WHERE character_id = 'char_keira_okafor' AND purpose = 'still_default';
