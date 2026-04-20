export type ProductionVerificationOpId = 'stack' | 'suite' | 'smoke-only' | 'ui-only'

export type ProductionVerificationOp = {
  id: ProductionVerificationOpId
  label: string
  description: string
  command: string
  priority: 'primary' | 'secondary'
}

export const PRODUCTION_VERIFICATION_OPS: ProductionVerificationOp[] = [
  {
    id: 'stack',
    label: 'Launch Worktree Handoff Stack',
    description: 'Start the bounded alternate-port backend/frontend stack for production-hub verification.',
    priority: 'primary',
    command:
      'cd frontend\n./scripts/run-worktree-handoff-stack.sh',
  },
  {
    id: 'suite',
    label: 'Run Production Hub Verification Suite',
    description: 'Canonical smoke -> ui verification path for the shared production core.',
    priority: 'primary',
    command:
      'cd backend\npython3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014',
  },
  {
    id: 'smoke-only',
    label: 'Rerun Smoke Only',
    description: 'Use only after the suite narrows the failure to the smoke lane.',
    priority: 'secondary',
    command:
      'cd backend\npython3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014 --smoke-only',
  },
  {
    id: 'ui-only',
    label: 'Rerun UI Only',
    description: 'Use only after the suite narrows the failure to the ui lane.',
    priority: 'secondary',
    command:
      'cd backend\npython3 scripts/run_production_hub_verification_suite.py --base-url http://127.0.0.1:8014 --ui-only',
  },
]

export const PRODUCTION_VERIFICATION_SOP_PATH = 'docs/HOLLOWFORGE_PRODUCTION_HUB_VERIFICATION_SOP_20260419.md'
