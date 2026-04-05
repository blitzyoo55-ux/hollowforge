import EmptyState from '../EmptyState'
import type {
  ComicEpisodeDetailResponse,
  ComicManuscriptProfileId,
  ComicPageExportResponse,
  ComicPageLayoutTemplateId,
} from '../../api/client'

interface ComicPageAssemblyPanelProps {
  episode: ComicEpisodeDetailResponse | null
  layoutTemplateId: ComicPageLayoutTemplateId
  manuscriptProfileId: ComicManuscriptProfileId
  exportResult: ComicPageExportResponse | null
  canAssemble: boolean
  canExport: boolean
  readinessMessage: string | null
  isAssembling: boolean
  isExporting: boolean
  onLayoutTemplateChange: (layoutTemplateId: ComicPageLayoutTemplateId) => void
  onManuscriptProfileChange: (manuscriptProfileId: ComicManuscriptProfileId) => void
  onAssemble: (episodeId: string) => void
  onExport: (episodeId: string) => void
}

const MANUSCRIPT_PROFILE_OPTIONS: Array<{
  id: ComicManuscriptProfileId
  label: string
}> = [
  {
    id: 'jp_manga_rightbound_v1',
    label: 'Japanese Manga Right-Bound v1',
  },
]

export default function ComicPageAssemblyPanel({
  episode,
  layoutTemplateId,
  manuscriptProfileId,
  exportResult,
  canAssemble,
  canExport,
  readinessMessage,
  isAssembling,
  isExporting,
  onLayoutTemplateChange,
  onManuscriptProfileChange,
  onAssemble,
  onExport,
}: ComicPageAssemblyPanelProps) {
  return (
    <section className="space-y-5 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="space-y-2">
        <span className="inline-flex rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-sky-300">
          Page Assembly
        </span>
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Japanese Page Layout Handoff</h2>
          <p className="mt-1 text-sm text-gray-400">
            Assemble page previews, inspect per-page order, and export the ZIP handoff package without leaving the current episode context.
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-2 text-sm text-gray-300">
          <label htmlFor="comic-layout-template" className="font-medium text-gray-200">
            Layout Template
          </label>
          <select
            id="comic-layout-template"
            value={layoutTemplateId}
            onChange={(event) => onLayoutTemplateChange(event.target.value as ComicPageLayoutTemplateId)}
            className="w-full min-w-[220px] rounded-xl border border-gray-700 bg-gray-950/70 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-sky-500/50"
          >
            <option value="jp_2x2_v1">jp_2x2_v1</option>
            <option value="jp_3row_v1">jp_3row_v1</option>
          </select>
          <p className="text-xs text-gray-500">Page composition</p>
        </div>

        <div className="space-y-2 text-sm text-gray-300">
          <label htmlFor="comic-manuscript-profile" className="font-medium text-gray-200">
            Manuscript Profile
          </label>
          <select
            id="comic-manuscript-profile"
            value={manuscriptProfileId}
            onChange={(event) => onManuscriptProfileChange(event.target.value as ComicManuscriptProfileId)}
            className="w-full min-w-[220px] rounded-xl border border-gray-700 bg-gray-950/70 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-sky-500/50"
          >
            {MANUSCRIPT_PROFILE_OPTIONS.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-500">Print/handoff intent</p>
        </div>
      </div>

      <p className="text-xs text-sky-200/80">
        Layout template = page composition. Manuscript profile = print/handoff intent.
      </p>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => episode && onAssemble(episode.episode.id)}
          disabled={!episode || !canAssemble || isAssembling}
          className="rounded-xl border border-sky-500/40 bg-sky-500/10 px-4 py-2.5 text-sm font-medium text-sky-200 transition hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isAssembling ? 'Assembling...' : 'Assemble Pages'}
        </button>
        <button
          type="button"
          onClick={() => episode && onExport(episode.episode.id)}
          disabled={!episode || !canExport || isExporting}
          className="rounded-xl border border-gray-700 bg-gray-950/80 px-4 py-2.5 text-sm font-medium text-gray-200 transition hover:border-sky-500/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isExporting ? 'Exporting...' : 'Export Handoff ZIP'}
        </button>
      </div>

      {readinessMessage && (
        <p className="text-xs text-sky-200/80">{readinessMessage}</p>
      )}

      {!episode ? (
        <EmptyState
          title="No episode ready for assembly"
          description="Import a Story Planner payload first. Page previews and ZIP handoff exports are always scoped to the current episode."
        />
      ) : episode.pages.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {episode.pages.map((page) => (
            <article key={page.id} className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-gray-500">Page {page.page_no}</p>
                  <h3 className="mt-1 text-base font-semibold text-gray-100">{page.layout_template_id ?? layoutTemplateId}</h3>
                </div>
                <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[11px] uppercase tracking-wide text-gray-300">
                  {page.export_state}
                </span>
              </div>
              <p className="mt-3 text-sm text-gray-400">Panels {page.ordered_panel_ids.join(', ')}</p>
              <p className="mt-2 break-all text-xs text-gray-500">{page.preview_path}</p>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No assembled pages yet"
          description="Run page assembly to generate preview PNGs and manifest files for the current episode."
        />
      )}

      {exportResult && (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
          <p className="text-xs uppercase tracking-wide text-emerald-200">Latest Export</p>
          <div className="mt-2 space-y-1 text-sm text-gray-100">
            <p className="break-all">
              <span className="text-emerald-100">Export ZIP:</span> {exportResult.export_zip_path}
            </p>
            <p>
              <span className="text-emerald-100">Manuscript Profile:</span> {exportResult.manuscript_profile.id}
            </p>
            <p className="break-all">
              <span className="text-emerald-100">Handoff Readme:</span> {exportResult.handoff_readme_path}
            </p>
            <p className="break-all">
              <span className="text-emerald-100">Production Checklist:</span> {exportResult.production_checklist_path}
            </p>
          </div>
          <p className="mt-2 text-xs text-emerald-100">
            {exportResult.pages.length} pages · manifest {exportResult.manuscript_profile_manifest_path}
          </p>
        </div>
      )}
    </section>
  )
}
