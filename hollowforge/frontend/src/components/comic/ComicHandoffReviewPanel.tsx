import EmptyState from '../EmptyState'
import type {
  ComicEpisodeDetailResponse,
  ComicHandoffExportSummaryResponse,
  ComicHandoffIssueResponse,
  ComicHandoffPageSummaryResponse,
  ComicHandoffValidationResponse,
} from '../../api/client'

interface ComicHandoffReviewPanelProps {
  episode: ComicEpisodeDetailResponse | null
  validation: ComicHandoffValidationResponse | null
  pageSummaries: ComicHandoffPageSummaryResponse[]
  layeredManifestPath: string | null
  handoffValidationPath: string | null
  latestExportSummary: ComicHandoffExportSummaryResponse | null
  canExport: boolean
  readinessMessage: string | null
  isExporting: boolean
  isActive: boolean
  onExport: (episodeId: string) => void
}

function issueLabel(issue: ComicHandoffIssueResponse): string {
  return issue.message?.trim() || issue.code?.trim() || 'Review required'
}

function statusTone(status: ComicHandoffPageSummaryResponse['art_layer_status']): string {
  switch (status) {
    case 'complete':
      return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
    case 'warning':
      return 'border-amber-500/30 bg-amber-500/10 text-amber-200'
    case 'blocked':
      return 'border-rose-500/30 bg-rose-500/10 text-rose-200'
    default:
      return 'border-gray-700 bg-gray-900 text-gray-200'
  }
}

function formatLayerLabel(label: string, status: ComicHandoffPageSummaryResponse['art_layer_status']): string {
  return `${label} ${status}`
}

type ChecklistStatus = 'ready' | 'blocked'

function checklistTone(status: ChecklistStatus): string {
  return status === 'ready'
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
    : 'border-rose-500/30 bg-rose-500/10 text-rose-200'
}

function checklistLabel(status: ChecklistStatus): string {
  return status === 'ready' ? 'Ready' : 'Blocked'
}

export default function ComicHandoffReviewPanel({
  episode,
  validation,
  pageSummaries,
  layeredManifestPath,
  handoffValidationPath,
  latestExportSummary,
  canExport,
  readinessMessage,
  isExporting,
  isActive,
  onExport,
}: ComicHandoffReviewPanelProps) {
  const hardBlockCount = validation?.hard_blocks.length ?? 0
  const softWarningCount = validation?.soft_warnings.length ?? 0
  const layeredManifestChecklistStatus: ChecklistStatus = layeredManifestPath ? 'ready' : 'blocked'
  const validationArtifactChecklistStatus: ChecklistStatus = handoffValidationPath ? 'ready' : 'blocked'
  const hardBlocksChecklistStatus: ChecklistStatus = hardBlockCount === 0 ? 'ready' : 'blocked'
  const pageSummaryChecklistStatus: ChecklistStatus = pageSummaries.length > 0 ? 'ready' : 'blocked'
  const checklistItems = [
    {
      label: 'Layered manifest present',
      status: layeredManifestChecklistStatus,
      detail: layeredManifestPath ?? 'Run page assembly to generate the layered manifest.',
    },
    {
      label: 'Validation artifact present',
      status: validationArtifactChecklistStatus,
      detail: handoffValidationPath ?? 'Run page assembly to generate the validation artifact.',
    },
    {
      label: 'Hard blocks clear',
      status: hardBlocksChecklistStatus,
      detail: hardBlockCount === 0
        ? 'No hard blocks detected in handoff validation.'
        : `${hardBlockCount} hard block${hardBlockCount === 1 ? '' : 's'} must be resolved before export.`,
    },
    {
      label: 'Page summaries ready for review/export',
      status: pageSummaryChecklistStatus,
      detail: pageSummaries.length > 0
        ? `${pageSummaries.length} page summary${pageSummaries.length === 1 ? '' : 'ies'} available for operator review.`
        : 'Assemble pages to generate reviewable page summaries.',
    },
  ]

  return (
    <section
      className={[
        'space-y-5 rounded-2xl border bg-gray-900/70 p-5 transition',
        isActive ? 'border-emerald-500/40 shadow-[0_0_0_1px_rgba(16,185,129,0.18)]' : 'border-gray-800',
      ].join(' ')}
    >
      <div className="space-y-2">
        <span className="inline-flex rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-emerald-300">
          Handoff
        </span>
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Handoff Review</h2>
          <p className="mt-1 text-sm text-gray-400">
            Review layered package readiness, validation output, and export only when hard blocks are clear.
          </p>
        </div>
      </div>

      {!episode ? (
        <EmptyState
          title="No handoff review yet"
          description="Assemble pages first so the layered manifest and validation package can be reviewed before export."
        />
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
              <p className="text-xs uppercase tracking-wide text-gray-500">Workflow</p>
              <p className="mt-2 text-sm font-medium text-gray-100">Assemble -&gt; Handoff Review -&gt; Export</p>
            </div>
            <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
              <p className="text-xs uppercase tracking-wide text-gray-500">Pages</p>
              <p className="mt-2 text-2xl font-semibold text-gray-100">{pageSummaries.length}</p>
            </div>
            <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4">
              <p className="text-xs uppercase tracking-wide text-rose-200">Hard Blocks</p>
              <p className="mt-2 text-2xl font-semibold text-gray-100">{hardBlockCount}</p>
            </div>
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
              <p className="text-xs uppercase tracking-wide text-amber-200">Warnings</p>
              <p className="mt-2 text-2xl font-semibold text-gray-100">{softWarningCount}</p>
            </div>
          </div>

          {readinessMessage && (
            <p className="text-xs text-emerald-200/80">{readinessMessage}</p>
          )}

          <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4 text-sm text-gray-200">
            <p className="text-xs uppercase tracking-wide text-gray-500">Artifacts</p>
            <div className="mt-2 space-y-1">
              {layeredManifestPath && (
                <p className="break-all">
                  <span className="text-gray-100">Layered manifest:</span> {layeredManifestPath}
                </p>
              )}
              {handoffValidationPath && (
                <p className="break-all">
                  <span className="text-gray-100">Validation artifact:</span> {handoffValidationPath}
                </p>
              )}
            </div>
          </div>

          <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
            <p className="text-xs uppercase tracking-wide text-gray-500">Export Checklist</p>
            <div className="mt-3 space-y-3">
              {checklistItems.map((item) => (
                <div
                  key={item.label}
                  className="flex flex-col gap-2 rounded-xl border border-gray-800 bg-gray-900/70 p-3 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-100">{item.label}</p>
                    <p className="mt-1 text-xs text-gray-400">{item.detail}</p>
                  </div>
                  <span className={`inline-flex w-fit rounded-full border px-2.5 py-1 text-xs font-medium uppercase tracking-wide ${checklistTone(item.status)}`}>
                    {checklistLabel(item.status)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {pageSummaries.length > 0 && (
            <div className="space-y-3">
              {pageSummaries.map((pageSummary) => (
                <article key={pageSummary.page_id} className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-gray-500">Page {pageSummary.page_no}</p>
                      <p className="mt-1 text-sm text-gray-300">
                        {pageSummary.hard_block_count} hard block{pageSummary.hard_block_count === 1 ? '' : 's'} · {pageSummary.soft_warning_count} warning{pageSummary.soft_warning_count === 1 ? '' : 's'}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs font-medium">
                    <span className={`rounded-full border px-2.5 py-1 ${statusTone(pageSummary.art_layer_status)}`}>
                      {formatLayerLabel('Art layer', pageSummary.art_layer_status)}
                    </span>
                    <span className={`rounded-full border px-2.5 py-1 ${statusTone(pageSummary.frame_layer_status)}`}>
                      {formatLayerLabel('Frame layer', pageSummary.frame_layer_status)}
                    </span>
                    <span className={`rounded-full border px-2.5 py-1 ${statusTone(pageSummary.balloon_layer_status)}`}>
                      {formatLayerLabel('Balloon layer', pageSummary.balloon_layer_status)}
                    </span>
                    <span className={`rounded-full border px-2.5 py-1 ${statusTone(pageSummary.text_draft_layer_status)}`}>
                      {formatLayerLabel('Text draft layer', pageSummary.text_draft_layer_status)}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          )}

          {(validation?.hard_blocks.length || validation?.soft_warnings.length) ? (
            <div className="grid gap-4 lg:grid-cols-2">
              {validation?.hard_blocks.length ? (
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-4">
                  <p className="text-xs uppercase tracking-wide text-rose-200">Hard Blocks</p>
                  <ul className="mt-2 space-y-1 text-sm text-gray-100">
                    {validation.hard_blocks.map((issue, index) => (
                      <li key={`${issue.code ?? 'hard'}-${index}`}>{issueLabel(issue)}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {validation?.soft_warnings.length ? (
                <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4">
                  <p className="text-xs uppercase tracking-wide text-amber-200">Warnings</p>
                  <ul className="mt-2 space-y-1 text-sm text-gray-100">
                    {validation.soft_warnings.map((issue, index) => (
                      <li key={`${issue.code ?? 'warn'}-${index}`}>{issueLabel(issue)}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => onExport(episode.episode.id)}
              disabled={!canExport || isExporting}
              className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2.5 text-sm font-medium text-emerald-200 transition hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isExporting ? 'Exporting...' : 'Export Handoff ZIP'}
            </button>
            {hardBlockCount > 0 ? (
              <p className="self-center text-sm text-rose-200">
                Resolve {hardBlockCount} hard block{hardBlockCount === 1 ? '' : 's'} before export.
              </p>
            ) : softWarningCount > 0 ? (
              <p className="self-center text-sm text-amber-200">
                Warning-only state detected. Export is still available.
              </p>
            ) : (
              <p className="self-center text-sm text-emerald-200">
                No hard blocks detected. Export is available.
              </p>
            )}
          </div>

          {latestExportSummary && (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
              <p className="text-xs uppercase tracking-wide text-emerald-200">Latest Export</p>
              <div className="mt-2 space-y-1 text-sm text-gray-100">
                <p className="break-all">
                  <span className="text-emerald-100">Export ZIP:</span> {latestExportSummary.export_zip_path}
                </p>
                <p className="break-all">
                  <span className="text-emerald-100">Layered manifest:</span> {latestExportSummary.layered_manifest_path}
                </p>
                <p className="break-all">
                  <span className="text-emerald-100">Validation artifact:</span> {latestExportSummary.handoff_validation_path}
                </p>
              </div>
              <p className="mt-2 text-xs text-emerald-100">
                {latestExportSummary.page_count} pages · {latestExportSummary.hard_block_count} hard blocks · {latestExportSummary.soft_warning_count} warnings
              </p>
            </div>
          )}
        </>
      )}
    </section>
  )
}
