import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useEffect } from 'react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import {
  createSequenceBlueprint,
  getProductionEpisode,
  listSequenceBlueprints,
  type ProductionEpisodeDetailResponse,
} from '../api/client'
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
  vi.mocked(createSequenceBlueprint).mockResolvedValue({
    blueprint: {
      id: 'bp-created-1',
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
  })
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

function SequenceStudioRouteDriver({ path }: { path: string }) {
  const navigate = useNavigate()

  useEffect(() => {
    navigate(path)
  }, [navigate, path])

  return <SequenceStudio />
}

function renderPageWithRouteControl(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  const renderAtPath = (path: string) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/sequences']}>
        <SequenceStudioRouteDriver path={path} />
      </MemoryRouter>
    </QueryClientProvider>
  )

  const view = render(renderAtPath(initialPath))
  return {
    ...view,
    setPath: (path: string) => view.rerender(renderAtPath(path)),
  }
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

test('blocks create_from_production submission while production context is unresolved', async () => {
  vi.mocked(getProductionEpisode).mockImplementation(() => new Promise(() => {}))

  renderPage('/sequences?production_episode_id=prod-ep-1&mode=create_from_production')

  const createButton = await screen.findByRole('button', { name: /Create Blueprint/i })
  expect(createButton).toBeDisabled()
  expect(
    screen.getByText(/Checking linked blueprints for this production episode before creating a new track/i),
  ).toBeInTheDocument()

  fireEvent.click(createButton)
  expect(vi.mocked(createSequenceBlueprint)).not.toHaveBeenCalled()
})

test('create_from_production submit includes required linkage fields', async () => {
  vi.mocked(getProductionEpisode).mockResolvedValue(
    buildEpisode({
      id: 'prod-ep-9',
      work_id: 'work_locked',
      series_id: 'series_locked',
      content_mode: 'adult_nsfw',
    }),
  )

  renderPage('/sequences?production_episode_id=prod-ep-9&mode=create_from_production')

  await screen.findByText(/Production Episode Context/i)
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Create Blueprint/i })).not.toBeDisabled()
  })

  fireEvent.click(screen.getByRole('button', { name: /Create Blueprint/i }))

  await waitFor(() => {
    expect(vi.mocked(createSequenceBlueprint)).toHaveBeenCalled()
  })
  expect(vi.mocked(createSequenceBlueprint)).toHaveBeenCalledWith(
    expect.objectContaining({
      content_mode: 'adult_nsfw',
      work_id: 'work_locked',
      series_id: 'series_locked',
      production_episode_id: 'prod-ep-9',
    }),
  )
})

test('create_from_production blocks duplicate creation when linked blueprints already exist and shows manual-open fallback', async () => {
  vi.mocked(getProductionEpisode).mockResolvedValue(
    buildEpisode({
      id: 'prod-ep-dup',
      work_id: 'work_dup',
      series_id: 'series_dup',
      content_mode: 'adult_nsfw',
    }),
  )
  vi.mocked(listSequenceBlueprints).mockImplementation(async (params) => {
    const productionEpisodeId = (params as { production_episode_id?: string } | undefined)?.production_episode_id
    if (productionEpisodeId === 'prod-ep-dup') {
      return [
        {
          blueprint: {
            id: 'bp-linked-dup-1',
            work_id: 'work_dup',
            series_id: 'series_dup',
            production_episode_id: 'prod-ep-dup',
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
      ]
    }
    return []
  })

  renderPage('/sequences?production_episode_id=prod-ep-dup&mode=create_from_production')

  expect(await screen.findByText(/already linked to this production episode/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Open Linked Blueprint bp-linked-dup-1/i })).toBeInTheDocument()

  const createButton = screen.getByRole('button', { name: /Create Blueprint/i })
  expect(createButton).toBeDisabled()
  fireEvent.click(createButton)
  expect(vi.mocked(createSequenceBlueprint)).not.toHaveBeenCalled()
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

test('keeps ambiguous open_current in filter-only mode when multiple linked blueprints exist', async () => {
  vi.mocked(listSequenceBlueprints).mockResolvedValue([
    {
      blueprint: {
        id: 'bp-linked-1',
        work_id: 'work_demo',
        series_id: 'series_demo',
        production_episode_id: 'prod-ep-1',
        content_mode: 'adult_nsfw',
        policy_profile_id: 'adult_stage1_v1',
        character_id: 'char_alpha',
        location_id: 'location_alpha',
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
    {
      blueprint: {
        id: 'bp-linked-2',
        work_id: 'work_demo',
        series_id: 'series_demo',
        production_episode_id: 'prod-ep-1',
        content_mode: 'adult_nsfw',
        policy_profile_id: 'adult_stage1_v1',
        character_id: 'char_beta',
        location_id: 'location_beta',
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

  expect(await screen.findByText(/char_alpha in location_alpha/i)).toBeInTheDocument()
  expect(screen.getByText(/char_beta in location_beta/i)).toBeInTheDocument()
  expect(screen.queryByText(/Production Episode Context/i)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Selected$/i })).not.toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: /^Inspect$/i })).toHaveLength(2)
  expect(vi.mocked(listSequenceBlueprints)).toHaveBeenCalledWith({ production_episode_id: 'prod-ep-1' })
})

test('route transition into ambiguous open_current clears stale selected blueprint and shows manual-open fallback', async () => {
  vi.mocked(listSequenceBlueprints).mockImplementation(async (params) => {
    const productionEpisodeId = (params as { production_episode_id?: string } | undefined)?.production_episode_id
    if (productionEpisodeId === 'prod-ep-single') {
      return [
        {
          blueprint: {
            id: 'bp-linked-single',
            work_id: 'work_demo',
            series_id: 'series_demo',
            production_episode_id: 'prod-ep-single',
            content_mode: 'adult_nsfw',
            policy_profile_id: 'adult_stage1_v1',
            character_id: 'char_single',
            location_id: 'location_single',
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
      ]
    }
    if (productionEpisodeId === 'prod-ep-ambiguous') {
      return [
        {
          blueprint: {
            id: 'bp-linked-ambig-1',
            work_id: 'work_demo',
            series_id: 'series_demo',
            production_episode_id: 'prod-ep-ambiguous',
            content_mode: 'adult_nsfw',
            policy_profile_id: 'adult_stage1_v1',
            character_id: 'char_alpha',
            location_id: 'location_alpha',
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
        {
          blueprint: {
            id: 'bp-linked-ambig-2',
            work_id: 'work_demo',
            series_id: 'series_demo',
            production_episode_id: 'prod-ep-ambiguous',
            content_mode: 'adult_nsfw',
            policy_profile_id: 'adult_stage1_v1',
            character_id: 'char_beta',
            location_id: 'location_beta',
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
      ]
    }
    return []
  })

  const view = renderPageWithRouteControl('/sequences?production_episode_id=prod-ep-single&mode=open_current')

  expect(await screen.findByRole('button', { name: /Selected/i })).toBeInTheDocument()

  view.setPath('/sequences?production_episode_id=prod-ep-ambiguous&mode=open_current')

  expect(await screen.findByText(/multiple linked blueprints were found/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Open Linked Blueprint bp-linked-ambig-1/i })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /^Selected$/i })).not.toBeInTheDocument()
})

test('clears stale production linkage after leaving create_from_production without remount', async () => {
  vi.mocked(getProductionEpisode).mockResolvedValue(
    buildEpisode({
      id: 'prod-ep-transition',
      work_id: 'work_transition',
      series_id: 'series_transition',
      content_mode: 'adult_nsfw',
    }),
  )

  const view = renderPageWithRouteControl('/sequences?production_episode_id=prod-ep-transition&mode=create_from_production')

  expect(await screen.findByText(/Production Episode Context/i)).toBeInTheDocument()
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /Create Blueprint/i })).not.toBeDisabled()
  })

  view.setPath('/sequences')

  await waitFor(() => {
    expect(screen.queryByText(/Production Episode Context/i)).not.toBeInTheDocument()
  })

  fireEvent.click(screen.getByRole('button', { name: /Create Blueprint/i }))

  await waitFor(() => {
    expect(vi.mocked(createSequenceBlueprint)).toHaveBeenCalled()
  })
  expect(vi.mocked(createSequenceBlueprint)).toHaveBeenCalledWith(
    expect.objectContaining({
      work_id: null,
      series_id: null,
      production_episode_id: null,
    }),
  )
})
