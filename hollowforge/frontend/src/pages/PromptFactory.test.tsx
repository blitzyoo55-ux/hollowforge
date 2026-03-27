import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import {
  generatePromptBatch,
  getPromptFactoryCapabilities,
  getPromptFactoryCheckpointPreferences,
} from '../api/client'
import PromptFactory from './PromptFactory'

vi.mock('../api/client', () => ({
  generatePromptBatch: vi.fn(),
  generatePromptBatchAndQueue: vi.fn(),
  getPromptFactoryCapabilities: vi.fn(),
  getPromptFactoryCheckpointPreferences: vi.fn(),
  queuePromptBatch: vi.fn(),
  updatePromptFactoryCheckpointPreferences: vi.fn(),
}))

vi.mock('../lib/toast', () => ({
  notify: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function renderPage() {
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
        <PromptFactory />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function buildCapabilities(overrides: Partial<Awaited<ReturnType<typeof getPromptFactoryCapabilities>>> = {}) {
  return {
    default_provider: 'xai',
    default_model: 'grok-4.1-fast',
    openrouter_configured: true,
    xai_configured: true,
    ready: true,
    recommended_lane: 'sdxl_illustrious',
    supported_lanes: ['auto', 'sdxl_illustrious', 'classic_clip'],
    batch_import_headers: ['Set_No', 'Checkpoint'],
    notes: ['factory note one'],
    ...overrides,
  }
}

function buildCheckpointPreferences() {
  return {
    generated_at: '2026-03-27T00:00:00+00:00',
    entries: [
      {
        checkpoint: 'waiIllustriousSDXL_v160.safetensors',
        available: true,
        architecture: 'sdxl',
        favorite_count: 14,
        mode: 'default' as const,
        priority_boost: 0,
        notes: null,
        updated_at: '2026-03-27T00:00:00+00:00',
      },
    ],
  }
}

function buildPreviewResponse() {
  return {
    provider: 'xai',
    model: 'grok-4.1-fast',
    requested_count: 8,
    generated_count: 2,
    chunk_count: 1,
    benchmark: {
      favorites_total: 10,
      workflow_lane: 'sdxl_illustrious',
      prompt_dialect: 'tag_stack',
      top_checkpoints: ['waiIllustriousSDXL_v160.safetensors'],
      top_loras: [],
      avg_lora_strength: 0.42,
      cfg_values: [5.4],
      steps_values: [30],
      sampler: 'euler_a',
      scheduler: 'normal',
      clip_skip: 2,
      width: 832,
      height: 1216,
      theme_keywords: ['editorial'],
      material_cues: ['latex sheen'],
      control_cues: ['containment frame'],
      camera_cues: ['low angle'],
      environment_cues: ['control room'],
      exposure_cues: ['rim light'],
      negative_prompt: 'bad anatomy',
    },
    direction_pack: [
      {
        codename_stub: 'alpha',
        series: 'series_a',
        scene_hook: 'sealed intake chamber',
        camera_plan: 'low angle portrait',
        pose_plan: 'restrained standing pose',
        environment: 'containment lab',
        device_focus: 'mask harness',
        lighting_plan: 'cold rim light',
        material_focus: 'gloss latex',
        intensity_hook: 'high tension',
      },
    ],
    rows: [
      {
        set_no: 1,
        codename: 'alpha',
        series: 'series_a',
        checkpoint: 'waiIllustriousSDXL_v160.safetensors',
        workflow_lane: 'sdxl_illustrious' as const,
        loras: [],
        sampler: 'euler_a',
        steps: 30,
        cfg: 5.4,
        clip_skip: 2,
        width: 832,
        height: 1216,
        positive_prompt: 'prompt alpha',
        negative_prompt: 'bad anatomy',
      },
      {
        set_no: 2,
        codename: 'beta',
        series: 'series_b',
        checkpoint: 'waiIllustriousSDXL_v160.safetensors',
        workflow_lane: 'sdxl_illustrious' as const,
        loras: [],
        sampler: 'euler_a',
        steps: 30,
        cfg: 5.4,
        clip_skip: 2,
        width: 832,
        height: 1216,
        positive_prompt: 'prompt beta',
        negative_prompt: 'bad anatomy',
      },
    ],
  }
}

beforeEach(() => {
  vi.mocked(getPromptFactoryCapabilities).mockResolvedValue(buildCapabilities())
  vi.mocked(getPromptFactoryCheckpointPreferences).mockResolvedValue(buildCheckpointPreferences())
  vi.mocked(generatePromptBatch).mockResolvedValue(buildPreviewResponse())
})

test('renders the prompt factory shell and quick recipe panel', async () => {
  renderPage()

  expect(await screen.findByRole('heading', { name: /Prompt Factory/i })).toBeInTheDocument()
  expect(screen.getByText(/Quick Recipes/i)).toBeInTheDocument()
  expect(screen.getByText(/Factory Status/i)).toBeInTheDocument()
  expect(screen.getByText(/Human Workflow/i)).toBeInTheDocument()
  expect(screen.getByText(/Balanced Production/i)).toBeInTheDocument()
})

test('applies the quick recipe selection to the visible summary', async () => {
  renderPage()

  expect(await screen.findByText(/Current Count/i)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Director Mode/i }))

  const summaryTile = screen.getByText(/Current Count/i).parentElement
  expect(summaryTile).not.toBeNull()
  expect(within(summaryTile as HTMLElement).getByText(/12 rows/i)).toBeInTheDocument()
  expect(
    screen.getByText((_, element) => element?.textContent === 'Autonomy Director'),
  ).toBeInTheDocument()
})

test('renders preview results after preview generation succeeds', async () => {
  renderPage()

  const previewButton = await screen.findByRole('button', { name: /Preview Directions & Prompts/i })
  await waitFor(() => {
    expect(previewButton).toBeEnabled()
  })

  fireEvent.click(previewButton)

  await waitFor(() => {
    expect(generatePromptBatch).toHaveBeenCalledTimes(1)
  })

  const latestResultHeading = await screen.findByText(/Latest Result/i)
  expect(latestResultHeading).toBeInTheDocument()
  const latestResultSection = latestResultHeading.closest('section')
  expect(latestResultSection).not.toBeNull()
  expect(within(latestResultSection as HTMLElement).getByText(/Generated/i)).toBeInTheDocument()
  expect(screen.getAllByText(/Prompt Rows/i).length).toBeGreaterThan(0)
  expect(screen.getAllByText(/Direction Pack/i).length).toBeGreaterThan(0)
  expect(screen.getByText(/prompt alpha/i)).toBeInTheDocument()
  const generatedTile = within(latestResultSection as HTMLElement).getByText(/Generated/i).parentElement
  expect(generatedTile).not.toBeNull()
  expect(within(generatedTile as HTMLElement).getByText(/^2$/)).toBeInTheDocument()
})
