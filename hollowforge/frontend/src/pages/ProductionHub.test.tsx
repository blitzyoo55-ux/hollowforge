import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import {
  createProductionWork,
  getProductionComicVerificationSummary,
  listProductionEpisodes,
  listProductionSeries,
  listProductionWorks,
} from '../api/client'
import type {
  ComicVerificationRunResponse,
  ComicVerificationSummaryResponse,
  ProductionEpisodeDetailResponse,
  ProductionSeriesResponse,
  ProductionWorkResponse,
} from '../api/client'
import ProductionHub from './ProductionHub'

vi.mock('../api/client', () => ({
  listProductionEpisodes: vi.fn(),
  listProductionWorks: vi.fn(),
  listProductionSeries: vi.fn(),
  getProductionComicVerificationSummary: vi.fn(),
  createProductionWork: vi.fn(),
  createProductionSeries: vi.fn(),
  createProductionEpisode: vi.fn(),
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
    comic_track_count: 0,
    animation_track_count: 0,
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

function buildWork(overrides: Partial<ProductionWorkResponse> = {}): ProductionWorkResponse {
  return {
    id: 'work_demo',
    title: 'Demo Work',
    format_family: 'mixed',
    default_content_mode: 'adult_nsfw',
    status: 'draft',
    canon_notes: null,
    created_at: '2026-04-13T00:00:00+00:00',
    updated_at: '2026-04-13T00:00:00+00:00',
    ...overrides,
  }
}

function buildSeries(overrides: Partial<ProductionSeriesResponse> = {}): ProductionSeriesResponse {
  return {
    id: 'series_demo',
    work_id: 'work_demo',
    title: 'Demo Series',
    delivery_mode: 'serial',
    audience_mode: 'adult_nsfw',
    visual_identity_notes: null,
    created_at: '2026-04-13T00:00:00+00:00',
    updated_at: '2026-04-13T00:00:00+00:00',
    ...overrides,
  }
}

function buildVerificationRun(overrides: Partial<ComicVerificationRunResponse> = {}): ComicVerificationRunResponse {
  return {
    id: 'run-1',
    run_mode: 'preflight',
    status: 'completed',
    overall_success: true,
    failure_stage: null,
    error_summary: null,
    base_url: 'http://127.0.0.1:8000',
    total_duration_sec: 2.345,
    started_at: '2026-04-17T00:00:00+00:00',
    finished_at: '2026-04-17T00:00:02+00:00',
    stage_status: {},
    created_at: '2026-04-17T00:00:02+00:00',
    updated_at: '2026-04-17T00:00:02+00:00',
    ...overrides,
  }
}

function buildVerificationSummary(
  overrides: Partial<ComicVerificationSummaryResponse> = {},
): ComicVerificationSummaryResponse {
  return {
    latest_preflight: null,
    latest_suite: null,
    recent_runs: [],
    ...overrides,
  }
}

beforeEach(() => {
  vi.mocked(getProductionComicVerificationSummary).mockReset()
  vi.mocked(getProductionComicVerificationSummary).mockResolvedValue(buildVerificationSummary())
})

test('renders production episodes with comic and animation track state', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([])
  vi.mocked(listProductionSeries).mockResolvedValue([])
  vi.mocked(listProductionEpisodes).mockResolvedValue([buildEpisode()])

  renderPage()

  expect(await screen.findByRole('heading', { name: /Production Hub/i })).toBeInTheDocument()
  expect(screen.getByText(/Shared Production Core/i)).toBeInTheDocument()
  expect(await screen.findByText(/Production Hub Smoke Episode/i)).toBeInTheDocument()
  expect(screen.getAllByText(/^adult_nsfw$/i).length).toBeGreaterThan(0)
  expect(screen.getByRole('heading', { name: /Comic Track/i })).toBeInTheDocument()
  expect(screen.getAllByRole('heading', { name: /Animation Track/i }).length).toBeGreaterThan(0)
  expect(screen.getByText(/No animation-track blueprint is linked yet/i)).toBeInTheDocument()
  expect(screen.getAllByRole('link', { name: /Open Comic Handoff/i }).length).toBeGreaterThan(0)
})

test('renders an empty state when no production episodes exist', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([])
  vi.mocked(listProductionSeries).mockResolvedValue([])
  vi.mocked(listProductionEpisodes).mockResolvedValue([])

  renderPage()

  expect(await screen.findByText(/No production episodes yet/i)).toBeInTheDocument()
  expect(screen.getByText(/Create shared production-core episodes first/i)).toBeInTheDocument()
})

test('renders all production creation panels', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([buildWork()])
  vi.mocked(listProductionSeries).mockResolvedValue([buildSeries()])
  vi.mocked(listProductionEpisodes).mockResolvedValue([])

  renderPage()

  expect(await screen.findByRole('heading', { name: /Create Production Work/i })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Create Production Series/i })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Create Production Episode/i })).toBeInTheDocument()
})

test('renders verification ops above the creation forms', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([])
  vi.mocked(listProductionSeries).mockResolvedValue([])
  vi.mocked(listProductionEpisodes).mockResolvedValue([])

  renderPage()

  expect(await screen.findByRole('heading', { name: /Verification Ops/i })).toBeInTheDocument()
  expect(screen.getByText(/Run Comic Verification Suite/i)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: /Verification History/i })).toBeInTheDocument()

  const opsHeading = screen.getByRole('heading', { name: /Verification Ops/i })
  const historyHeading = screen.getByRole('heading', { name: /Verification History/i })
  const workHeading = screen.getByRole('heading', { name: /Create Production Work/i })
  expect(opsHeading.compareDocumentPosition(workHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(opsHeading.compareDocumentPosition(historyHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

test('renders verification history summary cards and recent runs', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([])
  vi.mocked(listProductionSeries).mockResolvedValue([])
  vi.mocked(listProductionEpisodes).mockResolvedValue([])
  vi.mocked(getProductionComicVerificationSummary).mockResolvedValue(
    buildVerificationSummary({
      latest_preflight: buildVerificationRun({
        id: 'preflight-1',
        run_mode: 'preflight',
        overall_success: true,
      }),
      latest_suite: buildVerificationRun({
        id: 'suite-1',
        run_mode: 'suite',
        status: 'failed',
        overall_success: false,
        failure_stage: 'full',
        error_summary: 'stage full exited with code 1',
      }),
      recent_runs: [
        buildVerificationRun({
          id: 'suite-1',
          run_mode: 'suite',
          status: 'failed',
          overall_success: false,
          failure_stage: 'full',
          error_summary: 'stage full exited with code 1',
        }),
        buildVerificationRun({
          id: 'preflight-1',
          run_mode: 'preflight',
          overall_success: true,
        }),
      ],
    }),
  )

  renderPage()

  expect(await screen.findByRole('heading', { name: /Verification History/i })).toBeInTheDocument()
  const preflightHeading = await screen.findByText('Latest Preflight')
  const preflightCard = preflightHeading.closest('article')
  expect(preflightCard).not.toBeNull()
  expect(within(preflightCard as HTMLElement).getByText('preflight')).toBeInTheDocument()

  const suiteHeading = screen.getByText('Latest Suite')
  const suiteCard = suiteHeading.closest('article')
  expect(suiteCard).not.toBeNull()
  expect(within(suiteCard as HTMLElement).getByText('suite')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText(/stage full exited with code 1/i)).toBeInTheDocument()

  expect(screen.getByRole('columnheader', { name: /Run Mode/i })).toBeInTheDocument()
})

test('submits production work without requiring a raw id field', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([buildWork()])
  vi.mocked(listProductionSeries).mockResolvedValue([])
  vi.mocked(listProductionEpisodes).mockResolvedValue([])
  vi.mocked(createProductionWork).mockResolvedValue(
    buildWork({ id: 'work_new', title: 'Pilot Work' }),
  )

  renderPage()

  expect(await screen.findByRole('heading', { name: /Create Production Work/i })).toBeInTheDocument()
  expect(screen.queryByLabelText(/^id$/i)).not.toBeInTheDocument()

  fireEvent.change(screen.getByLabelText(/Work Title/i), { target: { value: 'Pilot Work' } })
  fireEvent.click(screen.getByRole('button', { name: /Create Work/i }))

  await waitFor(() => {
    expect(createProductionWork).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Pilot Work',
        format_family: 'mixed',
      }),
    )
  })
  expect(createProductionWork).toHaveBeenCalledWith(expect.not.objectContaining({ id: expect.anything() }))
})

test('filters production series options by selected work when creating an episode', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([
    buildWork({ id: 'work_alpha', title: 'Alpha Work' }),
    buildWork({ id: 'work_beta', title: 'Beta Work' }),
  ])
  vi.mocked(listProductionSeries).mockResolvedValue([
    buildSeries({ id: 'series_alpha_1', work_id: 'work_alpha', title: 'Alpha Series' }),
    buildSeries({ id: 'series_beta_1', work_id: 'work_beta', title: 'Beta Series' }),
  ])
  vi.mocked(listProductionEpisodes).mockResolvedValue([])

  renderPage()
  expect(await screen.findByRole('heading', { name: /Create Production Episode/i })).toBeInTheDocument()

  const episodeWorkSelect = screen.getByLabelText(/Episode Work/i)
  await waitFor(() => {
    expect(within(episodeWorkSelect).getByRole('option', { name: /Beta Work/i })).toBeInTheDocument()
  })
  fireEvent.change(episodeWorkSelect, { target: { value: 'work_beta' } })

  await waitFor(() => {
    const episodeSeriesSelect = screen.getByLabelText(/Episode Series/i)
    expect(within(episodeSeriesSelect).queryByRole('option', { name: /Alpha Series/i })).not.toBeInTheDocument()
    expect(within(episodeSeriesSelect).getByRole('option', { name: /Beta Series/i })).toBeInTheDocument()
  })
})

test('builds comic and animation entry links from production track counts', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([])
  vi.mocked(listProductionSeries).mockResolvedValue([])
  vi.mocked(listProductionEpisodes).mockResolvedValue([
    buildEpisode({
      id: 'prod-ep-1',
      title: 'Track Count Zero Episode',
      comic_track_count: 0,
      animation_track_count: 0,
      comic_track: null,
      animation_track: null,
    }),
    buildEpisode({
      id: 'prod-ep-2',
      title: 'Track Count One Episode',
      comic_track_count: 1,
      animation_track_count: 1,
      comic_track: null,
      animation_track: null,
    }),
  ])

  renderPage()
  expect(await screen.findByText(/Track Count Zero Episode/i)).toBeInTheDocument()

  const zeroCard = screen.getByRole('heading', { name: /Track Count Zero Episode/i }).closest('article')
  expect(zeroCard).not.toBeNull()
  expect(within(zeroCard as HTMLElement).getByRole('link', { name: /Open Comic Handoff/i })).toHaveAttribute(
    'href',
    '/comic?production_episode_id=prod-ep-1&mode=create_from_production',
  )
  expect(within(zeroCard as HTMLElement).getByRole('link', { name: /Open Animation Track/i })).toHaveAttribute(
    'href',
    '/sequences?production_episode_id=prod-ep-1&mode=create_from_production',
  )

  const oneCard = screen.getByRole('heading', { name: /Track Count One Episode/i }).closest('article')
  expect(oneCard).not.toBeNull()
  expect(within(oneCard as HTMLElement).getByRole('link', { name: /Open Comic Handoff/i })).toHaveAttribute(
    'href',
    '/comic?production_episode_id=prod-ep-2&mode=open_current',
  )
  expect(within(oneCard as HTMLElement).getByRole('link', { name: /Open Animation Track/i })).toHaveAttribute(
    'href',
    '/sequences?production_episode_id=prod-ep-2&mode=open_current',
  )
})

test('shows duplicate-track warnings and keeps open_current mode when track counts are ambiguous', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([])
  vi.mocked(listProductionSeries).mockResolvedValue([])
  vi.mocked(listProductionEpisodes).mockResolvedValue([
    buildEpisode({
      id: 'prod-ep-3',
      title: 'Ambiguous Track Episode',
      comic_track_count: 2,
      animation_track_count: 3,
      comic_track: null,
      animation_track: null,
    }),
  ])

  renderPage()
  expect(await screen.findByText(/Ambiguous Track Episode/i)).toBeInTheDocument()

  expect(screen.getByText(/Comic track count is 2; review duplicate links before final handoff/i)).toBeInTheDocument()
  expect(screen.getByText(/Animation track count is 3; review duplicate links before final handoff/i)).toBeInTheDocument()

  const ambiguousCard = screen.getByRole('heading', { name: /Ambiguous Track Episode/i }).closest('article')
  expect(ambiguousCard).not.toBeNull()
  expect(within(ambiguousCard as HTMLElement).getByRole('link', { name: /Open Comic Handoff/i })).toHaveAttribute(
    'href',
    '/comic?production_episode_id=prod-ep-3&mode=open_current',
  )
  expect(within(ambiguousCard as HTMLElement).getByRole('link', { name: /Open Animation Track/i })).toHaveAttribute(
    'href',
    '/sequences?production_episode_id=prod-ep-3&mode=open_current',
  )
})
