import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'

import Marketing from './Marketing'

vi.mock('../components/tools/CaptionGenerator', () => ({
  default: () => <div data-testid="caption-generator">CaptionGeneratorMock</div>,
}))

vi.mock('../components/publishing/PublishingPilotWorkbench', () => ({
  default: ({ generationIds }: { generationIds: string[] }) => (
    <div data-testid="publishing-workbench">{generationIds.join(',')}</div>
  ),
}))

function renderPage(initialEntry = '/marketing') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Marketing />
    </MemoryRouter>,
  )
}

test('renders the caption tool state when no ready batch is selected', async () => {
  renderPage()

  expect(await screen.findByRole('heading', { name: /Marketing Automation Tool/i })).toBeInTheDocument()
  expect(screen.getByText(/No ready batch selected/i)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Back to \/ready/i })).toHaveAttribute('href', '/ready')
  expect(screen.getByTestId('caption-generator')).toBeInTheDocument()
  expect(screen.queryByTestId('publishing-workbench')).not.toBeInTheDocument()
})

test('renders the publishing workbench when generation ids are present', async () => {
  renderPage('/marketing?generation_id=gen-1&generation_id=gen-2')

  expect(await screen.findByRole('heading', { name: /Publishing Pilot Workbench/i })).toBeInTheDocument()
  expect(screen.getByTestId('publishing-workbench')).toHaveTextContent('gen-1,gen-2')
  expect(screen.queryByTestId('caption-generator')).not.toBeInTheDocument()
})
