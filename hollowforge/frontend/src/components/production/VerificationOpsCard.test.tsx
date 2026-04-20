import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import { notify } from '../../lib/toast'
import VerificationOpsCard from './VerificationOpsCard'

vi.mock('../../lib/toast', () => ({
  notify: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

const writeTextMock = vi.fn()

beforeEach(() => {
  writeTextMock.mockReset()
  writeTextMock.mockResolvedValue(undefined)
  Object.defineProperty(globalThis.navigator, 'clipboard', {
    configurable: true,
    value: {
      writeText: writeTextMock,
    },
  })
})

test('renders verification commands in canonical order', () => {
  render(<VerificationOpsCard />)

  const headings = screen.getAllByRole('heading', { level: 3 })
  expect(headings.map((node) => node.textContent)).toEqual([
    'Launch Worktree Handoff Stack',
    'Run Production Hub Verification Suite',
    'Rerun Smoke Only',
    'Rerun UI Only',
  ])

  expect(
    screen.getByText(/Launch the worktree stack first, then run the full production-hub suite/i),
  ).toBeInTheDocument()
  expect(
    screen.getByText('docs/HOLLOWFORGE_PRODUCTION_HUB_VERIFICATION_SOP_20260419.md'),
  ).toBeInTheDocument()
})

test('copies the requested command and SOP path', async () => {
  render(<VerificationOpsCard />)

  fireEvent.click(
    screen.getByRole('button', { name: /Copy Command Launch Worktree Handoff Stack/i }),
  )

  await waitFor(() => {
    expect(writeTextMock).toHaveBeenCalledWith(
      expect.stringContaining('./scripts/run-worktree-handoff-stack.sh'),
    )
  })
  expect(notify.success).toHaveBeenCalledWith('Launch Worktree Handoff Stack copied')

  fireEvent.click(screen.getByRole('button', { name: /Copy SOP Path/i }))

  await waitFor(() => {
    expect(writeTextMock).toHaveBeenCalledWith(
      'docs/HOLLOWFORGE_PRODUCTION_HUB_VERIFICATION_SOP_20260419.md',
    )
  })
  expect(notify.success).toHaveBeenCalledWith('SOP path copied')
})
