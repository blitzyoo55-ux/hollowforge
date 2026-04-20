import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import { getProductionVerificationSummary } from '../../api/client'
import type { ProductionVerificationRunResponse, ProductionVerificationSummaryResponse } from '../../api/client'
import VerificationHistoryPanel from './VerificationHistoryPanel'

vi.mock('../../api/client', () => ({
  getProductionVerificationSummary: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(getProductionVerificationSummary).mockReset()
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

function buildRun(overrides: Partial<ProductionVerificationRunResponse> = {}): ProductionVerificationRunResponse {
  return {
    id: 'run-1',
    run_mode: 'smoke_only',
    status: 'completed',
    overall_success: true,
    failure_stage: null,
    error_summary: null,
    base_url: 'http://127.0.0.1:8014',
    total_duration_sec: 2.345,
    started_at: '2026-04-19T00:00:00+00:00',
    finished_at: '2026-04-19T00:00:02+00:00',
    stage_status: {},
    created_at: '2026-04-19T00:00:02+00:00',
    updated_at: '2026-04-19T00:00:02+00:00',
    ...overrides,
  }
}

function buildSummary(overrides: Partial<ProductionVerificationSummaryResponse> = {}): ProductionVerificationSummaryResponse {
  return {
    latest_smoke_only: null,
    latest_suite: null,
    recent_runs: [],
    ...overrides,
  }
}

test('renders loading state while verification history is pending', () => {
  vi.mocked(getProductionVerificationSummary).mockImplementation(
    () => new Promise(() => {}),
  )

  renderPanel()

  expect(screen.getByRole('status', { name: /Loading verification history/i })).toBeInTheDocument()
})

test('renders error state when verification history fails to load', async () => {
  vi.mocked(getProductionVerificationSummary).mockRejectedValueOnce(new Error('boom'))

  renderPanel()

  expect(await screen.findByText(/Failed to load production verification history/i)).toBeInTheDocument()
})

test('renders empty state when no verification history exists', async () => {
  vi.mocked(getProductionVerificationSummary).mockResolvedValue(buildSummary())

  renderPanel()

  expect(await screen.findByText(/No verification history yet/i)).toBeInTheDocument()
  expect(screen.getByText(/Run the production hub suite or an isolated rerun/i)).toBeInTheDocument()
})

test('renders latest summary cards and recent runs table', async () => {
  vi.mocked(getProductionVerificationSummary).mockResolvedValue(
    buildSummary({
      latest_smoke_only: buildRun({
        id: 'smoke-1',
        run_mode: 'smoke_only',
        overall_success: true,
      }),
      latest_suite: buildRun({
        id: 'suite-1',
        run_mode: 'suite',
        status: 'failed',
        overall_success: false,
        failure_stage: 'ui',
        error_summary: 'stage ui exited with code 1',
      }),
      recent_runs: [
        buildRun({
          id: 'suite-1',
          run_mode: 'suite',
          status: 'failed',
          overall_success: false,
          failure_stage: 'ui',
          error_summary: 'stage ui exited with code 1',
        }),
        buildRun({
          id: 'ui-1',
          run_mode: 'ui_only',
          status: 'completed',
          overall_success: true,
          failure_stage: null,
          error_summary: null,
        }),
      ],
    }),
  )

  renderPanel()

  const smokeHeading = await screen.findByText('Latest Smoke Only')
  const smokeCard = smokeHeading.closest('article')
  expect(smokeCard).not.toBeNull()
  expect(within(smokeCard as HTMLElement).getByText('smoke only')).toBeInTheDocument()
  expect(within(smokeCard as HTMLElement).getByText('Status')).toBeInTheDocument()
  expect(within(smokeCard as HTMLElement).getByText('Started')).toBeInTheDocument()
  expect(within(smokeCard as HTMLElement).getByText('Finished')).toBeInTheDocument()
  expect(within(smokeCard as HTMLElement).getByText('Duration')).toBeInTheDocument()
  expect(within(smokeCard as HTMLElement).getByText('Failure Stage')).toBeInTheDocument()

  const suiteHeading = screen.getByText('Latest Suite')
  const suiteCard = suiteHeading.closest('article')
  expect(suiteCard).not.toBeNull()
  expect(within(suiteCard as HTMLElement).getByText('suite')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Status')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Started')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Finished')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Duration')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('Failure Stage')).toBeInTheDocument()
  expect(within(suiteCard as HTMLElement).getByText('ui')).toBeInTheDocument()

  expect(screen.getByRole('columnheader', { name: /Started/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Mode/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Status/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Failure Stage/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Duration/i })).toBeInTheDocument()
  expect(screen.getByRole('columnheader', { name: /Error Summary/i })).toBeInTheDocument()

  const recentRunsTable = screen.getByRole('table')
  const suiteRow = within(recentRunsTable).getByText('suite').closest('tr')
  expect(suiteRow).not.toBeNull()
  expect(within(suiteRow as HTMLElement).getByText('ui')).toBeInTheDocument()
  expect(within(suiteRow as HTMLElement).getByText('stage ui exited with code 1')).toBeInTheDocument()

  const uiOnlyRow = within(recentRunsTable).getByText('ui only').closest('tr')
  expect(uiOnlyRow).not.toBeNull()
  expect(within(uiOnlyRow as HTMLElement).getByText('Pass')).toBeInTheDocument()

  await waitFor(() => {
    expect(screen.getAllByRole('row')).toHaveLength(3)
  })
})
