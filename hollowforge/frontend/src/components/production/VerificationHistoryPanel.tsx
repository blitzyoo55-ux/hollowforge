import { useQuery } from '@tanstack/react-query'

import {
  getProductionVerificationSummary,
  type ProductionVerificationRunResponse,
  type ProductionVerificationSummaryResponse,
} from '../../api/client'
import EmptyState from '../EmptyState'

function formatDuration(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—'
  return `${value.toFixed(3)}s`
}

function formatFinishedAt(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

function getRunModeLabel(run: ProductionVerificationRunResponse): string {
  if (run.run_mode === 'smoke_only') return 'smoke only'
  if (run.run_mode === 'ui_only') return 'ui only'
  return run.run_mode
}

function SummaryRunCard({
  title,
  run,
}: {
  title: string
  run: ProductionVerificationRunResponse | null
}) {
  return (
    <article className="rounded-xl border border-gray-800 bg-gray-950/70 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-gray-500">{title}</p>
          <h3 className="mt-1 text-sm font-semibold text-gray-100">
            {run ? getRunModeLabel(run) : 'No run yet'}
          </h3>
        </div>
        {run ? (
          <span
            className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide ${
              run.overall_success
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
            }`}
          >
            {run.overall_success ? 'Pass' : 'Fail'}
          </span>
        ) : null}
      </div>

      {run ? (
        <dl className="mt-4 grid gap-3 text-sm text-gray-300 sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-wide text-gray-500">Status</dt>
            <dd className="mt-1 text-gray-100">{run.status}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-gray-500">Started</dt>
            <dd className="mt-1 text-gray-100">{formatFinishedAt(run.started_at)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-gray-500">Finished</dt>
            <dd className="mt-1 text-gray-100">{formatFinishedAt(run.finished_at)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-gray-500">Duration</dt>
            <dd className="mt-1 text-gray-100">{formatDuration(run.total_duration_sec)}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-gray-500">Failure Stage</dt>
            <dd className="mt-1 text-gray-100">{run.failure_stage ?? '—'}</dd>
          </div>
        </dl>
      ) : (
        <p className="mt-3 text-sm text-gray-400">No summary run has been recorded yet.</p>
      )}
    </article>
  )
}

function RunsTable({ runs }: { runs: ProductionVerificationRunResponse[] }) {
  if (runs.length === 0) {
    return (
      <EmptyState
        title="No verification runs yet"
        description="Run the production hub suite or an isolated rerun to populate history."
      />
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-800">
      <table className="min-w-full divide-y divide-gray-800 text-left text-sm">
        <thead className="bg-gray-950/70 text-[11px] uppercase tracking-wide text-gray-500">
          <tr>
            <th className="px-4 py-3 font-medium">Started</th>
            <th className="px-4 py-3 font-medium">Mode</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Failure Stage</th>
            <th className="px-4 py-3 font-medium">Duration</th>
            <th className="px-4 py-3 font-medium">Error Summary</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800 bg-gray-950/40 text-gray-200">
          {runs.map((run) => (
            <tr key={run.id}>
              <td className="px-4 py-3 text-gray-300">{formatFinishedAt(run.started_at)}</td>
              <td className="px-4 py-3 font-medium text-gray-100">{getRunModeLabel(run)}</td>
              <td className="px-4 py-3">
                <span
                  className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide ${
                    run.overall_success
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                      : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
                  }`}
                >
                  {run.overall_success ? 'Pass' : 'Fail'}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-300">{run.failure_stage ?? '—'}</td>
              <td className="px-4 py-3 text-gray-300">{formatDuration(run.total_duration_sec)}</td>
              <td className="px-4 py-3 text-gray-300">{run.error_summary ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function VerificationHistoryPanel() {
  const summaryQuery = useQuery<ProductionVerificationSummaryResponse>({
    queryKey: ['production-verification-summary'],
    queryFn: () => getProductionVerificationSummary(),
    refetchInterval: 30_000,
  })
  const summary = summaryQuery.data
  const hasRuns =
    Boolean(summary?.latest_smoke_only || summary?.latest_suite || (summary?.recent_runs.length ?? 0) > 0)

  return (
    <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Verification History</h2>
          <p className="text-sm text-gray-400">
            Review the latest smoke-only and suite outcomes alongside the five most recent runs.
          </p>
        </div>
      </div>

      {summaryQuery.isLoading ? (
        <div
          role="status"
          aria-label="Loading verification history"
          className="flex items-center justify-center py-12"
        >
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
        </div>
      ) : summaryQuery.isError ? (
        <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          Failed to load production verification history.
        </div>
      ) : summary && hasRuns ? (
        <div className="mt-4 space-y-5">
          <div className="grid gap-4 xl:grid-cols-2">
            <SummaryRunCard title="Latest Smoke Only" run={summary.latest_smoke_only} />
            <SummaryRunCard title="Latest Suite" run={summary.latest_suite} />
          </div>

          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-100">Recent Runs</h3>
              <p className="text-sm text-gray-400">Most recent five persisted verification runs.</p>
            </div>
            <RunsTable runs={summary.recent_runs} />
          </div>
        </div>
      ) : (
        <div className="mt-4">
          <EmptyState
            title="No verification history yet"
            description="Run the production hub suite or an isolated rerun to start building history."
          />
        </div>
      )}
    </section>
  )
}
