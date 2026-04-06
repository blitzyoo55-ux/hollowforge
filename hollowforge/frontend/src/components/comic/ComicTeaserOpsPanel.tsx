import EmptyState from '../EmptyState'
import type {
  AnimationJobResponse,
  AnimationReconciliationResponse,
  ComicScenePanelResponse,
} from '../../api/client'

interface ComicTeaserOpsPanelProps {
  selectedPanel: ComicScenePanelResponse | null
  selectedAssetPath: string | null
  selectedAssetGenerationId: string | null
  selectedAssetOutputHref: string | null
  jobs: AnimationJobResponse[]
  jobsErrorMessage: string | null
  latestFailedJob: AnimationJobResponse | null
  latestSuccessfulJob: AnimationJobResponse | null
  latestSuccessfulJobHref: string | null
  latestReconcileSummary: AnimationReconciliationResponse | null
  latestLaunchedTeaserJobId: string | null
  presetId: string
  canRerun: boolean
  readinessMessage: string | null
  isReconciling: boolean
  isRerunning: boolean
  onReconcile: () => void
  onRerun: () => void
}

function formatJobTimestamp(job: AnimationJobResponse): string {
  return job.completed_at ?? job.updated_at ?? job.submitted_at ?? job.created_at
}

function resolveOutputHref(outputPath: string | null): string | null {
  const trimmed = outputPath?.trim()
  if (!trimmed) return null
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (trimmed.startsWith('/data/')) return trimmed
  if (trimmed.startsWith('/')) return `/data${trimmed}`
  return `/data/${trimmed}`
}

function isMp4OutputPath(outputPath: string | null): boolean {
  const trimmed = outputPath?.trim()
  return Boolean(trimmed && /\.mp4(?:$|\?)/i.test(trimmed))
}

function derivePresetSummary(job: AnimationJobResponse): string | null {
  const requestJson = job.request_json
  if (!requestJson || typeof requestJson !== 'object') return null

  const backendFamily = typeof requestJson.backend_family === 'string'
    ? requestJson.backend_family.trim()
    : ''
  const modelProfile = typeof requestJson.model_profile === 'string'
    ? requestJson.model_profile.trim()
    : ''

  if (backendFamily && modelProfile) return `${backendFamily} · ${modelProfile}`
  if (modelProfile) return modelProfile
  if (backendFamily) return backendFamily
  return null
}

export default function ComicTeaserOpsPanel({
  selectedPanel,
  selectedAssetPath,
  selectedAssetGenerationId,
  selectedAssetOutputHref,
  jobs,
  jobsErrorMessage,
  latestFailedJob,
  latestSuccessfulJob,
  latestSuccessfulJobHref,
  latestReconcileSummary,
  latestLaunchedTeaserJobId,
  presetId,
  canRerun,
  readinessMessage,
  isReconciling,
  isRerunning,
  onReconcile,
  onRerun,
}: ComicTeaserOpsPanelProps) {
  const latestSuccessfulPresetSummary = latestSuccessfulJob
    ? derivePresetSummary(latestSuccessfulJob)
    : null

  return (
    <section className="space-y-5 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="space-y-2">
        <span className="inline-flex rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-emerald-300">
          Teaser Operations
        </span>
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Teaser Ops For Selected Render</h2>
          <p className="mt-1 text-sm text-gray-400">
            Inspect recent teaser animation jobs, reconcile stale remote worker state, and rerun the default teaser preset from the current winning render.
          </p>
        </div>
      </div>

      {selectedPanel ? (
        <>
          <div className="grid gap-3 rounded-2xl border border-gray-800 bg-gray-950/60 p-4 text-sm text-gray-300 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Scene / Panel</p>
              <p className="mt-1 font-medium text-gray-100">Panel {selectedPanel.panel_no}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Selected Asset</p>
              <p className="mt-1 break-all font-medium text-gray-100">
                {selectedAssetPath ?? 'No selected render yet'}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Teaser Preset</p>
              <p className="mt-1 font-medium text-gray-100">{presetId}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Generation</p>
              <p className="mt-1 break-all font-medium text-gray-100">
                {selectedAssetGenerationId ?? 'Not ready'}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onReconcile}
              disabled={isReconciling}
              className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isReconciling ? 'Reconciling...' : 'Reconcile Stale Animation Jobs'}
            </button>
            <button
              type="button"
              onClick={onRerun}
              disabled={!canRerun || isRerunning}
              className="rounded-xl border border-emerald-500/40 bg-gray-950/80 px-4 py-2.5 text-sm font-medium text-gray-100 transition hover:border-emerald-500/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isRerunning ? 'Launching...' : 'Rerun Teaser From Selected Panel'}
            </button>
          </div>

          {readinessMessage && (
            <p className="text-xs text-emerald-100/80">{readinessMessage}</p>
          )}

          {latestReconcileSummary && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-emerald-200">Latest Reconcile Summary</p>
              <p className="mt-2 text-sm font-medium text-gray-100">
                checked {latestReconcileSummary.checked} · updated {latestReconcileSummary.updated} · failed_restart {latestReconcileSummary.failed_restart}
              </p>
              <p className="mt-1 text-xs text-emerald-100">
                completed {latestReconcileSummary.completed} · cancelled {latestReconcileSummary.cancelled} · skipped_unreachable {latestReconcileSummary.skipped_unreachable}
              </p>
            </div>
          )}

          {latestLaunchedTeaserJobId && (
            <div className="rounded-2xl border border-sky-500/30 bg-sky-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-sky-200">Latest Teaser Launch</p>
              <p className="mt-2 break-all text-sm font-medium text-gray-100">{latestLaunchedTeaserJobId}</p>
            </div>
          )}

          {latestSuccessfulJob && latestSuccessfulJobHref && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-emerald-200">Latest Successful MP4</p>
              <p className="mt-2 text-sm font-medium text-gray-100">{latestSuccessfulJob.id}</p>
              <p className="mt-1 text-xs text-gray-500">
                {formatJobTimestamp(latestSuccessfulJob)} · {latestSuccessfulJob.executor_mode}
              </p>
              {latestSuccessfulPresetSummary && (
                <p className="mt-2 text-xs text-emerald-100">
                  {latestSuccessfulPresetSummary}
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-3">
                <a
                  href={latestSuccessfulJobHref}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-xl border border-emerald-500/40 bg-gray-950/80 px-4 py-2 text-sm font-medium text-emerald-100 transition hover:border-emerald-400 hover:text-white"
                >
                  Open Latest MP4
                </a>
                {selectedAssetOutputHref && (
                  <a
                    href={selectedAssetOutputHref}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-xl border border-gray-700 bg-gray-950/80 px-4 py-2 text-sm font-medium text-gray-200 transition hover:border-emerald-500/40 hover:text-white"
                  >
                    Open Selected Render
                  </a>
                )}
              </div>
            </div>
          )}

          {latestFailedJob && latestFailedJob.error_message?.trim() && (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-rose-200">Latest Failed Teaser Job</p>
              <p className="mt-2 text-sm font-medium text-gray-100">{latestFailedJob.id}</p>
              <p className="mt-1 text-xs text-gray-500">
                {formatJobTimestamp(latestFailedJob)} · {latestFailedJob.executor_mode}
              </p>
              <p className="mt-3 text-sm text-rose-100">{latestFailedJob.error_message}</p>
            </div>
          )}

          {jobsErrorMessage ? (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-rose-200">Teaser Jobs Unavailable</p>
              <p className="mt-2 text-sm text-rose-100">{jobsErrorMessage}</p>
            </div>
          ) : jobs.length > 0 ? (
            <div className="space-y-3">
              {jobs.map((job) => {
                const jobOutputHref = isMp4OutputPath(job.output_path)
                  ? resolveOutputHref(job.output_path)
                  : null

                return (
                  <article key={job.id} className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[11px] uppercase tracking-wide text-gray-300">
                        {job.status}
                      </span>
                      <span className="text-xs text-gray-500">{job.executor_mode}</span>
                      <span className="text-xs text-gray-500">{formatJobTimestamp(job)}</span>
                    </div>
                    <p className="mt-2 break-all text-sm font-medium text-gray-100">{job.id}</p>
                    <p className="mt-1 text-xs text-gray-500">
                      {job.external_job_id ?? 'No external worker job id'}{job.target_tool ? ` · ${job.target_tool}` : ''}
                    </p>
                    {job.error_message?.trim() && (
                      <p className="mt-2 text-sm text-rose-100">{job.error_message}</p>
                    )}
                    <div className="mt-3 flex flex-wrap gap-3">
                      {jobOutputHref && (
                        <a
                          href={jobOutputHref}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm font-medium text-emerald-300 hover:text-emerald-200"
                        >
                          Open Output MP4
                        </a>
                      )}
                      {job.external_job_url?.trim() && (
                        <a
                          href={job.external_job_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm font-medium text-sky-300 hover:text-sky-200"
                        >
                          Open Worker Job
                        </a>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <EmptyState
              title="No teaser jobs for the current selected render"
              description="Select and materialize a winning render to inspect selected-asset-scoped teaser history and rerun the default preset."
            />
          )}
        </>
      ) : (
        <EmptyState
          title="Select a panel first"
          description="Teaser ops stay pinned to the current selected panel so render lineage and rerun source truth remain explicit."
        />
      )}
    </section>
  )
}
