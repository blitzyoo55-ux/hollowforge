import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useEffect, type ReactElement } from 'react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import {
  assembleComicEpisodePages,
  exportComicEpisodePages,
  generateComicPanelDialogues,
  getComicEpisode,
  getComicCharacterVersions,
  getComicCharacters,
  getComicPanelRenderJobs,
  getProductionEpisode,
  importComicStoryPlan,
  launchAnimationPreset,
  listComicEpisodes,
  queueComicPanelRenders,
  reconcileStaleAnimationJobs,
  selectComicPanelRenderAsset,
} from '../api/client'
import * as apiClient from '../api/client'
import type {
  AnimationCurrentShotResponse,
  ComicPageAssemblyBatchResponse,
  ComicPageExportResponse,
  ComicRenderJobResponse,
  StoryPlannerPlanResponse,
  ComicCharacterVersionResponse,
  ComicEpisodeDetailResponse,
  ProductionEpisodeDetailResponse,
  AnimationShotVariantResponse,
} from '../api/client'
import ComicStudio from './ComicStudio'

vi.mock('../api/client', () => ({
  getComicCharacters: vi.fn().mockResolvedValue([]),
  getComicCharacterVersions: vi.fn().mockResolvedValue([]),
  getComicEpisode: vi.fn(),
  listComicEpisodes: vi.fn().mockResolvedValue([]),
  getProductionEpisode: vi.fn(),
  getComicPanelRenderJobs: vi.fn().mockResolvedValue([]),
  importComicStoryPlan: vi.fn(),
  getCurrentAnimationShot: vi.fn().mockResolvedValue(null),
  launchAnimationPreset: vi.fn(),
  queueComicPanelRenders: vi.fn(),
  reconcileStaleAnimationJobs: vi.fn(),
  selectComicPanelRenderAsset: vi.fn(),
  generateComicPanelDialogues: vi.fn(),
  assembleComicEpisodePages: vi.fn(),
  exportComicEpisodePages: vi.fn(),
}))

vi.mock('../lib/toast', () => ({
  notify: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function renderWithProviders(ui: ReactElement, initialPath = '/comic') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

function ComicStudioRouteDriver({ path }: { path: string }) {
  const navigate = useNavigate()

  useEffect(() => {
    navigate(path)
  }, [navigate, path])

  return <ComicStudio />
}

function renderWithRouteControl(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  const renderAtPath = (path: string) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/comic']}>
        <ComicStudioRouteDriver path={path} />
      </MemoryRouter>
    </QueryClientProvider>
  )

  const view = render(renderAtPath(initialPath))
  return {
    ...view,
    setPath: (path: string) => view.rerender(renderAtPath(path)),
  }
}

function buildEpisodeDetail(
  panelCount = 1,
  panelRemoteJobCounts: Record<string, { remote: number; pending: number }> = {},
): ComicEpisodeDetailResponse {
  return {
    episode: {
      id: 'ep-1',
      character_id: 'char-1',
      character_version_id: 'charver-1',
      title: 'After Hours Intake',
      synopsis: 'A restrained corridor sequence.',
      source_story_plan_json: '{"plan":"ok"}',
      status: 'planned',
      continuity_summary: null,
      canon_delta: null,
      target_output: 'oneshot_manga',
      created_at: '2026-04-04T00:00:00+00:00',
      updated_at: '2026-04-04T00:00:00+00:00',
    },
    scenes: [
      {
        scene: {
          id: 'scene-1',
          episode_id: 'ep-1',
          scene_no: 1,
          premise: 'Containment corridor intake.',
          location_label: 'Corridor',
          tension: null,
          reveal: null,
          continuity_notes: null,
          involved_character_ids: ['char-1'],
          target_panel_count: 1,
          created_at: '2026-04-04T00:00:00+00:00',
          updated_at: '2026-04-04T00:00:00+00:00',
        },
        panels: Array.from({ length: panelCount }, (_, index) => {
          const panelId = `panel-${index + 1}`
          const remoteJobCounts = panelRemoteJobCounts[panelId] ?? { remote: 0, pending: 0 }
          return {
          id: panelId,
          episode_scene_id: 'scene-1',
          panel_no: index + 1,
          panel_type: 'beat',
          framing: index === 0 ? 'Waist-up with hard sidelight.' : 'Wide corridor cutaway.',
          camera_intent: index === 0 ? 'Medium close-up' : 'Wide shot',
          action_intent: index === 0
            ? 'The subject steadies against the wall.'
            : 'The handler watches from the corridor bend.',
          expression_intent: index === 0 ? 'Composed restraint.' : 'Measured concern.',
          dialogue_intent: index === 0
            ? 'One short command and a metallic SFX hit.'
            : 'A quiet reaction beat.',
          continuity_lock: null,
          page_target_hint: 1,
          reading_order: index + 1,
          remote_job_count: remoteJobCounts.remote,
          pending_remote_job_count: remoteJobCounts.pending,
          created_at: '2026-04-04T00:00:00+00:00',
          updated_at: '2026-04-04T00:00:00+00:00',
          }
        }),
      },
    ],
    pages: [],
  }
}

function buildCharacterVersion(
  id: string,
  characterId: string,
  versionName: string,
): ComicCharacterVersionResponse {
  return {
    id,
    character_id: characterId,
    version_name: versionName,
    purpose: 'manga',
    checkpoint: 'waiIllustrious',
    workflow_lane: 'sdxl_illustrious',
    created_at: '2026-04-04T00:00:00+00:00',
    updated_at: '2026-04-04T00:00:00+00:00',
  }
}

function buildRenderAsset(
  panelId: string,
  assetId: string,
) {
  return {
    id: assetId,
    scene_panel_id: panelId,
    generation_id: `gen-${assetId}`,
    asset_role: 'candidate' as const,
    storage_path: `images/${panelId}-${assetId}.png`,
    prompt_snapshot: { lane: 'adult_nsfw' },
    quality_score: 0.93,
    bubble_safe_zones: [],
    crop_metadata: { crop_mode: 'fit' },
    render_notes: null,
    is_selected: false,
    created_at: '2026-04-04T00:00:00+00:00',
    updated_at: '2026-04-04T00:00:00+00:00',
  }
}

function buildQueueResponse(panelId: string, assetId = 'asset-1') {
  const panel = buildEpisodeDetail(panelId === 'panel-2' ? 2 : 1).scenes[0].panels.find((entry) => entry.id === panelId)
    ?? buildEpisodeDetail().scenes[0].panels[0]
  return {
    panel,
    execution_mode: 'local_preview' as const,
    requested_count: 3,
    queued_generation_count: 3,
    materialized_asset_count: 1,
    pending_render_job_count: 0,
    remote_job_count: 0,
    render_assets: [buildRenderAsset(panelId, assetId)],
  }
}

function buildRemoteQueueResponse(panelId: string) {
  const panel = buildEpisodeDetail(1, { [panelId]: { remote: 3, pending: 3 } }).scenes[0].panels.find((entry) => entry.id === panelId)
    ?? buildEpisodeDetail().scenes[0].panels[0]
  return {
    panel,
    execution_mode: 'remote_worker' as const,
    requested_count: 3,
    queued_generation_count: 3,
    materialized_asset_count: 0,
    pending_render_job_count: 3,
    remote_job_count: 3,
    render_assets: [
      {
        ...buildRenderAsset(panelId, 'asset-remote-1'),
        storage_path: null,
      },
    ],
  }
}

function buildRemoteRenderJobs(panelId: string): ComicRenderJobResponse[] {
  return [
    {
      id: 'job-remote-1',
      scene_panel_id: panelId,
      render_asset_id: 'asset-remote-3',
      generation_id: 'gen-asset-remote-3',
      request_index: 2,
      source_id: `comic-panel-render:${panelId}:3:remote_worker`,
      target_tool: 'comic_panel_still',
      executor_mode: 'remote_worker',
      executor_key: 'default',
      status: 'processing',
      request_json: null,
      external_job_id: 'worker-job-123',
      external_job_url: 'https://worker.test/jobs/worker-job-123',
      output_path: null,
      error_message: null,
      submitted_at: '2026-04-04T00:05:00+00:00',
      completed_at: null,
      created_at: '2026-04-04T00:04:00+00:00',
      updated_at: '2026-04-04T00:05:00+00:00',
    },
    {
      id: 'job-remote-2',
      scene_panel_id: panelId,
      render_asset_id: 'asset-remote-2',
      generation_id: 'gen-asset-remote-2',
      request_index: 1,
      source_id: `comic-panel-render:${panelId}:3:remote_worker`,
      target_tool: 'comic_panel_still',
      executor_mode: 'remote_worker',
      executor_key: 'default',
      status: 'failed',
      request_json: null,
      external_job_id: 'worker-job-456',
      external_job_url: 'https://worker.test/jobs/worker-job-456',
      output_path: null,
      error_message: 'ComfyUI timed out on prompt 2.',
      submitted_at: '2026-04-04T00:05:00+00:00',
      completed_at: '2026-04-04T00:06:00+00:00',
      created_at: '2026-04-04T00:04:30+00:00',
      updated_at: '2026-04-04T00:06:00+00:00',
    },
    {
      id: 'job-remote-0',
      scene_panel_id: panelId,
      render_asset_id: 'asset-remote-1',
      generation_id: 'gen-asset-remote-1',
      request_index: 0,
      source_id: `comic-panel-render:${panelId}:3:remote_worker`,
      target_tool: 'comic_panel_still',
      executor_mode: 'remote_worker',
      executor_key: 'default',
      status: 'failed',
      request_json: null,
      external_job_id: 'worker-job-111',
      external_job_url: 'https://worker.test/jobs/worker-job-111',
      output_path: null,
      error_message: 'ComfyUI rejected prompt 1.',
      submitted_at: '2026-04-04T00:04:45+00:00',
      completed_at: '2026-04-04T00:05:30+00:00',
      created_at: '2026-04-04T00:04:00+00:00',
      updated_at: '2026-04-04T00:05:30+00:00',
    },
  ]
}

function buildCurrentAnimationShot(): AnimationCurrentShotResponse {
  const variants: AnimationShotVariantResponse[] = [
    {
      id: 'variant-success',
      animation_shot_id: 'shot-1',
      animation_job_id: 'anim-job-success',
      preset_id: 'sdxl_ipadapter_microanim_v2',
      launch_reason: 'rerun',
      status: 'completed',
      output_path: 'outputs/example.mp4',
      error_message: null,
      created_at: '2026-04-04T00:12:00+00:00',
      completed_at: '2026-04-04T00:13:00+00:00',
    },
    {
      id: 'variant-failed',
      animation_shot_id: 'shot-1',
      animation_job_id: 'anim-job-failed',
      preset_id: 'sdxl_ipadapter_microanim_v2',
      launch_reason: 'rerun',
      status: 'failed',
      output_path: null,
      error_message: 'Worker restarted',
      created_at: '2026-04-04T00:08:30+00:00',
      completed_at: '2026-04-04T00:08:45+00:00',
    },
  ]

  return {
    shot: {
      id: 'shot-1',
      source_kind: 'comic_selected_render',
      episode_id: 'ep-1',
      scene_panel_id: 'panel-1',
      selected_render_asset_id: 'asset-1',
      generation_id: 'gen-asset-1',
      is_current: true,
      created_at: '2026-04-04T00:09:00+00:00',
      updated_at: '2026-04-04T00:13:00+00:00',
    },
    variants,
  }
}

function buildApprovedPlanPayload(): StoryPlannerPlanResponse {
  return {
    story_prompt: 'After-hours intake in a secure corridor.',
    lane: 'adult_nsfw',
    policy_pack_id: 'adult_nsfw_single_location_v1',
    approval_token: 'a'.repeat(64),
    anchor_render: {
      policy_pack_id: 'adult_nsfw_single_location_v1',
      checkpoint: 'waiIllustrious',
      workflow_lane: 'sdxl_illustrious',
      negative_prompt: null,
      preserve_blank_negative_prompt: false,
    },
    resolved_cast: [
      {
        role: 'lead',
        source_type: 'registry',
        character_id: 'char-1',
        character_name: 'Kaede Ren',
        freeform_description: null,
        canonical_anchor: 'Black bob, measured gaze, controlled body language.',
        anti_drift: 'Preserve facial proportions and corridor costume silhouette.',
        wardrobe_notes: 'Dark intake uniform.',
        personality_notes: 'Restrained and observant.',
        resolution_note: 'Matched registry lead.',
      },
    ],
    location: {
      id: 'corridor-lab',
      name: 'Containment Corridor',
      setting_anchor: 'Sterile after-hours corridor with hard sidelight.',
      visual_rules: ['Keep the same corridor geometry across shots.'],
      restricted_elements: [],
      match_note: 'Matched against corridor keywords.',
    },
    episode_brief: {
      premise: 'Kaede holds composure during a late-night intake.',
      continuity_guidance: ['Keep the corridor lighting and wardrobe stable.'],
    },
    shots: [
      {
        shot_no: 1,
        beat: 'Establish the corridor.',
        camera: 'Wide corridor establishing shot.',
        action: 'The intake corridor hums before the subject enters frame.',
        emotion: 'Controlled tension.',
        continuity_note: 'Lock corridor geometry and sidelight placement.',
      },
      {
        shot_no: 2,
        beat: 'Hold on Kaede.',
        camera: 'Medium close-up.',
        action: 'Kaede steadies against the wall.',
        emotion: 'Composed restraint.',
        continuity_note: 'Keep facial proportions and uniform silhouette stable.',
      },
      {
        shot_no: 3,
        beat: 'Reaction from the handler.',
        camera: 'Three-quarter medium shot.',
        action: 'The handler watches from the corridor bend.',
        emotion: 'Measured concern.',
        continuity_note: 'Maintain corridor continuity and screen direction.',
      },
      {
        shot_no: 4,
        beat: 'Return to Kaede.',
        camera: 'Tight close-up.',
        action: 'Kaede gives a short command.',
        emotion: 'Cold focus.',
        continuity_note: 'Hold the same sidelight and costume details.',
      },
    ],
  }
}

function fillApprovedPlanJson() {
  fireEvent.change(screen.getByLabelText(/Approved Story Plan JSON/i), {
    target: { value: JSON.stringify(buildApprovedPlanPayload(), null, 2) },
  })
}

async function importEpisodeAndPrepareSelectedRender() {
  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeEnabled()
  })

  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))
  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))
  await waitFor(() => expect(queueComicPanelRenders).toHaveBeenCalled())
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Queue Local Preview/i })).toBeEnabled()
  })

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))
  await waitFor(() => expect(selectComicPanelRenderAsset).toHaveBeenCalled())
}

function buildProductionEpisode(
  overrides: Partial<ProductionEpisodeDetailResponse> = {},
): ProductionEpisodeDetailResponse {
  return {
    id: 'prod-ep-1',
    work_id: 'work_demo',
    series_id: 'series_demo',
    title: 'Production Intake Episode',
    synopsis: 'Production episode synopsis.',
    content_mode: 'adult_nsfw',
    target_outputs: ['comic'],
    continuity_summary: null,
    status: 'draft',
    comic_track: null,
    animation_track: null,
    comic_track_count: 0,
    animation_track_count: 0,
    created_at: '2026-04-11T10:00:00Z',
    updated_at: '2026-04-11T10:00:00Z',
    ...overrides,
  }
}

function buildHandoffValidation(overrides?: {
  hard_blocks?: Array<{ code: string; message: string; page_id?: string }>
  soft_warnings?: Array<{ code: string; message: string; page_id?: string }>
}) {
  return {
    episode_id: 'ep-1',
    hard_blocks: overrides?.hard_blocks ?? [],
    soft_warnings: overrides?.soft_warnings ?? [],
    page_summaries: [
      {
        page_id: 'page-1',
        page_no: 1,
        art_layer_status: 'complete' as const,
        frame_layer_status: 'complete' as const,
        balloon_layer_status: 'complete' as const,
        text_draft_layer_status: 'complete' as const,
        hard_block_count: overrides?.hard_blocks?.length ?? 0,
        soft_warning_count: overrides?.soft_warnings?.length ?? 0,
      },
    ],
    generated_at: '2026-04-04T00:10:00+00:00',
  }
}

function buildAssembleResponse(
  overrides: Partial<ComicPageAssemblyBatchResponse> = {},
): ComicPageAssemblyBatchResponse {
  const handoffValidation = buildHandoffValidation()

  return {
    episode_id: 'ep-1',
    layout_template_id: 'jp_2x2_v1',
    manuscript_profile: {
      id: 'jp_manga_rightbound_v1',
      label: 'Japanese Manga Right-Bound v1',
      binding_direction: 'right_to_left',
      finishing_tool: 'clip_studio_ex',
      print_intent: 'japanese_manga',
      trim_reference: 'B5 monochrome manga manuscript preset',
      bleed_reference: 'CLIP STUDIO EX Japanese comic print bleed preset',
      safe_area_reference: 'CLIP STUDIO EX default inner safe area guide',
      naming_pattern: 'page_{page_no:03d}.tif',
    },
    pages: [
      {
        id: 'page-1',
        episode_id: 'ep-1',
        page_no: 1,
        layout_template_id: 'jp_2x2_v1',
        ordered_panel_ids: ['panel-1'],
        export_state: 'preview_ready',
        preview_path: 'comics/previews/page_01.png',
        master_path: null,
        export_manifest: { page_no: 1 },
        created_at: '2026-04-04T00:00:00+00:00',
        updated_at: '2026-04-04T00:00:00+00:00',
      },
    ],
    export_manifest_path: 'comics/manifests/pages.json',
    dialogue_json_path: 'comics/manifests/dialogues.json',
    panel_asset_manifest_path: 'comics/manifests/panel_assets.json',
    page_assembly_manifest_path: 'comics/manifests/pages.json',
    manuscript_profile_manifest_path: 'comics/manifests/manuscript_profile.json',
    handoff_readme_path: 'comics/handoff/readme.md',
    production_checklist_path: 'comics/handoff/production_checklist.md',
    teaser_handoff_manifest_path: 'comics/manifests/teaser_handoff.json',
    layered_manifest_path: 'comics/handoff/layered/manifest.json',
    handoff_validation_path: 'comics/handoff/layered/handoff_validation.json',
    handoff_validation: handoffValidation,
    page_summaries: handoffValidation.page_summaries,
    latest_export_summary: null,
    ...overrides,
  }
}

function buildExportResponse(
  overrides: Partial<ComicPageExportResponse> = {},
): ComicPageExportResponse {
  const handoffValidation = buildHandoffValidation()

  return {
    ...buildAssembleResponse({
      pages: [
        {
          id: 'page-1',
          episode_id: 'ep-1',
          page_no: 1,
          layout_template_id: 'jp_2x2_v1',
          ordered_panel_ids: ['panel-1'],
          export_state: 'exported',
          preview_path: 'comics/previews/page_01.png',
          master_path: null,
          export_manifest: { page_no: 1 },
          created_at: '2026-04-04T00:00:00+00:00',
          updated_at: '2026-04-04T00:00:00+00:00',
        },
      ],
      handoff_validation: handoffValidation,
      page_summaries: handoffValidation.page_summaries,
    }),
    export_zip_path: 'comics/exports/handoff.zip',
    latest_export_summary: {
      export_zip_path: 'comics/exports/handoff.zip',
      layered_manifest_path: 'comics/handoff/layered/manifest.json',
      handoff_validation_path: 'comics/handoff/layered/handoff_validation.json',
      page_count: 1,
      hard_block_count: 0,
      soft_warning_count: 0,
      exported_at: '2026-04-04T00:12:00+00:00',
    },
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(getComicCharacters).mockResolvedValue([
    {
      id: 'char-1',
      slug: 'kaede',
      name: 'Kaede Ren',
      status: 'active',
      tier: 'hero',
      created_at: '2026-04-04T00:00:00+00:00',
      updated_at: '2026-04-04T00:00:00+00:00',
    },
    {
      id: 'char-2',
      slug: 'mika',
      name: 'Mika Soryu',
      status: 'active',
      tier: 'support',
      created_at: '2026-04-04T00:00:00+00:00',
      updated_at: '2026-04-04T00:00:00+00:00',
    },
  ])
  vi.mocked(getComicCharacterVersions).mockImplementation(async (characterId?: string | null) => {
    if (characterId === 'char-2') {
      return [buildCharacterVersion('charver-2', 'char-2', 'Alt v2')]
    }
    return [buildCharacterVersion('charver-1', 'char-1', 'Still v1')]
  })
  vi.mocked(importComicStoryPlan).mockResolvedValue(buildEpisodeDetail())
  vi.mocked(getComicEpisode).mockResolvedValue(buildEpisodeDetail())
  vi.mocked(listComicEpisodes).mockResolvedValue([])
  vi.mocked(getProductionEpisode).mockResolvedValue(buildProductionEpisode())
  vi.mocked(apiClient.getCurrentAnimationShot).mockResolvedValue(buildCurrentAnimationShot())
  vi.mocked(launchAnimationPreset).mockResolvedValue({
    preset: {
      id: 'sdxl_ipadapter_microanim_v2',
      name: 'Micro Animation v2',
      description: 'Identity-first teaser preset.',
      target_tool: 'seedance',
      backend_family: 'sdxl_ipadapter',
      model_profile: 'microanim_v2',
      request_json: {},
    },
    animation_job: {
      id: 'anim-job-new',
      candidate_id: null,
      generation_id: 'gen-asset-1',
      publish_job_id: null,
      target_tool: 'seedance',
      executor_mode: 'remote_worker',
      executor_key: 'default',
      status: 'submitted',
      request_json: {},
      external_job_id: 'worker-animation-new',
      external_job_url: 'https://worker.test/jobs/worker-animation-new',
      output_path: null,
      error_message: null,
      submitted_at: '2026-04-04T00:13:00+00:00',
      completed_at: null,
      created_at: '2026-04-04T00:13:00+00:00',
      updated_at: '2026-04-04T00:13:00+00:00',
    },
    dispatch: null,
    dispatch_error: null,
    animation_shot_id: 'shot-new',
    animation_shot_variant_id: 'variant-new',
  })
  vi.mocked(queueComicPanelRenders).mockImplementation(async (panelId: string) => buildQueueResponse(panelId))
  vi.mocked(reconcileStaleAnimationJobs).mockResolvedValue({
    checked: 1,
    updated: 1,
    failed_restart: 1,
    completed: 0,
    cancelled: 0,
    skipped_unreachable: 0,
  })
  vi.mocked(getComicPanelRenderJobs).mockResolvedValue([])
  vi.mocked(selectComicPanelRenderAsset).mockImplementation(async (panelId: string, assetId: string) => ({
    ...buildRenderAsset(panelId, assetId),
    asset_role: 'selected',
    is_selected: true,
  }))
  vi.mocked(generateComicPanelDialogues).mockResolvedValue({
    panel: buildEpisodeDetail().scenes[0].panels[0],
    dialogues: [
      {
        id: 'dialogue-1',
        scene_panel_id: 'panel-1',
        type: 'speech',
        speaker_character_id: 'char-1',
        text: 'Hold still.',
        tone: 'controlled',
        priority: 1,
        balloon_style_hint: 'tight',
        placement_hint: 'upper-right',
        created_at: '2026-04-04T00:00:00+00:00',
        updated_at: '2026-04-04T00:00:00+00:00',
      },
    ],
    generated_count: 1,
    overwrite_existing: false,
    prompt_provider_profile_id: 'adult_local_llm',
  })
  vi.mocked(assembleComicEpisodePages).mockResolvedValue(buildAssembleResponse())
  vi.mocked(exportComicEpisodePages).mockResolvedValue(buildExportResponse())
})

afterEach(() => {
  vi.useRealTimers()
})

test('shows selected state only after explicit asset selection without blocking draft actions', async () => {
  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()
  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeEnabled()
  })

  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  await waitFor(() => {
    expect(importComicStoryPlan).toHaveBeenCalledTimes(1)
  })

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()
  expect(screen.getAllByText(/Kaede Ren/i).length).toBeGreaterThan(0)
  expect(screen.getByRole('button', { name: /Generate Dialogues/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Queue Local Preview/i })).toBeEnabled()
  })

  expect(await screen.findByText(/No render has been selected yet\./i)).toBeInTheDocument()
  expect(screen.getAllByText(/images\/panel-1-asset-1\.png/i)).toHaveLength(1)
  expect(screen.getByRole('button', { name: /Generate Dialogues/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /Export Handoff ZIP/i })).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))

  await waitFor(() => {
    expect(selectComicPanelRenderAsset).toHaveBeenCalledWith('panel-1', 'asset-1')
  })

  await waitFor(() => {
    expect(screen.queryByText(/No render has been selected yet\./i)).not.toBeInTheDocument()
    expect(screen.getAllByText(/images\/panel-1-asset-1\.png/i).length).toBeGreaterThanOrEqual(3)
  })
  expect(screen.getByRole('button', { name: /Generate Dialogues/i })).toBeEnabled()
  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeEnabled()
  expect(screen.getByRole('button', { name: /Export Handoff ZIP/i })).toBeDisabled()
})

test('create_from_production shows linked intake context, prefill title, and forwards production linkage on import', async () => {
  vi.mocked(getProductionEpisode).mockResolvedValue(
    buildProductionEpisode({
      id: 'prod-ep-1',
      work_id: 'work_alpha',
      series_id: 'series_alpha',
      title: 'Production Episode One',
      content_mode: 'adult_nsfw',
    }),
  )

  renderWithProviders(<ComicStudio />, '/comic?production_episode_id=prod-ep-1&mode=create_from_production')

  const productionContextHeader = await screen.findByText(/^Production Episode Context$/i)
  const productionContextCard = productionContextHeader.closest('div')
  expect(productionContextCard).toBeTruthy()
  expect(productionContextCard).toHaveTextContent(/Production Episode:\s*prod-ep-1/i)
  expect(productionContextCard).toHaveTextContent(/Work:\s*work_alpha/i)
  expect(productionContextCard).toHaveTextContent(/Series:\s*series_alpha/i)
  await waitFor(() => {
    expect(screen.getByLabelText(/Episode Title/i)).toHaveValue('Production Episode One')
  })

  fillApprovedPlanJson()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeEnabled()
  })
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  await waitFor(() => {
    expect(importComicStoryPlan).toHaveBeenCalledWith(
      expect.objectContaining({
        work_id: 'work_alpha',
        series_id: 'series_alpha',
        production_episode_id: 'prod-ep-1',
        title: 'Production Episode One',
      }),
    )
  })
})

test('create_from_production blocks import while production episode context is unresolved', async () => {
  vi.mocked(getProductionEpisode).mockImplementation(() => new Promise(() => {}))

  renderWithProviders(<ComicStudio />, '/comic?production_episode_id=prod-ep-1&mode=create_from_production')

  fillApprovedPlanJson()
  const importButton = screen.getByRole('button', { name: /Import Story Plan/i })
  expect(importButton).toBeDisabled()
  expect(
    screen.getByText(/Checking linked comic episodes for this production episode before import/i),
  ).toBeInTheDocument()

  fireEvent.click(importButton)
  expect(importComicStoryPlan).not.toHaveBeenCalled()
})

test('create_from_production blocks duplicate import when linked episodes already exist and shows manual-open fallback', async () => {
  vi.mocked(getProductionEpisode).mockResolvedValue(
    buildProductionEpisode({
      id: 'prod-ep-dup',
      work_id: 'work_dup',
      series_id: 'series_dup',
      title: 'Duplicate Episode',
      content_mode: 'adult_nsfw',
    }),
  )
  vi.mocked(listComicEpisodes).mockImplementation(async (params) => {
    const productionEpisodeId = (params as { production_episode_id?: string } | undefined)?.production_episode_id
    if (productionEpisodeId === 'prod-ep-dup') {
      return [
        {
          episode: {
            ...buildEpisodeDetail().episode,
            id: 'ep-linked-dup-1',
            title: 'Existing Linked Episode',
          },
          scene_count: 1,
          page_count: 0,
        },
      ]
    }
    return []
  })
  vi.mocked(getComicEpisode).mockResolvedValue({
    ...buildEpisodeDetail(),
    episode: {
      ...buildEpisodeDetail().episode,
      id: 'ep-linked-dup-1',
      title: 'Existing Linked Episode',
    },
  })

  renderWithProviders(<ComicStudio />, '/comic?production_episode_id=prod-ep-dup&mode=create_from_production')

  fillApprovedPlanJson()
  expect(await screen.findByRole('heading', { name: /Duplicate Import Blocked/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Open Existing Linked Episode/i })).toBeInTheDocument()

  const importButton = screen.getByRole('button', { name: /Import Story Plan/i })
  expect(importButton).toBeDisabled()
  fireEvent.click(importButton)
  expect(importComicStoryPlan).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: /Open Existing Linked Episode/i }))
  await waitFor(() => {
    expect(getComicEpisode).toHaveBeenCalledWith('ep-linked-dup-1')
  })
})

test('open_current auto-loads the single linked comic episode detail', async () => {
  vi.mocked(listComicEpisodes).mockResolvedValue([
    {
      episode: {
        ...buildEpisodeDetail().episode,
        id: 'ep-linked-1',
      },
      scene_count: 1,
      page_count: 0,
    },
  ])
  vi.mocked(getComicEpisode).mockResolvedValue({
    ...buildEpisodeDetail(),
    episode: {
      ...buildEpisodeDetail().episode,
      id: 'ep-linked-1',
      title: 'Linked Imported Episode',
    },
  })

  renderWithProviders(<ComicStudio />, '/comic?production_episode_id=prod-ep-1&mode=open_current')

  await waitFor(() => {
    expect(listComicEpisodes).toHaveBeenCalledWith({ production_episode_id: 'prod-ep-1' })
  })
  await waitFor(() => {
    expect(getComicEpisode).toHaveBeenCalledWith('ep-linked-1')
  })
  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()
  expect(screen.getAllByText(/Linked Imported Episode/i).length).toBeGreaterThan(0)
})

test('open_current ambiguous linked episodes shows manual fallback and does not auto-open', async () => {
  vi.mocked(listComicEpisodes).mockResolvedValue([
    {
      episode: {
        ...buildEpisodeDetail().episode,
        id: 'ep-linked-1',
        title: 'Linked Episode A',
      },
      scene_count: 1,
      page_count: 0,
    },
    {
      episode: {
        ...buildEpisodeDetail().episode,
        id: 'ep-linked-2',
        title: 'Linked Episode B',
      },
      scene_count: 2,
      page_count: 0,
    },
  ])
  vi.mocked(getComicEpisode).mockResolvedValue({
    ...buildEpisodeDetail(),
    episode: {
      ...buildEpisodeDetail().episode,
      id: 'ep-linked-2',
      title: 'Linked Episode B',
    },
  })

  renderWithProviders(<ComicStudio />, '/comic?production_episode_id=prod-ep-1&mode=open_current')

  expect(await screen.findByText(/Multiple comic episodes are linked/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Open Linked Episode A/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Open Linked Episode B/i })).toBeInTheDocument()
  expect(getComicEpisode).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: /Open Linked Episode B/i }))
  await waitFor(() => {
    expect(getComicEpisode).toHaveBeenCalledWith('ep-linked-2')
  })
  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()
  expect(screen.getAllByText(/Linked Episode B/i).length).toBeGreaterThan(0)
})

test('route transition into ambiguous open_current clears stale episode view and shows manual-open fallback', async () => {
  vi.mocked(listComicEpisodes).mockImplementation(async (params) => {
    const productionEpisodeId = (params as { production_episode_id?: string } | undefined)?.production_episode_id
    if (productionEpisodeId === 'prod-ep-single') {
      return [
        {
          episode: {
            ...buildEpisodeDetail().episode,
            id: 'ep-linked-single',
            title: 'Linked Episode Single',
          },
          scene_count: 1,
          page_count: 0,
        },
      ]
    }
    if (productionEpisodeId === 'prod-ep-ambiguous') {
      return [
        {
          episode: {
            ...buildEpisodeDetail().episode,
            id: 'ep-linked-ambig-1',
            title: 'Linked Episode A',
          },
          scene_count: 1,
          page_count: 0,
        },
        {
          episode: {
            ...buildEpisodeDetail().episode,
            id: 'ep-linked-ambig-2',
            title: 'Linked Episode B',
          },
          scene_count: 2,
          page_count: 0,
        },
      ]
    }
    return []
  })
  vi.mocked(getComicEpisode).mockResolvedValue({
    ...buildEpisodeDetail(),
    episode: {
      ...buildEpisodeDetail().episode,
      id: 'ep-linked-single',
      title: 'Linked Episode Single',
    },
  })

  const view = renderWithRouteControl('/comic?production_episode_id=prod-ep-single&mode=open_current')

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()
  expect(screen.getAllByText(/Linked Episode Single/i).length).toBeGreaterThan(0)

  view.setPath('/comic?production_episode_id=prod-ep-ambiguous&mode=open_current')

  expect(await screen.findByText(/Multiple comic episodes are linked/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Open Linked Episode A/i })).toBeInTheDocument()
  expect(screen.queryByText(/Linked Episode Single/i)).not.toBeInTheDocument()
  expect(getComicEpisode).toHaveBeenCalledTimes(1)
})

test('route transition out of create_from_production clears stale linkage before plain import', async () => {
  vi.mocked(getProductionEpisode).mockResolvedValue(
    buildProductionEpisode({
      id: 'prod-ep-transition',
      work_id: 'work_transition',
      series_id: 'series_transition',
      title: 'Transition Episode',
      content_mode: 'adult_nsfw',
    }),
  )

  const view = renderWithRouteControl('/comic?production_episode_id=prod-ep-transition&mode=create_from_production')

  expect(await screen.findByText(/Production Episode Context/i)).toBeInTheDocument()
  await waitFor(() => {
    expect(screen.getByLabelText(/Episode Title/i)).toHaveValue('Transition Episode')
  })

  view.setPath('/comic')
  await waitFor(() => {
    expect(screen.queryByText(/Production Episode Context/i)).not.toBeInTheDocument()
  })

  fillApprovedPlanJson()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeEnabled()
  })
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  await waitFor(() => {
    expect(importComicStoryPlan).toHaveBeenCalledWith(expect.objectContaining({
      work_id: null,
      series_id: null,
      production_episode_id: null,
    }))
  })
})

test('teaser ops renders current shot and recent variants for the selected render', async () => {
  vi.mocked(apiClient.getCurrentAnimationShot).mockResolvedValue(buildCurrentAnimationShot())

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))
  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))
  await waitFor(() => {
    expect(selectComicPanelRenderAsset).toHaveBeenCalledWith('panel-1', 'asset-1')
  })

  await waitFor(() => {
    expect(apiClient.getCurrentAnimationShot).toHaveBeenCalledWith({
      scene_panel_id: 'panel-1',
      selected_render_asset_id: 'asset-1',
      limit: 8,
    })
  })

  expect(await screen.findByText(/Comic Handoff Workspace/i)).toBeInTheDocument()
  expect(await screen.findAllByText(/Animation Track Preview/i)).not.toHaveLength(0)
  expect(screen.getByText(/Current Teaser Shot/i)).toBeInTheDocument()
  expect(screen.getByText(/shot-1/i)).toBeInTheDocument()
  expect(screen.getByText(/Recent Variants For Selected Render/i)).toBeInTheDocument()
  expect(screen.getAllByText(/Worker restarted/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/sdxl_ipadapter_microanim_v2/i).length).toBeGreaterThan(0)
  expect(screen.getByRole('link', { name: /Open Latest MP4/i })).toHaveAttribute(
    'href',
    '/data/outputs/example.mp4',
  )
  expect(screen.getAllByRole('link', { name: /Open Output MP4/i })).toHaveLength(1)
})

test('teaser rerun action is disabled without a materialized selected asset', async () => {
  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()
  expect(await screen.findByText(/No current animation preview yet/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Rerun Animation Preview From Selected Panel/i })).toBeDisabled()
})

test('teaser ops reconcile action calls animation reconcile endpoint', async () => {
  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))
  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))
  await waitFor(() => {
    expect(selectComicPanelRenderAsset).toHaveBeenCalledWith('panel-1', 'asset-1')
  })

  await waitFor(() => {
    expect(apiClient.getCurrentAnimationShot).toHaveBeenCalledTimes(1)
  })

  fireEvent.click(screen.getByRole('button', { name: /Reconcile Stale Animation Jobs/i }))

  await waitFor(() => {
    expect(reconcileStaleAnimationJobs).toHaveBeenCalledTimes(1)
  })
  await waitFor(() => {
    expect(apiClient.getCurrentAnimationShot).toHaveBeenCalledTimes(2)
  })
})

test('teaser rerun action launches the default preset from the selected panel asset', async () => {
  vi.mocked(apiClient.getCurrentAnimationShot).mockResolvedValue(buildCurrentAnimationShot())

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))
  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))
  await waitFor(() => {
    expect(selectComicPanelRenderAsset).toHaveBeenCalledWith('panel-1', 'asset-1')
  })

  fireEvent.click(screen.getByRole('button', { name: /Rerun Animation Preview From Selected Panel/i }))

  await waitFor(() => {
    expect(launchAnimationPreset).toHaveBeenCalledWith('sdxl_ipadapter_microanim_v2', {
      generation_id: 'gen-asset-1',
      dispatch_immediately: true,
      request_overrides: {},
      episode_id: 'ep-1',
      scene_panel_id: 'panel-1',
      selected_render_asset_id: 'asset-1',
    })
  })
})

test('keeps assemble disabled until every panel has a selected render', async () => {
  vi.mocked(importComicStoryPlan).mockResolvedValue(buildEpisodeDetail(2))
  vi.mocked(queueComicPanelRenders).mockImplementation(async (panelId: string) => {
    if (panelId === 'panel-2') {
      return buildQueueResponse('panel-2', 'asset-2')
    }
    return buildQueueResponse('panel-1', 'asset-1')
  })

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeEnabled()
  })

  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()
  expect(screen.getAllByText(/Panel 2/i).length).toBeGreaterThan(0)
  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Queue Local Preview/i })).toBeEnabled()
  })

  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))

  await waitFor(() => {
    expect(selectComicPanelRenderAsset).toHaveBeenCalledWith('panel-1', 'asset-1')
  })

  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: /Panel 2/i }))
  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-2', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))

  await waitFor(() => {
    expect(selectComicPanelRenderAsset).toHaveBeenCalledWith('panel-2', 'asset-2')
  })

  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeEnabled()
})

test('keeps imported character version lineage when draft character selection changes', async () => {
  vi.mocked(getComicCharacterVersions)
    .mockReset()
    .mockImplementationOnce(async () => [buildCharacterVersion('charver-1', 'char-1', 'Still v1')])
    .mockImplementationOnce(async () => new Promise<ComicCharacterVersionResponse[]>(() => {}))
    .mockImplementation(async (characterId?: string | null) => {
      if (characterId === 'char-2') {
        return [buildCharacterVersion('charver-2', 'char-2', 'Alt v2')]
      }
      return [buildCharacterVersion('charver-1', 'char-1', 'Still v1')]
    })

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeEnabled()
  })

  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Panel Dialogue Editor/i })).toBeInTheDocument()
  expect(screen.getAllByText(/Still v1/i).length).toBeGreaterThan(0)

  fireEvent.change(screen.getByLabelText(/^Character$/i), { target: { value: 'char-2' } })

  await waitFor(() => {
    expect(getComicCharacterVersions).toHaveBeenCalledWith('char-2')
  })

  expect(screen.queryByText(/Unresolved version/i)).not.toBeInTheDocument()
  expect(screen.getAllByText(/Still v1/i).length).toBeGreaterThan(0)
})

test('imports a story plan and walks through render, selection, dialogue, and page assembly actions', async () => {
  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Import Story Plan/i })).toBeEnabled()
  })

  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  await waitFor(() => {
    expect(importComicStoryPlan).toHaveBeenCalledWith(expect.objectContaining({
      approved_plan: expect.objectContaining({
        approval_token: expect.any(String),
        location: expect.any(Object),
        shots: expect.arrayContaining([
          expect.objectContaining({ shot_no: 1 }),
          expect.objectContaining({ shot_no: 2 }),
          expect.objectContaining({ shot_no: 3 }),
          expect.objectContaining({ shot_no: 4 }),
        ]),
      }),
      character_version_id: 'charver-1',
      title: 'Comic Episode Draft',
      panel_multiplier: 2,
    }))
  })

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Generate Dialogues/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Queue Local Preview/i })).toBeEnabled()
  })

  expect(screen.getByRole('button', { name: /Generate Dialogues/i })).toBeDisabled()
  expect(screen.getByRole('button', { name: /Assemble Pages/i })).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))

  await waitFor(() => {
    expect(selectComicPanelRenderAsset).toHaveBeenCalledWith('panel-1', 'asset-1')
  })

  fireEvent.click(screen.getByRole('button', { name: /Generate Dialogues/i }))

  await waitFor(() => {
    expect(generateComicPanelDialogues).toHaveBeenCalledWith('panel-1')
  })

  expect(await screen.findByText(/Hold still\./i)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Assemble Pages/i }))

  await waitFor(() => {
    expect(assembleComicEpisodePages).toHaveBeenCalledWith('ep-1', 'jp_2x2_v1', 'jp_manga_rightbound_v1')
  })

  await waitFor(() => {
    expect(screen.getAllByText(/comics\/previews\/page_01\.png/i).length).toBeGreaterThan(0)
  })
  expect(screen.getByLabelText(/^Manuscript Profile$/i)).toHaveValue('jp_manga_rightbound_v1')
  expect(screen.getByText(/^Layout Template$/i)).toBeInTheDocument()
  expect(screen.getByText(/layout template = page composition/i)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Export Handoff ZIP/i }))

  await waitFor(() => {
    expect(exportComicEpisodePages).toHaveBeenCalledWith('ep-1', 'jp_2x2_v1', 'jp_manga_rightbound_v1')
  })

  expect(await screen.findByText(/comics\/exports\/handoff\.zip/i)).toBeInTheDocument()
  expect(screen.getAllByText(/comics\/handoff\/layered\/manifest\.json/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/comics\/handoff\/layered\/handoff_validation\.json/i).length).toBeGreaterThan(0)
})

test('queues remote production separately and surfaces selected-panel remote render status', async () => {
  vi.mocked(queueComicPanelRenders).mockResolvedValue(buildRemoteQueueResponse('panel-1'))
  vi.mocked(getComicPanelRenderJobs).mockResolvedValue(buildRemoteRenderJobs('panel-1'))

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Queue Remote Production/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'remote_worker',
    })
  })

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledWith('panel-1')
  })

  expect(await screen.findByText(/^Remote Production$/i)).toBeInTheDocument()
  expect(screen.getByText(/Pending Remote Jobs/i)).toBeInTheDocument()
  expect(screen.getByText(/Lane Remote Production · 1 pending/i)).toBeInTheDocument()
  expect(screen.getByText(/ComfyUI rejected prompt 1\./i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Open Remote Job/i })).toHaveAttribute(
    'href',
    'https://worker.test/jobs/worker-job-456',
  )
})

test('shows layered page readiness after assembly in Pages and Handoff workflow', async () => {
  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()
  await importEpisodeAndPrepareSelectedRender()
  fireEvent.click(screen.getByRole('button', { name: /Assemble Pages/i }))

  await waitFor(() => {
    expect(assembleComicEpisodePages).toHaveBeenCalledWith('ep-1', 'jp_2x2_v1', 'jp_manga_rightbound_v1')
  })

  expect(screen.getAllByText(/Assemble -> Handoff Review -> Export/i).length).toBeGreaterThan(0)
  expect(screen.getByRole('heading', { name: /Japanese Page Layout Handoff/i })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /^Handoff Review$/i })).toBeInTheDocument()
  expect(screen.getByText(/Frame layer complete/i)).toBeInTheDocument()
  expect(screen.getByText(/^Export Checklist$/i)).toBeInTheDocument()
  expect(screen.getByText(/Layered manifest present/i)).toBeInTheDocument()
  expect(screen.getByText(/Validation artifact present/i)).toBeInTheDocument()
  expect(screen.getByText(/Hard blocks clear/i)).toBeInTheDocument()
  expect(screen.getByText(/Page summaries ready for review\/export/i)).toBeInTheDocument()
  expect(screen.getAllByText(/Layered manifest/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/comics\/handoff\/layered\/manifest\.json/i).length).toBeGreaterThan(0)
})

test('blocks export in Handoff when validation has hard blocks', async () => {
  vi.mocked(assembleComicEpisodePages).mockResolvedValue(buildAssembleResponse({
    handoff_validation: buildHandoffValidation({
      hard_blocks: [{ code: 'missing-balloon', message: 'Balloon layer missing', page_id: 'page-1' }],
    }),
    page_summaries: [
      {
        page_id: 'page-1',
        page_no: 1,
        art_layer_status: 'complete',
        frame_layer_status: 'complete',
        balloon_layer_status: 'blocked',
        text_draft_layer_status: 'complete',
        hard_block_count: 1,
        soft_warning_count: 0,
      },
    ],
  }))

  renderWithProviders(<ComicStudio />)

  await importEpisodeAndPrepareSelectedRender()
  fireEvent.click(screen.getByRole('button', { name: /Assemble Pages/i }))
  await waitFor(() => expect(assembleComicEpisodePages).toHaveBeenCalled())

  const exportButton = screen.getByRole('button', { name: /Export Handoff ZIP/i })
  expect(exportButton).toBeDisabled()
  expect(screen.getAllByText(/1 hard block/i).length).toBeGreaterThan(0)
  expect(screen.getByText(/Hard blocks clear/i)).toBeInTheDocument()
  expect(screen.getAllByText(/^Blocked$/i).length).toBeGreaterThan(0)
  expect(exportComicEpisodePages).not.toHaveBeenCalled()
})

test('shows latest export summary with layered manifest and validation artifact paths', async () => {
  renderWithProviders(<ComicStudio />)

  await importEpisodeAndPrepareSelectedRender()
  fireEvent.click(screen.getByRole('button', { name: /Assemble Pages/i }))
  await waitFor(() => expect(assembleComicEpisodePages).toHaveBeenCalled())
  fireEvent.click(screen.getByRole('button', { name: /Export Handoff ZIP/i }))

  await waitFor(() => {
    expect(exportComicEpisodePages).toHaveBeenCalledWith('ep-1', 'jp_2x2_v1', 'jp_manga_rightbound_v1')
  })

  expect(await screen.findByText(/comics\/exports\/handoff\.zip/i)).toBeInTheDocument()
  expect(screen.getAllByText(/comics\/handoff\/layered\/manifest\.json/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/comics\/handoff\/layered\/handoff_validation\.json/i).length).toBeGreaterThan(0)
})

test('keeps previous successful export summary visible after a failed export', async () => {
  vi.mocked(exportComicEpisodePages)
    .mockResolvedValueOnce(buildExportResponse())
    .mockRejectedValueOnce(new Error('hard blocks prevent export'))

  renderWithProviders(<ComicStudio />)

  await importEpisodeAndPrepareSelectedRender()
  fireEvent.click(screen.getByRole('button', { name: /Assemble Pages/i }))
  await waitFor(() => expect(assembleComicEpisodePages).toHaveBeenCalled())

  const exportButton = screen.getByRole('button', { name: /Export Handoff ZIP/i })
  fireEvent.click(exportButton)
  expect(await screen.findByText(/comics\/exports\/handoff\.zip/i)).toBeInTheDocument()

  fireEvent.click(exportButton)

  await waitFor(() => {
    expect(exportComicEpisodePages).toHaveBeenCalledTimes(2)
  })
  expect(screen.getByText(/comics\/exports\/handoff\.zip/i)).toBeInTheDocument()
  expect(screen.getAllByText(/comics\/handoff\/layered\/manifest\.json/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/comics\/handoff\/layered\/handoff_validation\.json/i).length).toBeGreaterThan(0)
})

test('queueing remote production preserves an existing selected local asset', async () => {
  vi.mocked(queueComicPanelRenders).mockImplementation(async (_panelId: string, request) => {
    if (request.execution_mode === 'remote_worker') {
      return buildRemoteQueueResponse('panel-1')
    }
    return buildQueueResponse('panel-1', 'asset-local-1')
  })
  vi.mocked(selectComicPanelRenderAsset).mockImplementation(async (panelId: string, assetId: string) => ({
    ...buildRenderAsset(panelId, assetId),
    asset_role: 'selected',
    is_selected: true,
  }))
  vi.mocked(getComicPanelRenderJobs).mockResolvedValue(buildRemoteRenderJobs('panel-1'))

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })

  fireEvent.click(screen.getByRole('button', { name: /Mark Selected/i }))

  await waitFor(() => {
    expect(selectComicPanelRenderAsset).toHaveBeenCalledWith('panel-1', 'asset-local-1')
  })

  await waitFor(() => {
    expect(screen.getAllByText(/images\/panel-1-asset-local-1\.png/i).length).toBeGreaterThan(0)
  })
  expect(screen.getByRole('button', { name: /Generate Dialogues/i })).toBeEnabled()

  fireEvent.click(screen.getByRole('button', { name: /Queue Remote Production/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'remote_worker',
    })
  })

  await waitFor(() => {
    expect(screen.getAllByText(/images\/panel-1-asset-local-1\.png/i).length).toBeGreaterThan(0)
  })
  expect(screen.getByRole('button', { name: /Generate Dialogues/i })).toBeEnabled()
  expect(screen.getByRole('button', { name: /^Selected$/i })).toBeInTheDocument()
})

test('remote queue followed by local preview keeps remote status visible on the same panel', async () => {
  vi.mocked(queueComicPanelRenders).mockImplementation(async (_panelId: string, request) => {
    if (request.execution_mode === 'remote_worker') {
      return buildRemoteQueueResponse('panel-1')
    }
    return buildQueueResponse('panel-1', 'asset-local-2')
  })
  vi.mocked(getComicPanelRenderJobs).mockResolvedValue([])

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Queue Remote Production/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'remote_worker',
    })
  })

  expect(await screen.findByText(/^Remote Production$/i)).toBeInTheDocument()
  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledWith('panel-1')
  })

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })

  expect(screen.getAllByText(/^Local Preview$/i).length).toBeGreaterThan(0)
  expect(screen.getByText(/Pending Remote Jobs/i)).toBeInTheDocument()
  expect(screen.getAllByText(/^0$/i).length).toBeGreaterThan(0)
})

test('persisted remote outputs remain visible after switching away from the selected panel', async () => {
  vi.mocked(importComicStoryPlan).mockResolvedValue(
    buildEpisodeDetail(2, { 'panel-1': { remote: 1, pending: 0 } }),
  )
  vi.mocked(getComicPanelRenderJobs).mockResolvedValue([
    {
      ...buildRemoteRenderJobs('panel-1')[0],
      status: 'completed',
      output_path: 'images/panel-1-asset-remote-3.png',
      completed_at: '2026-04-04T00:07:00+00:00',
      updated_at: '2026-04-04T00:07:00+00:00',
      external_job_url: 'https://worker.test/jobs/worker-job-999',
    },
  ])

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledWith('panel-1')
  })

  fireEvent.click(screen.getByRole('button', { name: /Panel 2/i }))

  const panelOneCard = screen.getByRole('button', { name: /Panel 1/i })
  expect(within(panelOneCard).getByText(/Candidates 1 · Quality n\/a/i)).toBeInTheDocument()
  expect(within(panelOneCard).getByText(/Lane Remote Production · 0 pending/i)).toBeInTheDocument()
})

test('remote polling repeats while jobs are pending and stops after terminal results', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.mocked(importComicStoryPlan).mockResolvedValue(
    buildEpisodeDetail(1, { 'panel-1': { remote: 2, pending: 1 } }),
  )
  vi.mocked(getComicPanelRenderJobs)
    .mockResolvedValueOnce([
      {
        ...buildRemoteRenderJobs('panel-1')[0],
      },
    ])
    .mockResolvedValueOnce([
      {
        ...buildRemoteRenderJobs('panel-1')[0],
        status: 'completed',
        output_path: 'images/panel-1-asset-remote-3.png',
        completed_at: '2026-04-04T00:07:00+00:00',
        updated_at: '2026-04-04T00:07:00+00:00',
      },
    ])

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))
    await Promise.resolve()
  })

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(1)
    expect(getComicPanelRenderJobs).toHaveBeenCalledWith('panel-1')
  })

  await act(async () => {
    await vi.advanceTimersByTimeAsync(2100)
    await Promise.resolve()
  })

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(2)
  })

  await act(async () => {
    await vi.advanceTimersByTimeAsync(4000)
    await Promise.resolve()
  })

  expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(2)
}, 12000)

test('empty remote-job fetch does not clear persisted remote hints and polling continues until terminal jobs arrive', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  vi.mocked(importComicStoryPlan).mockResolvedValue(
    buildEpisodeDetail(1, { 'panel-1': { remote: 2, pending: 1 } }),
  )
  vi.mocked(getComicPanelRenderJobs)
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([
      {
        ...buildRemoteRenderJobs('panel-1')[0],
      },
    ])
    .mockResolvedValueOnce([
      {
        ...buildRemoteRenderJobs('panel-1')[0],
        status: 'completed',
        output_path: 'images/panel-1-asset-remote-3.png',
        completed_at: '2026-04-04T00:07:00+00:00',
        updated_at: '2026-04-04T00:07:00+00:00',
      },
    ])

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))
    await Promise.resolve()
  })

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(1)
  })

  expect(await screen.findByText(/^Remote Production$/i)).toBeInTheDocument()
  expect(screen.getByText(/Pending Remote Jobs/i)).toBeInTheDocument()
  expect(screen.getByText(/Lane Remote Production · 1 pending/i)).toBeInTheDocument()

  await act(async () => {
    await vi.advanceTimersByTimeAsync(2100)
    await Promise.resolve()
  })

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(2)
  })
  expect(screen.getByText(/Lane Remote Production · 1 pending/i)).toBeInTheDocument()

  await act(async () => {
    await vi.advanceTimersByTimeAsync(2100)
    await Promise.resolve()
  })

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(3)
  })

  await act(async () => {
    await vi.advanceTimersByTimeAsync(4000)
    await Promise.resolve()
  })

  expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(3)
}, 12000)

test('importing a new episode ignores late remote results from the previous episode', async () => {
  let resolveFirstEpisodeJobs: ((jobs: ComicRenderJobResponse[]) => void) | null = null
  const firstEpisodeJobs = new Promise<ComicRenderJobResponse[]>((resolve) => {
    resolveFirstEpisodeJobs = resolve
  })
  const secondEpisodeDetail = buildEpisodeDetail()
  secondEpisodeDetail.episode = {
    ...secondEpisodeDetail.episode,
    id: 'ep-2',
    title: 'Second Intake',
  }
  secondEpisodeDetail.scenes = secondEpisodeDetail.scenes.map((sceneDetail) => ({
    ...sceneDetail,
    scene: {
      ...sceneDetail.scene,
      id: 'scene-2',
      episode_id: 'ep-2',
      premise: 'Fresh import corridor beat.',
    },
    panels: sceneDetail.panels.map((panel) => ({
      ...panel,
      episode_scene_id: 'scene-2',
      framing: 'Fresh import frame.',
    })),
  }))

  vi.mocked(importComicStoryPlan)
    .mockResolvedValueOnce(buildEpisodeDetail(1, { 'panel-1': { remote: 1, pending: 1 } }))
    .mockResolvedValueOnce(secondEpisodeDetail)
  vi.mocked(getComicPanelRenderJobs).mockImplementationOnce(() => firstEpisodeJobs)

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))
  })

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(1)
    expect(getComicPanelRenderJobs).toHaveBeenCalledWith('panel-1')
  })

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))
  })

  expect(await screen.findByText(/Fresh import corridor beat\./i)).toBeInTheDocument()
  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledTimes(1)
  })

  await act(async () => {
    resolveFirstEpisodeJobs?.([
      {
        ...buildRemoteRenderJobs('panel-1')[0],
        status: 'completed',
        output_path: 'images/panel-1-asset-remote-stale.png',
        completed_at: '2026-04-04T00:07:00+00:00',
        updated_at: '2026-04-04T00:07:00+00:00',
      },
    ])
    await Promise.resolve()
  })

  const panelOneCard = screen.getByRole('button', { name: /Panel 1/i })
  await waitFor(() => {
    expect(within(panelOneCard).getByText(/Candidates 0 · Quality n\/a/i)).toBeInTheDocument()
    expect(within(panelOneCard).getByText(/Lane Local Preview/i)).toBeInTheDocument()
  })
  expect(screen.queryByText(/^Remote Production$/i)).not.toBeInTheDocument()
})

test('importing a new episode ignores late queue responses from the previous episode', async () => {
  let resolveFirstQueueResponse: ((response: ReturnType<typeof buildQueueResponse>) => void) | null = null
  const firstQueueResponse = new Promise<ReturnType<typeof buildQueueResponse>>((resolve) => {
    resolveFirstQueueResponse = resolve
  })
  const secondEpisodeDetail = buildEpisodeDetail(2)
  secondEpisodeDetail.episode = {
    ...secondEpisodeDetail.episode,
    id: 'ep-2',
    title: 'Queue Reset Intake',
  }
  secondEpisodeDetail.scenes = secondEpisodeDetail.scenes.map((sceneDetail) => ({
    ...sceneDetail,
    scene: {
      ...sceneDetail.scene,
      id: 'scene-queue-2',
      episode_id: 'ep-2',
      premise: 'Second queue import beat.',
    },
    panels: sceneDetail.panels.map((panel, index) => ({
      ...panel,
      id: `panel-b-${index + 1}`,
      episode_scene_id: 'scene-queue-2',
      framing: index === 0 ? 'Fresh queue import frame.' : 'Second queue focus frame.',
    })),
  }))

  vi.mocked(importComicStoryPlan)
    .mockResolvedValueOnce(buildEpisodeDetail())
    .mockResolvedValueOnce(secondEpisodeDetail)
  vi.mocked(queueComicPanelRenders).mockImplementationOnce(async () => firstQueueResponse)

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))
  })

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))
  })

  expect(await screen.findByText(/Second queue import beat\./i)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Panel 2/i }))
  expect(screen.getByText(/Current focus/i)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Panel 2/i })).toBeInTheDocument()
  const firstVisiblePanelCard = screen.getByRole('button', { name: /Panel 1/i })
  expect(within(firstVisiblePanelCard).getByText(/Candidates 0 · Quality n\/a/i)).toBeInTheDocument()
  expect(within(firstVisiblePanelCard).getByText(/Lane Local Preview/i)).toBeInTheDocument()

  await act(async () => {
    resolveFirstQueueResponse?.(buildQueueResponse('panel-1', 'asset-stale-1'))
    await Promise.resolve()
  })

  await waitFor(() => {
    expect(screen.getByRole('heading', { name: /Panel 2/i })).toBeInTheDocument()
    expect(within(firstVisiblePanelCard).getByText(/Candidates 0 · Quality n\/a/i)).toBeInTheDocument()
    expect(within(firstVisiblePanelCard).getByText(/Lane Local Preview/i)).toBeInTheDocument()
  })
  expect(screen.queryByText(/asset-stale-1/i)).not.toBeInTheDocument()
})

test('local-only panel flow does not fetch remote render jobs', async () => {
  vi.mocked(queueComicPanelRenders).mockResolvedValue(buildQueueResponse('panel-1'))

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))
  })

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(getComicPanelRenderJobs).not.toHaveBeenCalled()
  })

  fireEvent.click(screen.getByRole('button', { name: /Queue Local Preview/i }))

  await waitFor(() => {
    expect(queueComicPanelRenders).toHaveBeenCalledWith('panel-1', {
      candidate_count: 3,
      execution_mode: 'local_preview',
    })
  })

  expect(getComicPanelRenderJobs).not.toHaveBeenCalled()
})

test('imported panel with persisted remote-job counts fetches and surfaces remote status', async () => {
  vi.mocked(importComicStoryPlan).mockResolvedValue(
    buildEpisodeDetail(1, { 'panel-1': { remote: 2, pending: 1 } }),
  )
  vi.mocked(getComicPanelRenderJobs).mockResolvedValue(buildRemoteRenderJobs('panel-1'))

  renderWithProviders(<ComicStudio />)

  expect(await screen.findByRole('heading', { name: /Comic Studio/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getByLabelText(/^Character$/i)).toHaveValue('char-1')
    expect(screen.getByLabelText(/Character Version/i)).toHaveValue('charver-1')
  })

  fillApprovedPlanJson()
  fireEvent.click(screen.getByRole('button', { name: /Import Story Plan/i }))

  expect(await screen.findByRole('heading', { name: /Episode lineage/i })).toBeInTheDocument()

  await waitFor(() => {
    expect(getComicPanelRenderJobs).toHaveBeenCalledWith('panel-1')
  })

  expect(await screen.findByText(/^Remote Production$/i)).toBeInTheDocument()
  expect(screen.getByText(/Pending Remote Jobs/i)).toBeInTheDocument()
  expect(await screen.findByText(/ComfyUI rejected prompt 1\./i)).toBeInTheDocument()
})
