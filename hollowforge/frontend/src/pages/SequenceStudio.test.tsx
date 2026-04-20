import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import {
  createSequenceBlueprint,
  listSequenceBlueprints,
} from '../api/client'
import type { SequenceBlueprintDetailResponse } from '../api/client'
import SequenceStudio from './SequenceStudio'

vi.mock('../api/client', () => ({
  listSequenceBlueprints: vi.fn().mockResolvedValue([]),
  listSequenceRuns: vi.fn().mockResolvedValue([]),
  createSequenceBlueprint: vi.fn(),
  createSequenceRun: vi.fn(),
  getSequenceRun: vi.fn(),
  startSequenceRun: vi.fn(),
}))

function renderPage(initialEntries: string[] = ['/sequences']) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <SequenceStudio />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function buildBlueprintDetail(
  overrides: Partial<SequenceBlueprintDetailResponse['blueprint']> = {},
): SequenceBlueprintDetailResponse {
  return {
    blueprint: {
      id: 'blueprint-1',
      work_id: null,
      series_id: null,
      production_episode_id: null,
      content_mode: 'all_ages',
      policy_profile_id: 'safe_stage1_v1',
      character_id: 'char_stage1',
      location_id: 'location_stage1',
      beat_grammar_id: 'stage1_single_location_v1',
      target_duration_sec: 36,
      shot_count: 6,
      tone: 'tense',
      executor_policy: 'safe_remote_prod',
      created_at: '2026-04-18T00:00:00+00:00',
      updated_at: '2026-04-18T00:00:00+00:00',
      ...overrides,
    },
    planned_shots: [],
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(listSequenceBlueprints).mockResolvedValue([])
  vi.mocked(createSequenceBlueprint).mockResolvedValue(buildBlueprintDetail())
})

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

test('filters by production episode query and injects production context into blueprint creation', async () => {
  vi.mocked(listSequenceBlueprints).mockResolvedValue([
    buildBlueprintDetail({
      id: 'blueprint-linked-7',
      work_id: 'work-7',
      series_id: 'series-7',
      production_episode_id: 'prod-ep-7',
      content_mode: 'adult_nsfw',
      policy_profile_id: 'adult_stage1_v1',
      beat_grammar_id: 'adult_stage1_v1',
      executor_policy: 'adult_remote_prod',
    }),
  ])

  renderPage([
    '/sequences?production_episode_id=prod-ep-7&work_id=work-7&series_id=series-7&content_mode=adult_nsfw&mode=create_from_production&sequence_blueprint_id=blueprint-linked-7',
  ])

  await waitFor(() => {
    expect(listSequenceBlueprints).toHaveBeenCalledWith({
      production_episode_id: 'prod-ep-7',
    })
  })
  expect(screen.getByLabelText(/Content Mode/i)).toHaveValue('adult_nsfw')
  expect(screen.getByLabelText(/Content Mode/i)).toBeDisabled()

  fireEvent.click(screen.getByRole('button', { name: /Create Blueprint/i }))

  await waitFor(() => {
    expect(createSequenceBlueprint).toHaveBeenCalledWith(
      expect.objectContaining({
        work_id: 'work-7',
        series_id: 'series-7',
        production_episode_id: 'prod-ep-7',
        content_mode: 'adult_nsfw',
      }),
    )
  })
})
