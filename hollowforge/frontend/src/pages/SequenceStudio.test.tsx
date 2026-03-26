import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'

import SequenceStudio from './SequenceStudio'

vi.mock('../api/client', () => ({
  listSequenceBlueprints: vi.fn().mockResolvedValue([]),
  listSequenceRuns: vi.fn().mockResolvedValue([]),
  createSequenceBlueprint: vi.fn(),
  createSequenceRun: vi.fn(),
  getSequenceRun: vi.fn(),
  startSequenceRun: vi.fn(),
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
        <SequenceStudio />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('renders Stage 1 blueprint controls', async () => {
  renderPage()

  expect(await screen.findByRole('heading', { name: /Sequence Studio/i })).toBeInTheDocument()
  expect(screen.getByText(/^Stage 1 Sequence$/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/Content Mode/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/Executor Profile/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Create Blueprint/i })).toBeInTheDocument()
})
