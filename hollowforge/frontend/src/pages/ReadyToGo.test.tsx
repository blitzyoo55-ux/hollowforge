import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeAll, beforeEach, expect, test, vi } from 'vitest'

import { getGallery } from '../api/client'
import ReadyToGo from './ReadyToGo'

const navigateSpy = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateSpy,
  }
})

vi.mock('../api/client', () => ({
  getGallery: vi.fn(),
}))

vi.mock('../lib/toast', () => ({
  notify: {
    info: vi.fn(),
  },
}))

vi.mock('../components/GalleryGrid', () => ({
  default: ({
    items,
    selectionMode,
    selectedIds,
    onToggleSelect,
  }: {
    items: Array<{ id: string; prompt: string }>
    selectionMode: boolean
    selectedIds: Set<string>
    onToggleSelect: (item: { id: string; prompt: string }) => void
  }) => (
    <div data-testid="gallery-grid">
      <div>selection-mode:{selectionMode ? 'on' : 'off'}</div>
      <div>selected-count:{selectedIds.size}</div>
      {items.map((item) => (
        <button key={item.id} type="button" onClick={() => onToggleSelect(item)}>
          toggle-{item.id}
        </button>
      ))}
    </div>
  ),
}))

vi.mock('../components/Lightbox', () => ({
  default: () => <div data-testid="lightbox">LightboxMock</div>,
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
        <ReadyToGo />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function buildGalleryItem(id: string) {
  return {
    id,
    prompt: `prompt ${id}`,
    negative_prompt: null,
    checkpoint: 'waiIllustriousSDXL_v160.safetensors',
    loras: [],
    seed: 123,
    steps: 28,
    cfg: 5.4,
    width: 832,
    height: 1216,
    sampler: 'euler',
    scheduler: 'normal',
    clip_skip: null,
    status: 'completed',
    image_path: `images/${id}.png`,
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
    generation_time_sec: 12.4,
    tags: ['ready'],
    preset_id: null,
    notes: null,
    source_id: null,
    comfyui_prompt_id: null,
    error_message: null,
    is_favorite: false,
    publish_approved: 1,
    created_at: '2026-03-27T00:00:00+00:00',
    completed_at: '2026-03-27T00:00:12+00:00',
  }
}

beforeAll(() => {
  class MockIntersectionObserver {
    observe() {}
    disconnect() {}
    unobserve() {}
  }

  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
})

beforeEach(() => {
  navigateSpy.mockReset()
})

test('renders the ready-to-go empty state and gallery action', async () => {
  vi.mocked(getGallery).mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    per_page: 24,
    total_pages: 1,
  })

  renderPage()

  expect(await screen.findByRole('heading', { name: /Ready to Go/i })).toBeInTheDocument()
  expect(await screen.findByText(/Ready to Go 이미지가 없습니다/i)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Gallery 열기/i }))

  expect(navigateSpy).toHaveBeenCalledWith('/gallery')
})

test('shows an error message when the ready gallery query fails', async () => {
  vi.mocked(getGallery).mockRejectedValueOnce(new Error('gallery failed'))

  renderPage()

  expect(await screen.findByText(/Failed to load ready-to-go images\./i)).toBeInTheDocument()
})

test('launches the marketing handoff with selected generation ids', async () => {
  vi.mocked(getGallery).mockResolvedValue({
    items: [buildGalleryItem('ready-gen-1')],
    total: 1,
    page: 1,
    per_page: 24,
    total_pages: 1,
  })

  renderPage()

  expect(await screen.findByTestId('gallery-grid')).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Select for publishing pilot/i }))
  fireEvent.click(screen.getByRole('button', { name: /toggle-ready-gen-1/i }))

  await waitFor(() => {
    expect(screen.getByText(/1 selected for publishing pilot/i)).toBeInTheDocument()
  })

  fireEvent.click(screen.getByRole('button', { name: /Launch marketing handoff/i }))

  expect(navigateSpy).toHaveBeenCalledWith('/marketing?generation_id=ready-gen-1')
})
