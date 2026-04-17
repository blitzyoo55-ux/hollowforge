import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import { getProductionComicVerificationSummary } from '../../api/client'
import type { ComicVerificationRunResponse, ComicVerificationSummaryResponse } from '../../api/client'
import VerificationHistoryPanel from './VerificationHistoryPanel'

vi.mock('../../api/client', () => ({
  getProductionComicVerificationSummary: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(getProductionComicVerificationSummary).mockReset()
})

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <VerificationHistoryPanel />
    </QueryClientProvider>,
  )
}

function buildRun(overrides: Partial<ComicVerificationRunResponse> = {}): ComicVerificationRunResponse {
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

function buildSummary(overrides: Partial<ComicVerificationSummaryResponse> = {}): ComicVerificationSummaryResponse {
  return {
    latest_preflight: null,
    latest_suite: null,
    recent_runs: [],
    ...overrides,
  }
}

test('renders loading state while verification history is pending', () => {
  vi.mocked(getProductionComicVerificationSummary).mockImplementation(
    () => new Promise(() => {}),
  )

  renderPanel()

  expect(screen.getByRole('status', { name: /Loading verification history/i })).toBeInTheDocument()
})

test('renders error state when verification history fails to load', async () => {
  vi.mocked(getProductionComicVerificationSummary).mockRejectedValueOnce(new Error('boom'))

  renderPanel()

  expect(await screen.findByText(/Failed to load comic verification history/i)).toBeInTheDocument()
})

test('renders empty state when no verification history exists', async () => {
  vi.mocked(getProductionComicVerificationSummary).mockResolvedValue(buildSummary())

  renderPanel()

  expect(await screen.findByText(/No verification history yet/i)).toBeInTheDocument()
  expect(screen.getByText(/Run the preflight check or verification suite/i)).toBeInTheDocument()
})

test('renders latest summary cards and recent runs table', async () => {
  vi.mocked(getProductionComicVerificationSummary).mockResolvedValue(
    buildSummary({
      latest_preflight: buildRun({
        id: 'preflight-1',
        run_mode: 'preflight',
        overall_success: true,
      }),
      latest_suite: buildRun({
        id: 'suite-1',
        run_mode: 'suite',
        status: 'failed',
        overall_success: false,
        failure_stage: 'full',
        error_summary: 'stage full exited with code 1',
      }),
      recent_runs: [
        buildRun({
          id: 'suite-1',
          run_mode: 'full_only',
          status: 'failed',
          overall_success: false,
          failure_stage: 'full',
          error_summary: 'stage full exited with code 1',
        }),
        buildRun({
          id: 'remote-1',
          run_mode: 'remote_only',
          status: 'failed',
          overall_success: false,
          failure_stage: 'remote',
          error_summary: 'stage remote exited with code 2',
        }),
      ],
    }),
  )

  renderPanel()

  const preflightHeading = await screen.findByText('Latest Preflight')
  const preflightCard = preflightHeading.closest('article')
  expect(preflightCard).not.toBeNull()
  expect(within(preflightCard as HTMLElement).getByText('preflight')).toBeInTheDocument()
  expect(within(preflightCard as HTMLElement).getByText('Status')).toBeInTheDocument()
  expect(within(preflightCard as HTMLElement).getByText('Started')).toBeInTheDocument()
  expect(within(preflightCard as HTMLElement).getByText('Finished')).toBeInTheDocument()
  expect(within(preflightCard as HTMLElement).getByText('Duration')).toBeInTheDocument()
  expect(within(preflightCard as HTMLElement).getByText('Failure Stage')).toBeInTheDocument()

  const suiteHeading = screen.getByText('Latest Suite')
  const suiteCard = suiteHeading.closest('article')
  expect(suiteCard).not.toBeNull()
  expect(within(suiteCard as HTMLElement).getByText('suite')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Status')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Started')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Finished')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Duration')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Failure Stage')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('full')).toBeInTheDocument()

  expect(screen.getByRole('columnheader', { name: /Started/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Mode/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Status/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Failure Stage/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Duration/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Error Summary/i })).toBeInTheDocument()

  const fullOnlyRow = screen.getByText('full only').closest('tr')
  expect(fullOnlyRow).not.toBeNull()
  expect(within(fullOnlyRow as HTMLElement).getByText('full')).toBeInTheDocument()
  expect(within(fullOnlyRow as HTMLElement).getByText('stage full exited with code 1')).toBeInTheDocument()

  const remoteOnlyRow = screen.getByText('remote only').closest('tr')
  expect(remoteOnlyRow).not.toBeNull()
  expect(within(remoteOnlyRow as HTMLElement).getByText('remote')).toBeInTheDocument()
  expect(within(remoteOnlyRow as HTMLElement).getByText('stage remote exited with code 2')).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getAllByRole('row')).toHaveLength(3)
  })
})
