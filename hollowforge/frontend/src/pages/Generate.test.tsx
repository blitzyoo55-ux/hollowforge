import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import type { GenerationCreate } from '../api/client'
import { getGeneration, getPresets } from '../api/client'
import Generate from './Generate'

const generateFormSpy = vi.fn()

vi.mock('../api/client', () => ({
  createGeneration: vi.fn(),
  createGenerationBatch: vi.fn(),
  createPreset: vi.fn(),
  getGeneration: vi.fn(),
  getPresets: vi.fn(),
}))

vi.mock('../components/GenerateForm', () => ({
  default: (props: unknown) => {
    generateFormSpy(props)
    return <div data-testid="generate-form">GenerateFormMock</div>
  },
}))

vi.mock('../components/ProgressCard', () => ({
  default: () => <div data-testid="progress-card">ProgressCardMock</div>,
}))

function renderPage(initialEntry = '/generate') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Generate />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  generateFormSpy.mockClear()
  vi.mocked(getPresets).mockResolvedValue([])
  vi.mocked(getGeneration).mockResolvedValue({
    id: 'source-gen-1',
    prompt: 'source prompt',
    negative_prompt: null,
    checkpoint: 'prefectIllustriousXL_v70.safetensors',
    loras: [],
    seed: 404,
    steps: 28,
    cfg: 5.4,
    width: 832,
    height: 1216,
    sampler: 'euler',
    scheduler: 'normal',
    clip_skip: null,
    status: 'completed',
    image_path: 'images/source-gen-1.png',
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
    generation_time_sec: 12.3,
    tags: null,
    preset_id: null,
    notes: null,
    source_id: null,
    comfyui_prompt_id: null,
    error_message: null,
    is_favorite: false,
    created_at: '2026-03-27T00:00:00+00:00',
    completed_at: '2026-03-27T00:00:12+00:00',
  })
})

test('renders the generate page shell and default form', async () => {
  renderPage()

  expect(await screen.findByRole('heading', { name: /Generate/i })).toBeInTheDocument()
  expect(screen.getByText(/Create a new image with ComfyUI/i)).toBeInTheDocument()
  expect(screen.getByTestId('generate-form')).toBeInTheDocument()
  expect(screen.getByText(/Preview will appear here/i)).toBeInTheDocument()
})

test('passes preset-derived initial values into the generate form', async () => {
  vi.mocked(getPresets).mockResolvedValue([
    {
      id: 'preset-1',
      name: 'Editorial Portrait',
      description: null,
      checkpoint: 'waiIllustriousSDXL_v160.safetensors',
      loras: [],
      prompt_template: 'preset portrait prompt',
      negative_prompt: 'bad anatomy',
      default_params: {
        steps: 32,
        cfg: 6.1,
        width: 768,
        height: 1024,
        sampler: 'euler_a',
        scheduler: 'normal',
        clip_skip: 2,
      },
      tags: ['editorial', 'smoke'],
      created_at: '2026-03-27T00:00:00+00:00',
      updated_at: null,
    },
  ])

  renderPage('/generate?preset=preset-1')

  await waitFor(() => {
    const latestProps = generateFormSpy.mock.calls.at(-1)?.[0] as
      | { initialValues?: Partial<GenerationCreate> }
      | undefined
    expect(latestProps?.initialValues).toMatchObject({
      prompt: 'preset portrait prompt',
      negative_prompt: 'bad anatomy',
      checkpoint: 'waiIllustriousSDXL_v160.safetensors',
      steps: 32,
      cfg: 6.1,
      width: 768,
      height: 1024,
      sampler: 'euler_a',
      scheduler: 'normal',
      clip_skip: 2,
      tags: ['editorial', 'smoke'],
      preset_id: 'preset-1',
    })
  })
})

test('shows a source-generation error banner when the source lookup fails', async () => {
  vi.mocked(getGeneration).mockRejectedValueOnce(new Error('source lookup failed'))

  renderPage('/generate?from=source-gen-1')

  expect(
    await screen.findByText(/Failed to load source generation from URL parameter\./i),
  ).toBeInTheDocument()
})
