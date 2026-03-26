import type { SequenceRoughCutCandidateResponse } from '../api/client'

interface RoughCutCandidateCardProps {
  candidate: SequenceRoughCutCandidateResponse
}

function formatMetric(value: number | null, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '-'
  return value.toFixed(digits)
}

export default function RoughCutCandidateCard({ candidate }: RoughCutCandidateCardProps) {
  const { rough_cut: roughCut, is_selected: isSelected } = candidate

  return (
    <article className="rounded-xl border border-gray-800 bg-gray-900/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-gray-100">Rough Cut</h4>
            {isSelected && (
              <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
                Selected
              </span>
            )}
          </div>
          <p className="mt-1 text-xs text-gray-500">{roughCut.id}</p>
        </div>
        <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-300">
          {roughCut.output_path ? 'Rendered' : 'Metadata only'}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
        <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Overall</p>
          <p className="mt-1 font-semibold text-gray-100">{formatMetric(roughCut.overall_score)}</p>
        </div>
        <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Story</p>
          <p className="mt-1 font-semibold text-gray-100">{formatMetric(roughCut.story_score)}</p>
        </div>
        <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Continuity</p>
          <p className="mt-1 font-semibold text-gray-100">{formatMetric(roughCut.continuity_score)}</p>
        </div>
        <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Duration</p>
          <p className="mt-1 font-semibold text-gray-100">{formatMetric(roughCut.total_duration_sec, 1)}s</p>
        </div>
      </div>

      <div className="mt-4 space-y-2 text-sm text-gray-400">
        <p>
          <span className="text-gray-500">Output:</span>{' '}
          <span className="break-all text-gray-300">{roughCut.output_path ?? 'Not rendered yet'}</span>
        </p>
        <p>
          <span className="text-gray-500">Updated:</span>{' '}
          <span className="text-gray-300">{new Date(roughCut.updated_at).toLocaleString()}</span>
        </p>
      </div>
    </article>
  )
}
