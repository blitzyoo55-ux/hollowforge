import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
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
