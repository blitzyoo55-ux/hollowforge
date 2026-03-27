import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import {
  cancelAllQueued,
  cancelGeneration,
  getQueueSummary,
} from '../api/client'
import { toast } from 'sonner'
import QueuePage from './QueuePage'

vi.mock('../api/client', () => ({
  cancelAllQueued: vi.fn(),
  cancelGeneration: vi.fn(),
  getQueueSummary: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
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
  const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

  const utils = render(
    <QueryClientProvider client={queryClient}>
      <QueuePage />
    </QueryClientProvider>,
  )

  return { ...utils, invalidateSpy }
}

beforeEach(() => {
  vi.clearAllMocks()
})

test('renders the empty queue state when no items are active', async () => {
  vi.mocked(getQueueSummary).mockResolvedValue({
    total_queued: 0,
    total_running: 0,
    total_active: 0,
    avg_generation_sec: 0,
    estimated_remaining_sec: 0,
    oldest_queued_at: null,
    queue_items: [],
  })

  renderPage()

  expect(await screen.findByRole('heading', { level: 1, name: /^Queue$/i })).toBeInTheDocument()
  expect(screen.getByText(/Queue is empty/i)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Cancel All Queued/i })).not.toBeInTheDocument()
})

test('cancels a single queue item and invalidates queue queries', async () => {
  vi.mocked(getQueueSummary).mockResolvedValue({
    total_queued: 1,
    total_running: 1,
    total_active: 2,
    avg_generation_sec: 33,
    estimated_remaining_sec: 88,
    oldest_queued_at: '2026-03-27T00:00:00+00:00',
    queue_items: [
      {
        id: 'queue-1',
        status: 'queued',
        position: 1,
        checkpoint: 'waiIllustriousSDXL_v160.safetensors',
        loras: [],
        prompt: 'queue prompt one',
        steps: 28,
        cfg: 5.4,
        width: 832,
        height: 1216,
        sampler: 'euler_a',
        tags: ['smoke'],
        notes: 'queue note',
        created_at: '2026-03-27T00:00:00+00:00',
        estimated_start_sec: 12,
        estimated_done_sec: 55,
      },
    ],
  })
  vi.mocked(cancelGeneration).mockResolvedValue(undefined)

  const { invalidateSpy } = renderPage()

  expect(await screen.findByText(/queue prompt one/i)).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /^Cancel$/i }))

  await waitFor(() => {
    expect(cancelGeneration).toHaveBeenCalledTimes(1)
    expect(vi.mocked(cancelGeneration).mock.calls[0]?.[0]).toBe('queue-1')
  })

  await waitFor(() => {
    expect(toast.success).toHaveBeenCalledWith('Generation cancelled')
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['queue-summary'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['active-generations'] })
  })
})

test('cancels all queued items and shows the cancelled count', async () => {
  vi.mocked(getQueueSummary).mockResolvedValue({
    total_queued: 2,
    total_running: 0,
    total_active: 2,
    avg_generation_sec: 30,
    estimated_remaining_sec: 70,
    oldest_queued_at: '2026-03-27T00:00:00+00:00',
    queue_items: [
      {
        id: 'queue-1',
        status: 'queued',
        position: 1,
        checkpoint: 'waiIllustriousSDXL_v160.safetensors',
        loras: [],
        prompt: 'queue prompt one',
        steps: 28,
        cfg: 5.4,
        width: 832,
        height: 1216,
        sampler: 'euler_a',
        tags: null,
        notes: null,
        created_at: '2026-03-27T00:00:00+00:00',
        estimated_start_sec: 10,
        estimated_done_sec: 40,
      },
      {
        id: 'queue-2',
        status: 'queued',
        position: 2,
        checkpoint: 'prefectIllustriousXL_v70.safetensors',
        loras: [],
        prompt: 'queue prompt two',
        steps: 30,
        cfg: 6.0,
        width: 832,
        height: 1216,
        sampler: 'euler',
        tags: null,
        notes: null,
        created_at: '2026-03-27T00:01:00+00:00',
        estimated_start_sec: 20,
        estimated_done_sec: 70,
      },
    ],
  })
  vi.mocked(cancelAllQueued).mockResolvedValue({ cancelled: 2 })

  const { invalidateSpy } = renderPage()

  expect(await screen.findByRole('button', { name: /Cancel All Queued/i })).toBeInTheDocument()

  fireEvent.click(screen.getByRole('button', { name: /Cancel All Queued/i }))

  await waitFor(() => {
    expect(cancelAllQueued).toHaveBeenCalledTimes(1)
  })

  await waitFor(() => {
    expect(toast.success).toHaveBeenCalledWith('Cancelled 2 queued items')
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['queue-summary'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['active-generations'] })
  })
})
