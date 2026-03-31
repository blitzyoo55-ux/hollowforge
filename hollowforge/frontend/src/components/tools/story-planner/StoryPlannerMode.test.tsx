import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import {
  generateStoryPlannerAnchors,
  getStoryPlannerCatalog,
  planStoryEpisode,
} from '../../../api/client'
import StoryPlannerMode from './StoryPlannerMode'

vi.mock('../../../api/client', () => ({
  generateStoryPlannerAnchors: vi.fn(),
  getStoryPlannerCatalog: vi.fn(),
  planStoryEpisode: vi.fn(),
}))

vi.mock('../../../lib/toast', () => ({
  notify: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function renderMode() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <StoryPlannerMode />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function buildCatalog() {
  return {
    characters: [
      {
        id: 'hana_seo',
        name: 'Hana Seo',
        canonical_anchor: 'Adult Korean woman, luxury skincare strategist.',
        anti_drift: 'Keep Hana adult and composed.',
        wardrobe_notes: 'Monochrome dresses and expensive styling.',
        personality_notes: 'Controlled, observant, private.',
        preferred_checkpoints: ['waiIllustriousSDXL_v140.safetensors'],
      },
      {
        id: 'mina_park',
        name: 'Mina Park',
        canonical_anchor: 'Adult Korean woman, bathhouse operations manager.',
        anti_drift: 'Keep Mina adult and practical.',
        wardrobe_notes: 'Structured workwear and soft knits.',
        personality_notes: 'Protective and pragmatic.',
        preferred_checkpoints: ['waiIllustriousSDXL_v140.safetensors'],
      },
    ],
    locations: [
      {
        id: 'moonlit_bathhouse',
        name: 'Moonlit Bathhouse',
        setting_anchor: 'Premium urban bathhouse with polished stone corridors.',
        visual_rules: ['Stone, wood, steam-softened light.'],
        restricted_elements: ['neon club lighting'],
      },
    ],
    policy_packs: [
      {
        id: 'canon_adult_nsfw_v1',
        lane: 'adult_nsfw' as const,
        prompt_provider_profile_id: 'adult_local_llm_strict_json',
        negative_prompt_mode: 'recommended' as const,
        forbidden_defaults: ['minors', 'age ambiguity', 'non-consensual framing'],
        planner_rules: ['Treat all beats as adult-only material.'],
        render_preferences: {
          default_checkpoint: 'waiIllustriousSDXL_v140.safetensors',
          default_size: '832x1216',
        },
      },
      {
        id: 'canon_all_ages_v1',
        lane: 'all_ages' as const,
        prompt_provider_profile_id: 'safe_hosted_grok',
        negative_prompt_mode: 'recommended' as const,
        forbidden_defaults: ['minors'],
        planner_rules: ['Keep every beat suitable for a general audience.'],
        render_preferences: {
          default_checkpoint: 'waiIllustriousSDXL_v140.safetensors',
          default_size: '832x1216',
        },
      },
    ],
  }
}

function buildPlanResponse() {
  return {
    story_prompt: 'A tense bathhouse rendezvous under soft reflected light.',
    lane: 'adult_nsfw' as const,
    policy_pack_id: 'canon_adult_nsfw_v1',
    approval_token: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    anchor_render: {
      policy_pack_id: 'canon_adult_nsfw_v1',
      checkpoint: 'waiIllustriousSDXL_v140.safetensors',
      workflow_lane: 'sdxl_illustrious' as const,
      negative_prompt: 'minors, age ambiguity, non-consensual framing',
      preserve_blank_negative_prompt: false,
    },
    resolved_cast: [
      {
        role: 'lead' as const,
        source_type: 'registry' as const,
        character_id: 'hana_seo',
        character_name: 'Hana Seo',
        freeform_description: null,
        canonical_anchor: 'Adult Korean woman, luxury skincare strategist.',
        anti_drift: 'Keep Hana adult and composed.',
        wardrobe_notes: 'Monochrome dresses and expensive styling.',
        personality_notes: 'Controlled, observant, private.',
        resolution_note: "Resolved registry character 'hana_seo' from catalog.",
      },
      {
        role: 'support' as const,
        source_type: 'registry' as const,
        character_id: 'mina_park',
        character_name: 'Mina Park',
        freeform_description: null,
        canonical_anchor: 'Adult Korean woman, bathhouse operations manager.',
        anti_drift: 'Keep Mina adult and practical.',
        wardrobe_notes: 'Structured workwear and soft knits.',
        personality_notes: 'Protective and pragmatic.',
        resolution_note: "Resolved registry character 'mina_park' from catalog.",
      },
    ],
    location: {
      id: 'moonlit_bathhouse',
      name: 'Moonlit Bathhouse',
      setting_anchor: 'Premium urban bathhouse with polished stone corridors.',
      visual_rules: ['Stone, wood, steam-softened light.'],
      restricted_elements: ['neon club lighting'],
      match_note: 'Matched prompt keywords to Moonlit Bathhouse.',
    },
    episode_brief: {
      premise: 'At Moonlit Bathhouse, Hana Seo and Mina Park work through the prompt.',
      continuity_guidance: [
        'Keep Moonlit Bathhouse as the only location.',
        "Keep Hana Seo's canon details stable.",
        'Keep the support cast secondary and unresolved.',
      ],
    },
    shots: [
      {
        shot_no: 1,
        beat: 'Establish the scene',
        camera: 'Wide establishing shot inside Moonlit Bathhouse.',
        action: 'Hana Seo enters and takes in the room before anyone speaks.',
        emotion: 'Measured alertness',
        continuity_note: "Hold Moonlit Bathhouse's visual rules.",
      },
      {
        shot_no: 2,
        beat: 'Introduce the exchange',
        camera: 'Medium tracking shot at shoulder height.',
        action: 'Mina Park meets Hana Seo and the first cue is exchanged.',
        emotion: 'Quiet curiosity',
        continuity_note: 'Keep the support presence secondary and readable.',
      },
      {
        shot_no: 3,
        beat: 'Reveal the key detail',
        camera: 'Over-the-shoulder close-up.',
        action: "A message, gesture, or object shifts the scene's stakes.",
        emotion: 'Focused concern',
        continuity_note: 'Preserve the same wardrobe and framing.',
      },
      {
        shot_no: 4,
        beat: 'Close on a decision',
        camera: 'Tight two-shot with shallow depth of field.',
        action: 'Hana Seo commits to the next move while the support beat lingers.',
        emotion: 'Controlled resolve',
        continuity_note: 'End on the same setting anchor.',
      },
    ],
  }
}

function buildPromptOnlyPlanResponse() {
  return {
    ...buildPlanResponse(),
    story_prompt: 'Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing.',
    lane: 'unrestricted' as const,
    policy_pack_id: 'canon_unrestricted_v1',
    anchor_render: {
      policy_pack_id: 'canon_unrestricted_v1',
      checkpoint: 'waiIllustriousSDXL_v140.safetensors',
      workflow_lane: 'sdxl_illustrious' as const,
      negative_prompt: null,
      preserve_blank_negative_prompt: true,
    },
    resolved_cast: [
      {
        role: 'lead' as const,
        source_type: 'freeform' as const,
        character_id: null,
        character_name: null,
        freeform_description: 'Hana Seo',
        canonical_anchor: null,
        anti_drift: null,
        wardrobe_notes: null,
        personality_notes: null,
        resolution_note: 'Derived lead candidate from the story prompt.',
      },
      {
        role: 'support' as const,
        source_type: 'freeform' as const,
        character_id: null,
        character_name: null,
        freeform_description: 'a quiet messenger',
        canonical_anchor: null,
        anti_drift: null,
        wardrobe_notes: null,
        personality_notes: null,
        resolution_note: 'Derived support presence from the story prompt.',
      },
    ],
    episode_brief: {
      premise: 'At Moonlit Bathhouse, Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing.',
      continuity_guidance: [
        'Keep Moonlit Bathhouse as the only location and preserve its visual rules.',
        'Keep Hana Seo canon details stable across all shots.',
        'Keep the support cast secondary while the prompt tension stays anchored on closing.',
      ],
    },
    shots: [
      {
        shot_no: 1,
        beat: 'Establish the scene',
        camera: 'Wide establishing shot inside Moonlit Bathhouse.',
        action: 'Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing',
        emotion: 'Measured alertness',
        continuity_note: "Hold Moonlit Bathhouse's visual rules.",
      },
      {
        shot_no: 2,
        beat: 'Introduce the exchange',
        camera: 'Medium tracking shot at shoulder height.',
        action: 'a quiet messenger shifts the exchange around closing while Hana Seo stays in focus.',
        emotion: 'Quiet curiosity',
        continuity_note: 'Keep the support presence secondary and readable.',
      },
      {
        shot_no: 3,
        beat: 'Reveal the key detail',
        camera: 'Over-the-shoulder close-up.',
        action: 'The key detail comes into focus: closing.',
        emotion: 'Focused concern',
        continuity_note: 'Preserve the same wardrobe and framing.',
      },
      {
        shot_no: 4,
        beat: 'Close on a decision',
        camera: 'Tight two-shot with shallow depth of field.',
        action: 'Hana Seo commits to the next move after closing.',
        emotion: 'Controlled resolve',
        continuity_note: 'End on the same setting anchor.',
      },
    ],
  }
}

function buildGenerationResponse(id: string) {
  return {
    id,
    prompt: `prompt ${id}`,
    negative_prompt: null,
    checkpoint: 'waiIllustriousSDXL_v140.safetensors',
    workflow_lane: 'sdxl_illustrious' as const,
    loras: [],
    seed: 123,
    steps: 28,
    cfg: 7,
    width: 832,
    height: 1216,
    sampler: 'euler',
    scheduler: 'normal',
    clip_skip: null,
    status: 'queued',
    image_path: null,
    watermarked_path: null,
    upscaled_image_path: null,
    adetailed_path: null,
    hiresfix_path: null,
    dreamactor_path: null,
    dreamactor_task_id: null,
    dreamactor_status: null,
    upscaled_preview_path: null,
    upscale_model: null,
    thumbnail_path: null,
    workflow_path: null,
    generation_time_sec: null,
    tags: ['story_planner'],
    preset_id: null,
    notes: null,
    source_id: `story_planner_anchor:${id}`,
    comfyui_prompt_id: null,
    error_message: null,
    is_favorite: false,
    created_at: '2026-03-27T00:00:00+00:00',
    completed_at: null,
  }
}

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getStoryPlannerCatalog).mockResolvedValue(buildCatalog())
  vi.mocked(planStoryEpisode).mockResolvedValue(buildPlanResponse())
  vi.mocked(generateStoryPlannerAnchors).mockResolvedValue({
    lane: 'adult_nsfw',
    requested_shot_count: 4,
    queued_generation_count: 8,
    queued_shots: [
      { shot_no: 1, generation_ids: ['gen-1a', 'gen-1b'] },
      { shot_no: 2, generation_ids: ['gen-2a', 'gen-2b'] },
      { shot_no: 3, generation_ids: ['gen-3a', 'gen-3b'] },
      { shot_no: 4, generation_ids: ['gen-4a', 'gen-4b'] },
    ],
    queued_generations: [
      buildGenerationResponse('gen-1a'),
      buildGenerationResponse('gen-1b'),
      buildGenerationResponse('gen-2a'),
      buildGenerationResponse('gen-2b'),
      buildGenerationResponse('gen-3a'),
      buildGenerationResponse('gen-3b'),
      buildGenerationResponse('gen-4a'),
      buildGenerationResponse('gen-4b'),
    ],
  })
})

test('renders the story prompt input and Plan Episode button', async () => {
  renderMode()

  expect(await screen.findByLabelText(/Story Prompt/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Plan Episode/i })).toBeInTheDocument()
  expect(screen.getByLabelText(/Lane/i)).toHaveValue('unrestricted')
})

test('plans a prompt-only episode without registry characters', async () => {
  vi.mocked(planStoryEpisode).mockResolvedValueOnce(buildPromptOnlyPlanResponse())

  renderMode()

  const promptInput = await screen.findByLabelText(/Story Prompt/i)
  fireEvent.change(promptInput, {
    target: {
      value: 'Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing.',
    },
  })

  fireEvent.click(screen.getByRole('button', { name: /Plan Episode/i }))

  await waitFor(() => {
    expect(planStoryEpisode).toHaveBeenCalledWith({
      story_prompt: 'Hana Seo meets a quiet messenger in the Moonlit Bathhouse corridor after closing.',
      lane: 'unrestricted',
      cast: [],
    })
  })

  expect(screen.getByText('Hana Seo')).toBeInTheDocument()
  expect(screen.getByText('a quiet messenger')).toBeInTheDocument()
  expect(screen.getByText(/Derived lead candidate from the story prompt/i)).toBeInTheDocument()
})

test('renders plan review cards after planner preview succeeds', async () => {
  renderMode()

  const promptInput = await screen.findByLabelText(/Story Prompt/i)
  fireEvent.change(promptInput, { target: { value: 'A tense bathhouse rendezvous.' } })
  fireEvent.click(screen.getByRole('button', { name: /Use Registry Characters/i }))

  fireEvent.click(screen.getByLabelText(/Lead Character/i))
  fireEvent.change(screen.getByLabelText(/Lead Character/i), { target: { value: 'hana_seo' } })
  fireEvent.change(screen.getByLabelText(/Support Character/i), { target: { value: 'mina_park' } })

  fireEvent.click(screen.getByRole('button', { name: /Plan Episode/i }))

  await waitFor(() => {
    expect(planStoryEpisode).toHaveBeenCalledTimes(1)
  })

  expect(screen.getAllByText(/Episode Brief/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/Cast Resolution/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/Location/i).length).toBeGreaterThan(0)
  expect(screen.getByText(/Shot 1/i)).toBeInTheDocument()
  expect(screen.getByText(/Shot 4/i)).toBeInTheDocument()
  expect(screen.getAllByText(/Moonlit Bathhouse/i).length).toBeGreaterThan(0)
})

test('allows approve and generate and shows queued anchor summary', async () => {
  renderMode()

  const promptInput = await screen.findByLabelText(/Story Prompt/i)
  fireEvent.change(promptInput, { target: { value: 'A tense bathhouse rendezvous.' } })
  fireEvent.click(screen.getByRole('button', { name: /Use Registry Characters/i }))
  fireEvent.change(screen.getByLabelText(/Lead Character/i), { target: { value: 'hana_seo' } })
  fireEvent.change(screen.getByLabelText(/Support Character/i), { target: { value: 'mina_park' } })

  fireEvent.click(screen.getByRole('button', { name: /Plan Episode/i }))

  await waitFor(() => {
    expect(planStoryEpisode).toHaveBeenCalledTimes(1)
  })

  fireEvent.click(screen.getByRole('button', { name: /Approve And Generate Anchors/i }))

  await waitFor(() => {
    expect(generateStoryPlannerAnchors).toHaveBeenCalledTimes(1)
  })

  expect(screen.getAllByText(/Queued Anchor Results/i).length).toBeGreaterThan(0)
  expect(screen.getByText(/8 queued anchors/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Queue/i })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Gallery/i })).toBeInTheDocument()

  const summary = screen.getByText(/Queued Anchor Results/i).closest('section')
  expect(summary).not.toBeNull()
  expect(within(summary as HTMLElement).getByText(/Shot 4/i)).toBeInTheDocument()
})

test('ignores late preview success after the prompt changes', async () => {
  renderMode()

  const promptInput = await screen.findByLabelText(/Story Prompt/i)
  fireEvent.change(promptInput, { target: { value: 'A tense bathhouse rendezvous.' } })
  fireEvent.click(screen.getByRole('button', { name: /Use Registry Characters/i }))
  fireEvent.change(screen.getByLabelText(/Lead Character/i), { target: { value: 'hana_seo' } })
  fireEvent.change(screen.getByLabelText(/Support Character/i), { target: { value: 'mina_park' } })

  const deferredPlan = createDeferred<ReturnType<typeof buildPlanResponse>>()
  vi.mocked(planStoryEpisode).mockImplementationOnce(async () => deferredPlan.promise)

  fireEvent.click(screen.getByRole('button', { name: /Plan Episode/i }))

  await waitFor(() => {
    expect(planStoryEpisode).toHaveBeenCalledTimes(1)
  })

  fireEvent.change(promptInput, { target: { value: 'A revised bathhouse rendezvous.' } })

  expect(screen.queryByText(/Plan Review/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/Queued Anchor Results/i)).not.toBeInTheDocument()

  await act(async () => {
    deferredPlan.resolve(buildPlanResponse())
    await Promise.resolve()
  })

  expect(screen.queryByText(/Plan Review/i)).not.toBeInTheDocument()
  expect(screen.queryByText(/Queued Anchor Results/i)).not.toBeInTheDocument()
})

test('ignores late queue success after the support character changes', async () => {
  renderMode()

  const promptInput = await screen.findByLabelText(/Story Prompt/i)
  fireEvent.change(promptInput, { target: { value: 'A tense bathhouse rendezvous.' } })
  fireEvent.click(screen.getByRole('button', { name: /Use Registry Characters/i }))
  fireEvent.change(screen.getByLabelText(/Lead Character/i), { target: { value: 'hana_seo' } })
  fireEvent.change(screen.getByLabelText(/Support Character/i), { target: { value: 'mina_park' } })

  fireEvent.click(screen.getByRole('button', { name: /Plan Episode/i }))

  await waitFor(() => {
    expect(planStoryEpisode).toHaveBeenCalledTimes(1)
  })

  const deferredQueue = createDeferred<Awaited<ReturnType<typeof generateStoryPlannerAnchors>>>()
  vi.mocked(generateStoryPlannerAnchors).mockImplementationOnce(async () => deferredQueue.promise)

  fireEvent.click(screen.getByRole('button', { name: /Approve And Generate Anchors/i }))

  await waitFor(() => {
    expect(generateStoryPlannerAnchors).toHaveBeenCalledTimes(1)
  })

  fireEvent.change(screen.getByLabelText(/Support Character/i), { target: { value: 'hana_seo' } })

  expect(screen.queryByText(/Queued Anchor Results/i)).not.toBeInTheDocument()

  await act(async () => {
    deferredQueue.resolve({
      lane: 'adult_nsfw',
      requested_shot_count: 4,
      queued_generation_count: 8,
      queued_shots: [
        { shot_no: 1, generation_ids: ['gen-1a', 'gen-1b'] },
        { shot_no: 2, generation_ids: ['gen-2a', 'gen-2b'] },
        { shot_no: 3, generation_ids: ['gen-3a', 'gen-3b'] },
        { shot_no: 4, generation_ids: ['gen-4a', 'gen-4b'] },
      ],
      queued_generations: [
        buildGenerationResponse('gen-1a'),
        buildGenerationResponse('gen-1b'),
        buildGenerationResponse('gen-2a'),
        buildGenerationResponse('gen-2b'),
        buildGenerationResponse('gen-3a'),
        buildGenerationResponse('gen-3b'),
        buildGenerationResponse('gen-4a'),
        buildGenerationResponse('gen-4b'),
      ],
    })
    await Promise.resolve()
  })

  expect(screen.queryByText(/Queued Anchor Results/i)).not.toBeInTheDocument()
})
