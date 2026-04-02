import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

import type {
  StoryPlannerAnchorQueueResponse,
  StoryPlannerPlanResponse,
} from '../../../api/client'

function StoryPlannerSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="rounded-3xl border border-white/10 bg-gray-950/90 p-6 shadow-2xl shadow-black/20">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-emerald-100">
          Queued
        </span>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  )
}

export interface StoryPlannerAnchorResultsProps {
  result: StoryPlannerAnchorQueueResponse
  plan: StoryPlannerPlanResponse
}

export default function StoryPlannerAnchorResults({ result, plan }: StoryPlannerAnchorResultsProps) {
  return (
    <StoryPlannerSection title="Planner Recommendation">
      <div className="space-y-5">
        <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-4">
          <div className="grid gap-3 md:grid-cols-[minmax(0,0.45fr)_minmax(0,1fr)]">
            <Metric label="Recommended Anchor Shot" value={`Shot ${plan.recommended_anchor_shot_no}`} accent="good" />
            <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
              <p className="text-[11px] uppercase tracking-[0.18em] text-gray-500">Recommendation Reason</p>
              <p className="mt-3 text-sm leading-6 text-gray-200">{plan.recommended_anchor_reason}</p>
            </div>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <Metric label="Requested Shots" value={`${result.requested_shot_count}`} />
          <Metric label="Queued Generations" value={`${result.queued_generation_count}`} accent="good" />
          <Metric label="Lane" value={result.lane} />
        </div>

        <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold text-gray-100">Queued Shot Map</p>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/queue"
                className="rounded-full border border-gray-700 px-3 py-1.5 text-xs text-gray-200 transition hover:border-gray-500 hover:text-white"
              >
                Queue
              </Link>
              <Link
                to="/gallery"
                className="rounded-full border border-gray-700 px-3 py-1.5 text-xs text-gray-200 transition hover:border-gray-500 hover:text-white"
              >
                Gallery
              </Link>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {result.queued_shots.map((shot) => (
              <article key={shot.shot_no} className="rounded-2xl border border-gray-800 bg-gray-900/70 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-gray-500">Shot {shot.shot_no}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {shot.generation_ids.map((generationId) => (
                    <span
                      key={generationId}
                      className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-1 text-[11px] text-violet-100"
                    >
                      {generationId}
                    </span>
                  ))}
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
          <p className="text-sm font-semibold text-gray-100">Queued Generations</p>
          <p className="mt-2 text-sm leading-6 text-gray-300">
            {result.queued_generation_count} queued anchors were added to the queue for {result.requested_shot_count} shots.
          </p>
        </div>
      </div>
    </StoryPlannerSection>
  )
}

function Metric({
  label,
  value,
  accent = 'default',
}: {
  label: string
  value: string
  accent?: 'default' | 'good'
}) {
  const accentClass =
    accent === 'good'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
      : 'border-gray-800 bg-gray-950/80 text-gray-100'

  return (
    <div className={`rounded-2xl border px-4 py-3 ${accentClass}`}>
      <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">{label}</div>
      <div className="mt-2 break-all text-sm font-semibold">{value}</div>
    </div>
  )
}
