import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'

import { getPublishingReadiness } from '../api/client'
import Marketing from './Marketing'

vi.mock('../api/client', () => ({
  getPublishingReadiness: vi.fn(),
}))

vi.mock('../components/tools/CaptionGenerator', () => ({
  default: () => <div data-testid="caption-generator">CaptionGeneratorMock</div>,
}))

vi.mock('../components/publishing/PublishingPilotWorkbench', () => ({
  default: ({ generationIds }: { generationIds: string[] }) => (
    <div data-testid="publishing-workbench">{generationIds.join(',')}</div>
  ),
}))

function renderPage(initialEntry = '/marketing') {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Marketing />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('renders the caption tool state when no ready batch is selected', async () => {
  renderPage()

  expect(await screen.findByRole('heading', { name: /Marketing Automation Tool/i })).toBeInTheDocument()
  expect(screen.getByText(/No ready batch selected/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Back to \/ready/i })).toHaveAttribute('href', '/ready')
  expect(screen.getByTestId('caption-generator')).toBeInTheDocument()
  expect(screen.queryByTestId('publishing-workbench')).not.toBeInTheDocument()
  expect(getPublishingReadiness).not.toHaveBeenCalled()
})

test('renders the publishing workbench and draft-only readiness summary when generation ids are present', async () => {
  vi.mocked(getPublishingReadiness).mockResolvedValue({
    caption_generation_ready: false,
    draft_publish_ready: true,
    degraded_mode: 'draft_only',
    provider: 'openrouter',
    model: 'x-ai/grok-2-vision-1212',
    missing_requirements: ['OPENROUTER_API_KEY'],
    notes: [],
  })

  renderPage('/marketing?generation_id=gen-1&generation_id=gen-2')

  expect(await screen.findByRole('heading', { name: /Publishing Pilot Workbench/i })).toBeInTheDocument()
  expect(await screen.findByText(/Draft-only mode/i)).toBeInTheDocument()
  expect(screen.getByText(/OPENROUTER_API_KEY/i)).toBeInTheDocument()
  expect(screen.getByTestId('publishing-workbench')).toHaveTextContent('gen-1,gen-2')
  expect(screen.queryByTestId('caption-generator')).not.toBeInTheDocument()
  expect(getPublishingReadiness).toHaveBeenCalledTimes(1)
})
