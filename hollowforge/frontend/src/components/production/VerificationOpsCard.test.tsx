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
    'Run Preflight',
    'Run Comic Verification Suite',
    'Rerun Full Only',
    'Rerun Remote Only',
  ])

  expect(screen.getByText(/Run Preflight first, then run the full suite/i)).toBeInTheDocument()
  expect(screen.getByText('docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md')).toBeInTheDocument()
})

test('copies the requested command and SOP path', async () => {
  render(<VerificationOpsCard />)

  fireEvent.click(screen.getByRole('button', { name: /Copy Command Run Preflight/i }))

  await waitFor(() => {
    expect(writeTextMock).toHaveBeenCalledWith(expect.stringContaining('check_comic_remote_render_preflight.py'))
  })
  expect(notify.success).toHaveBeenCalledWith('Run Preflight copied')

  fireEvent.click(screen.getByRole('button', { name: /Copy SOP Path/i }))

  await waitFor(() => {
    expect(writeTextMock).toHaveBeenCalledWith('docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md')
  })
  expect(notify.success).toHaveBeenCalledWith('SOP path copied')
})
