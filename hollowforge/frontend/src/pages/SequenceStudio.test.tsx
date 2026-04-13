import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import { getProductionEpisode, listSequenceBlueprints, type ProductionEpisodeDetailResponse } from '../api/client'
import SequenceStudio from './SequenceStudio'

vi.mock('../api/client', () => ({
  listSequenceBlueprints: vi.fn().mockResolvedValue([]),
  listSequenceRuns: vi.fn().mockResolvedValue([]),
  getProductionEpisode: vi.fn(),
  createSequenceBlueprint: vi.fn(),
  createSequenceRun: vi.fn(),
  getSequenceRun: vi.fn(),
  startSequenceRun: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listSequenceBlueprints).mockResolvedValue([])
  vi.mocked(getProductionEpisode).mockResolvedValue(buildEpisode())
})

function buildEpisode(overrides: Partial<ProductionEpisodeDetailResponse> = {}): ProductionEpisodeDetailResponse {
  return {
    id: 'prod-ep-1',
    work_id: 'work_demo',
    series_id: 'series_demo',
    title: 'Episode One',
    synopsis: 'Synopsis',
    content_mode: 'adult_nsfw',
    target_outputs: ['animation'],
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

function renderPage(initialPath = '/sequences') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <SequenceStudio />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('renders Stage 1 blueprint controls', async () => {
  renderPage()

  expect(await screen.findByRole('heading', { name: /Animation Track Studio/i })).toBeInTheDocument()
  expect(screen.getByText(/^Stage 1 Sequence$/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/Content Mode/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/Executor Profile/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Create Blueprint/i })).toBeInTheDocument()
})

test('shows the adult Stage 1 grammar option when adult mode is selected', async () => {
  renderPage()

  fireEvent.change(screen.getByLabelText(/Content Mode/i), { target: { value: 'adult_nsfw' } })

  const beatGrammarSelect = screen.getByLabelText(/Beat Grammar/i)
  expect(beatGrammarSelect).toHaveValue('adult_stage1_v1')
  expect(within(beatGrammarSelect).getByRole('option', { name: /adult_stage1_v1/i })).toBeInTheDocument()
  expect(
    screen.getByText(/Lane-separated adult Stage 1 controls using the adult grammar/i),
  ).toBeInTheDocument()
})

test('prefills blueprint context from production handoff when mode=create_from_production', async () => {
  vi.mocked(getProductionEpisode).mockResolvedValue(
    buildEpisode({
      id: 'prod-ep-1',
      work_id: 'work_alpha',
      series_id: 'series_alpha',
      content_mode: 'adult_nsfw',
    }),
  )

  renderPage('/sequences?production_episode_id=prod-ep-1&mode=create_from_production')

  expect(await screen.findByText(/Production Episode Context/i)).toBeInTheDocument()
  await waitFor(() => {
    expect(screen.getByLabelText(/Content Mode/i)).toHaveValue('adult_nsfw')
  })
  expect(screen.getByText(/Production Episode:\s*prod-ep-1/i)).toBeInTheDocument()
  expect(screen.getByText(/Work:\s*work_alpha/i)).toBeInTheDocument()
  expect(screen.getByText(/Series:\s*series_alpha/i)).toBeInTheDocument()
  expect(vi.mocked(getProductionEpisode)).toHaveBeenCalledWith('prod-ep-1')
})

test('auto-selects the single linked blueprint when mode=open_current', async () => {
  vi.mocked(listSequenceBlueprints).mockResolvedValue([
    {
      blueprint: {
        id: 'bp-linked-1',
        work_id: 'work_demo',
        series_id: 'series_demo',
        production_episode_id: 'prod-ep-1',
        content_mode: 'adult_nsfw',
        policy_profile_id: 'adult_stage1_v1',
        character_id: 'char_stage1',
        location_id: 'location_stage1',
        beat_grammar_id: 'adult_stage1_v1',
        target_duration_sec: 36,
        shot_count: 6,
        tone: 'tense',
        executor_policy: 'adult_remote_prod',
        created_at: '2026-04-11T10:00:00Z',
        updated_at: '2026-04-11T10:00:00Z',
      },
      planned_shots: [],
    },
  ])

  renderPage('/sequences?production_episode_id=prod-ep-1&mode=open_current')

  expect(await screen.findByRole('button', { name: /Selected/i })).toBeInTheDocument()
  expect(vi.mocked(listSequenceBlueprints)).toHaveBeenCalledWith({ production_episode_id: 'prod-ep-1' })
})
