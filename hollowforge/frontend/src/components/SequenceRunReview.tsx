import type { SequenceRunDetailResponse, SequenceRunShotDetailResponse } from '../api/client'
import EmptyState from './EmptyState'
import RoughCutCandidateCard from './RoughCutCandidateCard'

interface SequenceRunReviewProps {
  runDetail: SequenceRunDetailResponse | null
  isLoading?: boolean
  isError?: boolean
  isAssembling?: boolean
  onAssembleRoughCut: () => void
}

function formatDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

function shotStatus(shotDetail: SequenceRunShotDetailResponse): {
  label: string
  className: string
} {
  if (shotDetail.clips.some((clip) => clip.clip_path)) {
    return {
      label: 'Clip ready',
      className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    }
  }
  if (shotDetail.anchor_candidates.length > 0) {
    return {
      label: 'Animating',
      className: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
    }
  }
  return {
    label: 'Queued',
    className: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
  }
}

export default function SequenceRunReview({
  runDetail,
  isLoading = false,
  isError = false,
  isAssembling = false,
  onAssembleRoughCut,
}: SequenceRunReviewProps) {
  if (isLoading) {
    return (
      <div className="rounded-2xl border border-gray-800 bg-gray-900/70 p-10">
        <div className="flex items-center justify-center py-10">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <EmptyState
        title="Run review is unavailable"
        description="The selected sequence run could not be loaded."
      />
    )
  }

  if (!runDetail) {
    return (
      <EmptyState
        title="Select a sequence run"
        description="Choose a run from the list to inspect per-shot status and rough-cut candidates."
      />
    )
  }

  return (
    <section className="space-y-6 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-100">Run Review</h2>
            <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-300">
              {runDetail.run.status}
            </span>
          </div>
          <p className="text-sm text-gray-400">
            {runDetail.blueprint.character_id} in {runDetail.blueprint.location_id}
          </p>
          <div className="flex flex-wrap gap-4 text-xs text-gray-500">
            <span>Prompt profile: {runDetail.run.prompt_provider_profile_id}</span>
            <span>Execution: {runDetail.run.execution_mode}</span>
            <span>Created: {formatDate(runDetail.run.created_at)}</span>
          </div>
        </div>

        <button
          type="button"
          onClick={onAssembleRoughCut}
          disabled={isAssembling}
          className="rounded-xl border border-violet-500/40 bg-violet-500/10 px-4 py-2.5 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isAssembling ? 'Assembling...' : 'Assemble Rough Cut'}
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Shots</p>
          <p className="mt-1 text-2xl font-semibold text-gray-100">{runDetail.shots.length}</p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Rough Cuts</p>
          <p className="mt-1 text-2xl font-semibold text-gray-100">{runDetail.rough_cut_candidates.length}</p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Lane</p>
          <p className="mt-1 text-2xl font-semibold text-gray-100">{runDetail.run.content_mode}</p>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Shot Status</h3>
          <p className="text-xs text-gray-500">Candidate counts and clip progress per shot</p>
        </div>
        <div className="space-y-3">
          {runDetail.shots.map((shotDetail) => {
            const status = shotStatus(shotDetail)
            const bestCandidate = shotDetail.anchor_candidates[0]
            const bestClip = shotDetail.clips[0]
            return (
              <article
                key={shotDetail.shot.id}
                className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"
              >
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-0.5 text-xs text-gray-300">
                        Shot {shotDetail.shot.shot_no}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${status.className}`}>
                        {status.label}
                      </span>
                      <span className="text-sm font-medium text-gray-100">{shotDetail.shot.beat_type}</span>
                    </div>
                    <p className="text-sm text-gray-400">{shotDetail.shot.camera_intent}</p>
                    <p className="text-xs text-gray-500">
                      {shotDetail.shot.emotion_intent} / {shotDetail.shot.action_intent}
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm lg:min-w-[240px]">
                    <div className="rounded-lg border border-gray-800 bg-gray-900/80 p-3">
                      <p className="text-[11px] uppercase tracking-wide text-gray-500">Candidates</p>
                      <p className="mt-1 font-semibold text-gray-100">{shotDetail.anchor_candidates.length}</p>
                      <p className="mt-1 text-xs text-gray-500">
                        Best rank {bestCandidate?.rank_score?.toFixed(2) ?? '-'}
                      </p>
                    </div>
                    <div className="rounded-lg border border-gray-800 bg-gray-900/80 p-3">
                      <p className="text-[11px] uppercase tracking-wide text-gray-500">Clips</p>
                      <p className="mt-1 font-semibold text-gray-100">{shotDetail.clips.length}</p>
                      <p className="mt-1 text-xs text-gray-500">
                        Best clip {bestClip?.clip_score?.toFixed(2) ?? '-'}
                      </p>
                    </div>
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-400">Rough-Cut Candidates</h3>
          <p className="text-xs text-gray-500">Sorted by backend score and persisted per run</p>
        </div>
        {runDetail.rough_cut_candidates.length === 0 ? (
          <EmptyState
            title="No rough-cut candidates yet"
            description="Assemble the selected run once shot clips are ready to persist candidate edits."
          />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {runDetail.rough_cut_candidates.map((candidate) => (
              <RoughCutCandidateCard key={candidate.rough_cut.id} candidate={candidate} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
