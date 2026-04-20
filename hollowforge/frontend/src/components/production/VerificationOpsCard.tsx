import {
  PRODUCTION_VERIFICATION_OPS,
  PRODUCTION_VERIFICATION_SOP_PATH,
} from '../../lib/productionVerificationOps'
import { notify } from '../../lib/toast'

async function copyText(value: string, successLabel: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    notify.success(successLabel)
  } catch {
    notify.error('Clipboard copy failed')
  }
}

export default function VerificationOpsCard() {
  return (
    <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-gray-100">Verification Ops</h2>
        <p className="text-sm text-gray-400">
          Launch the worktree stack first, then run the full production-hub suite. Use isolated reruns only after the
          suite narrows the failing lane.
        </p>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {PRODUCTION_VERIFICATION_OPS.map((item) => (
          <article key={item.id} className="rounded-xl border border-gray-800 bg-gray-950/70 p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="space-y-2">
                <span
                  className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide ${
                    item.priority === 'primary'
                      ? 'border-violet-500/30 bg-violet-500/10 text-violet-200'
                      : 'border-gray-700 bg-gray-900 text-gray-300'
                  }`}
                >
                  {item.priority === 'primary' ? 'Default Path' : 'Fallback Rerun'}
                </span>
                <h3 className="text-sm font-semibold text-gray-100">{item.label}</h3>
              </div>
              <button
                type="button"
                aria-label={`Copy Command ${item.label}`}
                onClick={() => copyText(item.command, `${item.label} copied`)}
                className="rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-200 transition hover:bg-violet-500/20"
              >
                Copy Command
              </button>
            </div>
            <p className="mt-3 text-sm text-gray-400">{item.description}</p>
            <pre className="mt-3 overflow-x-auto rounded-lg border border-gray-800 bg-black/30 p-3 text-xs text-gray-200">
              <code>{item.command}</code>
            </pre>
          </article>
        ))}
      </div>

      <article className="mt-4 rounded-xl border border-gray-800 bg-gray-950/70 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h4 className="text-sm font-semibold text-gray-100">Operator SOP</h4>
            <p className="mt-2 text-sm text-gray-400">
              Keep the repo-local SOP handy for terminal execution details and failure triage.
            </p>
            <code className="mt-3 block rounded-lg border border-gray-800 bg-black/30 px-3 py-2 text-xs text-gray-200">
              {PRODUCTION_VERIFICATION_SOP_PATH}
            </code>
          </div>
          <button
            type="button"
            aria-label="Copy SOP Path"
            onClick={() => copyText(PRODUCTION_VERIFICATION_SOP_PATH, 'SOP path copied')}
            className="rounded-lg border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs font-medium text-gray-200 transition hover:border-violet-500/40 hover:text-white"
          >
            Copy SOP Path
          </button>
        </div>
      </article>
    </section>
  )
}
