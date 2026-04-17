import EmptyState from '../EmptyState'
import type {
  AnimationReconciliationResponse,
  AnimationShotResponse,
  AnimationShotVariantResponse,
  ComicScenePanelResponse,
} from '../../api/client'

interface ComicTeaserOpsPanelProps {
  selectedPanel: ComicScenePanelResponse | null
  selectedAssetPath: string | null
  selectedAssetGenerationId: string | null
  selectedAssetOutputHref: string | null
  currentShot: AnimationShotResponse | null
  currentShotErrorMessage: string | null
  currentShotVariants: AnimationShotVariantResponse[]
  latestFailedVariant: AnimationShotVariantResponse | null
  latestSuccessfulVariant: AnimationShotVariantResponse | null
  latestSuccessfulVariantHref: string | null
  latestReconcileSummary: AnimationReconciliationResponse | null
  latestLaunchedTeaserJobId: string | null
  latestLaunchedTeaserShotId: string | null
  latestLaunchedTeaserVariantId: string | null
  presetId: string
  canRerun: boolean
  readinessMessage: string | null
  isReconciling: boolean
  isRerunning: boolean
  onReconcile: () => void
  onRerun: () => void
}

function formatVariantTimestamp(variant: AnimationShotVariantResponse): string {
  return variant.completed_at ?? variant.created_at
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

export default function ComicTeaserOpsPanel({
  selectedPanel,
  selectedAssetPath,
  selectedAssetGenerationId,
  selectedAssetOutputHref,
  currentShot,
  currentShotErrorMessage,
  currentShotVariants,
  latestFailedVariant,
  latestSuccessfulVariant,
  latestSuccessfulVariantHref,
  latestReconcileSummary,
  latestLaunchedTeaserJobId,
  latestLaunchedTeaserShotId,
  latestLaunchedTeaserVariantId,
  presetId,
  canRerun,
  readinessMessage,
  isReconciling,
  isRerunning,
  onReconcile,
  onRerun,
}: ComicTeaserOpsPanelProps) {
  return (
    <section className="space-y-5 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="space-y-2">
        <span className="inline-flex rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-emerald-300">
          Animation Track Preview
        </span>
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Animation Track Preview For Selected Render</h2>
          <p className="mt-1 text-sm text-gray-400">
            Inspect current shot registry state, reconcile stale remote worker state, and rerun the current animation preview from the winning render.
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
              {isRerunning ? 'Launching...' : 'Rerun Animation Preview From Selected Panel'}
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

          {currentShotErrorMessage && (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-rose-200">Current Teaser Shot Unavailable</p>
              <p className="mt-2 text-sm text-rose-100">{currentShotErrorMessage}</p>
            </div>
          )}

          {currentShot ? (
            <div className="rounded-2xl border border-sky-500/30 bg-sky-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-sky-200">Current Teaser Shot</p>
              <p className="mt-2 break-all text-sm font-medium text-gray-100">{currentShot.id}</p>
              <div className="mt-3 grid gap-3 text-xs text-sky-100 sm:grid-cols-2 xl:grid-cols-4">
                <div>
                  <p className="uppercase tracking-wide text-sky-200/80">Source Kind</p>
                  <p className="mt-1 break-all text-gray-100">{currentShot.source_kind}</p>
                </div>
                <div>
                  <p className="uppercase tracking-wide text-sky-200/80">Episode</p>
                  <p className="mt-1 break-all text-gray-100">{currentShot.episode_id ?? 'Not set'}</p>
                </div>
                <div>
                  <p className="uppercase tracking-wide text-sky-200/80">Selected Render Asset</p>
                  <p className="mt-1 break-all text-gray-100">{currentShot.selected_render_asset_id}</p>
                </div>
                <div>
                  <p className="uppercase tracking-wide text-sky-200/80">Variant Count</p>
                  <p className="mt-1 text-gray-100">{currentShotVariants.length}</p>
                </div>
              </div>
            </div>
          ) : !currentShotErrorMessage ? (
            <EmptyState
              title="No current animation preview yet"
              description="Select and materialize a winning render to load shot registry state and selected-asset-scoped preview history."
            />
          ) : null}

          {latestLaunchedTeaserJobId && (
            <div className="rounded-2xl border border-sky-500/30 bg-sky-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-sky-200">Latest Teaser Launch</p>
              <p className="mt-2 break-all text-sm font-medium text-gray-100">{latestLaunchedTeaserJobId}</p>
              <p className="mt-1 text-xs text-sky-100">
                shot {latestLaunchedTeaserShotId ?? 'n/a'} · variant {latestLaunchedTeaserVariantId ?? 'n/a'}
              </p>
            </div>
          )}

          {latestSuccessfulVariant && latestSuccessfulVariantHref && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-emerald-200">Latest Successful MP4</p>
              <p className="mt-2 text-sm font-medium text-gray-100">{latestSuccessfulVariant.id}</p>
              <p className="mt-1 text-xs text-gray-500">
                {formatVariantTimestamp(latestSuccessfulVariant)} · {latestSuccessfulVariant.status}
              </p>
              <p className="mt-2 text-xs text-emerald-100">
                {latestSuccessfulVariant.preset_id} · {latestSuccessfulVariant.launch_reason} · job {latestSuccessfulVariant.animation_job_id}
              </p>
              <div className="mt-3 flex flex-wrap gap-3">
                <a
                  href={latestSuccessfulVariantHref}
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

          {latestFailedVariant && latestFailedVariant.error_message?.trim() && (
            <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-rose-200">Latest Failed Variant</p>
              <p className="mt-2 text-sm font-medium text-gray-100">{latestFailedVariant.id}</p>
              <p className="mt-1 text-xs text-gray-500">
                {formatVariantTimestamp(latestFailedVariant)} · {latestFailedVariant.status}
              </p>
              <p className="mt-2 text-xs text-rose-100">
                {latestFailedVariant.preset_id} · {latestFailedVariant.launch_reason} · job {latestFailedVariant.animation_job_id}
              </p>
              <p className="mt-3 text-sm text-rose-100">{latestFailedVariant.error_message}</p>
            </div>
          )}

          {currentShot ? (
            <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
              <div className="space-y-1">
                <p className="text-xs uppercase tracking-wide text-gray-500">Recent Variants For Selected Render</p>
                <p className="text-sm text-gray-400">
                  Selected-asset-scoped teaser lineage in newest-first order.
                </p>
              </div>
              {currentShotVariants.length > 0 ? (
                <div className="mt-3 space-y-3">
                {currentShotVariants.map((variant) => {
                  const variantOutputHref = isMp4OutputPath(variant.output_path)
                    ? resolveOutputHref(variant.output_path)
                    : null

                  return (
                    <article key={variant.id} className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[11px] uppercase tracking-wide text-gray-300">
                          {variant.status}
                        </span>
                        <span className="text-xs text-gray-500">{variant.launch_reason}</span>
                        <span className="text-xs text-gray-500">{formatVariantTimestamp(variant)}</span>
                      </div>
                      <p className="mt-2 break-all text-sm font-medium text-gray-100">{variant.id}</p>
                      <p className="mt-1 text-xs text-gray-500">
                        job {variant.animation_job_id} · preset {variant.preset_id}
                      </p>
                      {variant.error_message?.trim() && (
                        <p className="mt-2 text-sm text-rose-100">{variant.error_message}</p>
                      )}
                      <div className="mt-3 flex flex-wrap gap-3">
                        {variantOutputHref && (
                          <a
                            href={variantOutputHref}
                            target="_blank"
                            rel="noreferrer"
                            className="text-sm font-medium text-emerald-300 hover:text-emerald-200"
                          >
                            Open Output MP4
                          </a>
                        )}
                        {selectedAssetOutputHref && variant.status !== 'completed' && (
                          <a
                            href={selectedAssetOutputHref}
                            target="_blank"
                            rel="noreferrer"
                            className="text-sm font-medium text-gray-300 hover:text-gray-100"
                          >
                            Open Selected Render
                          </a>
                        )}
                      </div>
                    </article>
                  )
                })}
              </div>
              ) : (
                <div className="mt-3">
                  <EmptyState
                    title="No teaser variants for the current selected render"
                    description="Run teaser or reconcile to populate the selected-asset-scoped variant history."
                  />
                </div>
              )}
            </div>
          ) : null}
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
