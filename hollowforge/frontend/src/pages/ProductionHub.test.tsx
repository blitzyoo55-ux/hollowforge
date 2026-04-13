import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'

import { listProductionEpisodes } from '../api/client'
import type { ProductionEpisodeDetailResponse } from '../api/client'
import ProductionHub from './ProductionHub'

vi.mock('../api/client', () => ({
  listProductionEpisodes: vi.fn(),
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
        <ProductionHub />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function buildEpisode(overrides: Partial<ProductionEpisodeDetailResponse> = {}): ProductionEpisodeDetailResponse {
  return {
    id: 'prod-ep-1',
    work_id: 'work_demo',
    series_id: 'series_demo',
    title: 'Production Hub Smoke Episode',
    synopsis: 'Camila hands off the corridor scene into comic and animation packaging.',
    content_mode: 'adult_nsfw',
    target_outputs: ['comic', 'animation'],
    continuity_summary: null,
    status: 'draft',
    comic_track: {
      id: 'comic-ep-1',
      status: 'planned',
      target_output: 'oneshot_manga',
      character_id: 'camila',
    },
    animation_track: null,
    created_at: '2026-04-13T00:00:00+00:00',
    updated_at: '2026-04-13T00:00:00+00:00',
    ...overrides,
  }
}

test('renders production episodes with comic and animation track state', async () => {
  vi.mocked(listProductionEpisodes).mockResolvedValue([buildEpisode()])

  renderPage()

  expect(await screen.findByRole('heading', { name: /Production Hub/i })).toBeInTheDocument()
  expect(screen.getByText(/Shared Production Core/i)).toBeInTheDocument()
  expect(await screen.findByText(/Production Hub Smoke Episode/i)).toBeInTheDocument()
  expect(screen.getByText(/^adult_nsfw$/i)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Comic Track/i })).toBeInTheDocument()
  expect(screen.getAllByRole('heading', { name: /Animation Track/i }).length).toBeGreaterThan(0)
  expect(screen.getByText(/No animation-track blueprint is linked yet/i)).toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: /Open Comic Handoff/i }).length).toBeGreaterThan(0)
})

test('renders an empty state when no production episodes exist', async () => {
  vi.mocked(listProductionEpisodes).mockResolvedValue([])

  renderPage()

  expect(await screen.findByText(/No production episodes yet/i)).toBeInTheDocument()
  expect(screen.getByText(/Create shared production-core episodes first/i)).toBeInTheDocument()
})
