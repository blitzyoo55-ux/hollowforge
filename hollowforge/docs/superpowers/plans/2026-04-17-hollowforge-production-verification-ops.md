# HollowForge Production Verification Ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a global `Verification Ops` surface to `/production` so operators can copy the canonical comic verification commands without leaving the production hub.

**Architecture:** Keep the operator contract static and local to the frontend. Store the canonical command definitions in a small production-specific helper, render them through a dedicated `VerificationOpsCard` component, and mount that card in `ProductionHub` above the creation forms. Keep the page integration thin, and isolate clipboard behavior in component tests.

**Tech Stack:** React 19, React Router 7, TanStack Query 5, Vitest, Testing Library, Tailwind utility classes

---

## File Map

- Create: `frontend/src/lib/productionVerificationOps.ts`
  - Own the canonical verification command list, execution order copy, and the repo-relative SOP path string.
- Create: `frontend/src/components/production/VerificationOpsCard.tsx`
  - Render the operator card, command blocks, copy buttons, and the SOP path surface.
- Create: `frontend/src/components/production/VerificationOpsCard.test.tsx`
  - Verify copy behavior, visible command ordering, and the SOP path presentation in isolation.
- Modify: `frontend/src/pages/ProductionHub.tsx`
  - Insert the new card into the hero-area flow without entangling it with episode-row actions.
- Modify: `frontend/src/pages/ProductionHub.test.tsx`
  - Assert the `/production` page renders the new global ops surface and keeps the existing shared-core hub behavior intact.

## Implementation Notes

- The verification surface stays global. Do not add per-episode verification buttons.
- The default operator path stays explicit:
  1. `Run Preflight`
  2. `Run Comic Verification Suite`
- `--full-only` and `--remote-only` stay visibly secondary.
- Use the canonical local backend URL in the displayed commands: `http://127.0.0.1:8000`
- Do **not** add backend process execution APIs in this phase.
- Because the frontend cannot reliably open a repo-local Markdown file in the browser, present the SOP as a visible repo-relative path plus a `Copy SOP Path` button instead of shipping a broken browser link.

### Task 1: Define the Static Verification Contract

**Files:**
- Create: `frontend/src/lib/productionVerificationOps.ts`
- Test: `frontend/src/components/production/VerificationOpsCard.test.tsx`

- [ ] **Step 1: Write the failing component test for the expected operator contract**

```tsx
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
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `cd frontend && npm run test -- src/components/production/VerificationOpsCard.test.tsx`

Expected: FAIL because `VerificationOpsCard` and `productionVerificationOps` do not exist yet.

- [ ] **Step 3: Add the static contract helper**

```ts
export type ProductionVerificationOpId = 'preflight' | 'suite' | 'full-only' | 'remote-only'

export type ProductionVerificationOp = {
  id: ProductionVerificationOpId
  label: string
  description: string
  command: string
  priority: 'primary' | 'secondary'
}

export const PRODUCTION_VERIFICATION_OPS: ProductionVerificationOp[] = [
  {
    id: 'preflight',
    label: 'Run Preflight',
    description: 'Confirm the remote still-render lane is reachable before the suite.',
    priority: 'primary',
    command:
      'cd backend\n./.venv/bin/python scripts/check_comic_remote_render_preflight.py --backend-url http://127.0.0.1:8000',
  },
  {
    id: 'suite',
    label: 'Run Comic Verification Suite',
    description: 'Canonical smoke -> full -> remote verification path.',
    priority: 'primary',
    command:
      'cd backend\n./.venv/bin/python scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8000',
  },
  {
    id: 'full-only',
    label: 'Rerun Full Only',
    description: 'Use only after the suite narrows the failure to the full lane.',
    priority: 'secondary',
    command:
      'cd backend\n./.venv/bin/python scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8000 --full-only',
  },
  {
    id: 'remote-only',
    label: 'Rerun Remote Only',
    description: 'Use only after the suite narrows the failure to the remote lane.',
    priority: 'secondary',
    command:
      'cd backend\n./.venv/bin/python scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8000 --remote-only',
  },
]

export const PRODUCTION_VERIFICATION_SOP_PATH = 'docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md'
```

- [ ] **Step 4: Re-run the targeted test to verify the contract is now available**

Run: `cd frontend && npm run test -- src/components/production/VerificationOpsCard.test.tsx`

Expected: FAIL moves forward to missing component-render logic instead of missing data definitions.

- [ ] **Step 5: Commit the contract helper**

```bash
git add frontend/src/lib/productionVerificationOps.ts frontend/src/components/production/VerificationOpsCard.test.tsx
git commit -m "feat: add production verification ops contract"
```

### Task 2: Build the Verification Ops Card

**Files:**
- Create: `frontend/src/components/production/VerificationOpsCard.tsx`
- Modify: `frontend/src/components/production/VerificationOpsCard.test.tsx`

- [ ] **Step 1: Extend the failing test to cover clipboard actions**

```tsx
import { notify } from '../../lib/toast'

vi.mock('../../lib/toast', () => ({
  notify: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

beforeEach(() => {
  vi.stubGlobal('navigator', {
    clipboard: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
  })
})

test('copies the requested command and SOP path', async () => {
  render(<VerificationOpsCard />)

  fireEvent.click(screen.getByRole('button', { name: /Copy Command Run Preflight/i }))
  await waitFor(() => {
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining('check_comic_remote_render_preflight.py'),
    )
  })
  expect(notify.success).toHaveBeenCalledWith('Run Preflight copied')

  fireEvent.click(screen.getByRole('button', { name: /Copy SOP Path/i }))
  await waitFor(() => {
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      'docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md',
    )
  })
})
```

- [ ] **Step 2: Run the component test to verify the copy interaction fails**

Run: `cd frontend && npm run test -- src/components/production/VerificationOpsCard.test.tsx`

Expected: FAIL because the component does not yet render copy buttons or invoke clipboard writes.

- [ ] **Step 3: Implement the isolated card component**

```tsx
async function copyText(value: string, successLabel: string) {
  try {
    await navigator.clipboard.writeText(value)
    notify.success(successLabel)
  } catch {
    notify.error('Clipboard copy failed')
  }
}

export default function VerificationOpsCard() {
  const primary = PRODUCTION_VERIFICATION_OPS.filter((item) => item.priority === 'primary')
  const secondary = PRODUCTION_VERIFICATION_OPS.filter((item) => item.priority === 'secondary')

  return (
    <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-100">Verification Ops</h2>
        <p className="text-sm text-gray-400">
          Run Preflight first, then run the full suite. Use isolated reruns only after the suite narrows the failing lane.
        </p>
      </div>

      {[...primary, ...secondary].map((item) => (
        <article key={item.id} className="mt-4 rounded-xl border border-gray-800 bg-gray-950/70 p-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-gray-100">{item.label}</h3>
            <button
              type="button"
              onClick={() => copyText(item.command, `${item.label} copied`)}
              className="rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-200"
            >
              Copy Command
            </button>
          </div>
          <p className="mt-2 text-sm text-gray-400">{item.description}</p>
          <pre className="mt-3 overflow-x-auto rounded-lg border border-gray-800 bg-black/30 p-3 text-xs text-gray-200">
            <code>{item.command}</code>
          </pre>
        </article>
      ))}

      <div className="mt-4 rounded-xl border border-gray-800 bg-gray-950/70 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-100">Operator SOP</h3>
            <p className="mt-1 text-sm text-gray-400">{PRODUCTION_VERIFICATION_SOP_PATH}</p>
          </div>
          <button
            type="button"
            onClick={() => copyText(PRODUCTION_VERIFICATION_SOP_PATH, 'SOP path copied')}
            className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs font-medium text-gray-200"
          >
            Copy SOP Path
          </button>
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Re-run the component test to verify it passes**

Run: `cd frontend && npm run test -- src/components/production/VerificationOpsCard.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit the component slice**

```bash
git add frontend/src/components/production/VerificationOpsCard.tsx frontend/src/components/production/VerificationOpsCard.test.tsx
git commit -m "feat: add production verification ops card"
```

### Task 3: Mount the Card in `/production`

**Files:**
- Modify: `frontend/src/pages/ProductionHub.tsx`
- Modify: `frontend/src/pages/ProductionHub.test.tsx`
- Test: `frontend/src/components/production/VerificationOpsCard.test.tsx`

- [ ] **Step 1: Add the failing page integration test**

```tsx
test('renders verification ops above the creation forms', async () => {
  vi.mocked(listProductionWorks).mockResolvedValue([])
  vi.mocked(listProductionSeries).mockResolvedValue([])
  vi.mocked(listProductionEpisodes).mockResolvedValue([])

  renderPage()

  expect(await screen.findByRole('heading', { name: /Verification Ops/i })).toBeInTheDocument()
  expect(screen.getByText(/Run Comic Verification Suite/i)).toBeInTheDocument()

  const opsHeading = screen.getByRole('heading', { name: /Verification Ops/i })
  const workHeading = screen.getByRole('heading', { name: /Create Production Work/i })
  expect(opsHeading.compareDocumentPosition(workHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})
```

- [ ] **Step 2: Run the focused page test to verify it fails**

Run: `cd frontend && npm run test -- src/pages/ProductionHub.test.tsx`

Expected: FAIL because `ProductionHub` does not yet render the ops card.

- [ ] **Step 3: Mount the new card in the page shell**

```tsx
import VerificationOpsCard from '../components/production/VerificationOpsCard'

export default function ProductionHub() {
  // existing queries and mutations

  return (
    <div className="space-y-6">
      <section>{/* existing hero */}</section>

      <VerificationOpsCard />

      <section className="grid gap-6 xl:grid-cols-3">
        {/* existing creation forms */}
      </section>

      {/* existing track boundary cards + episode registry */}
    </div>
  )
}
```

- [ ] **Step 4: Run the focused frontend verification set**

Run: `cd frontend && npm run test -- src/components/production/VerificationOpsCard.test.tsx src/pages/ProductionHub.test.tsx`

Expected: PASS

- [ ] **Step 5: Run the broader frontend safety checks**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 6: Commit the page integration**

```bash
git add frontend/src/pages/ProductionHub.tsx frontend/src/pages/ProductionHub.test.tsx
git commit -m "feat: surface verification ops in production hub"
```

### Task 4: Final Verification and Operator Review

**Files:**
- Modify: none
- Test: `frontend/src/components/production/VerificationOpsCard.test.tsx`
- Test: `frontend/src/pages/ProductionHub.test.tsx`

- [ ] **Step 1: Run the complete targeted verification bundle**

Run: `cd frontend && npm run test -- src/components/production/VerificationOpsCard.test.tsx src/pages/ProductionHub.test.tsx`

Expected: PASS

- [ ] **Step 2: Re-run the production hub build verification**

Run: `cd frontend && npm run build`

Expected: PASS

- [ ] **Step 3: Smoke-check the UX manually in the running app**

Run: `cd frontend && npm run dev`

Expected:
- `/production` hero still renders
- `Verification Ops` card appears above the creation forms
- `Copy Command` buttons fire success toasts
- `Copy SOP Path` copies `docs/HOLLOWFORGE_COMIC_OPERATOR_SOP_20260408.md`

- [ ] **Step 4: Commit any final polish if needed**

```bash
git add frontend/src/lib/productionVerificationOps.ts frontend/src/components/production/VerificationOpsCard.tsx frontend/src/components/production/VerificationOpsCard.test.tsx frontend/src/pages/ProductionHub.tsx frontend/src/pages/ProductionHub.test.tsx
git commit -m "test: verify production verification ops flow"
```
