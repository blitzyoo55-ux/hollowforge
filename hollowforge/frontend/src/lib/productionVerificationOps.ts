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
