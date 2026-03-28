import type {
  StoryPlannerPlanResponse,
} from '../../../api/client'
import type { ReactNode } from 'react'

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
        <span className="rounded-full border border-sky-500/20 bg-sky-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-sky-100">
          Preview
        </span>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  )
}

export interface StoryPlannerPlanReviewProps {
  plan: StoryPlannerPlanResponse
  isGenerating: boolean
  onApproveAndGenerate: () => void
}

export default function StoryPlannerPlanReview({
  plan,
  isGenerating,
  onApproveAndGenerate,
}: StoryPlannerPlanReviewProps) {
  return (
    <StoryPlannerSection title="Plan Review">
      <div className="space-y-5">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <Metric label="Lane" value={plan.lane} />
          <Metric label="Policy Pack" value={plan.policy_pack_id} />
          <Metric label="Checkpoint" value={plan.anchor_render.checkpoint} />
          <Metric label="Workflow Lane" value={plan.anchor_render.workflow_lane} />
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
            <p className="text-[11px] uppercase tracking-[0.18em] text-gray-500">Episode Brief</p>
            <p className="mt-3 text-sm leading-6 text-gray-200">{plan.episode_brief.premise}</p>
            <div className="mt-4 space-y-2">
              {plan.episode_brief.continuity_guidance.map((guidance) => (
                <div key={guidance} className="rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-2 text-xs leading-5 text-gray-300">
                  {guidance}
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
            <p className="text-[11px] uppercase tracking-[0.18em] text-gray-500">Location</p>
            <h3 className="mt-2 text-base font-semibold text-gray-100">{plan.location.name}</h3>
            <p className="mt-2 text-sm leading-6 text-gray-300">{plan.location.setting_anchor}</p>
            <p className="mt-4 text-xs leading-5 text-gray-500">{plan.location.match_note}</p>
          </div>
        </div>

        <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
          <p className="text-[11px] uppercase tracking-[0.18em] text-gray-500">Cast Resolution</p>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {plan.resolved_cast.length ? (
              plan.resolved_cast.map((member) => (
                <article key={`${member.role}-${member.character_id ?? member.freeform_description ?? 'cast'}`} className="rounded-2xl border border-gray-800 bg-gray-900/70 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-gray-500">{member.role}</p>
                      <h4 className="mt-1 text-sm font-semibold text-gray-100">
                        {member.character_name ?? member.freeform_description ?? 'Unassigned'}
                      </h4>
                    </div>
                    <span className="rounded-full border border-gray-700 bg-gray-950 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-gray-400">
                      {member.source_type}
                    </span>
                  </div>
                  <p className="mt-3 text-xs leading-5 text-gray-400">{member.resolution_note}</p>
                </article>
              ))
            ) : (
              <div className="rounded-2xl border border-dashed border-gray-800 bg-gray-900/60 px-4 py-5 text-sm text-gray-400">
                No registry cast was supplied, so the plan stays focused on the story prompt and location.
              </div>
            )}
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {plan.shots.map((shot) => (
            <article key={shot.shot_no} className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-gray-100">Shot {shot.shot_no}</h3>
                <span className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-violet-100">
                  {shot.beat}
                </span>
              </div>
              <div className="mt-3 space-y-2 text-xs leading-5 text-gray-300">
                <p><span className="text-gray-500">Camera</span> {shot.camera}</p>
                <p><span className="text-gray-500">Action</span> {shot.action}</p>
                <p><span className="text-gray-500">Emotion</span> {shot.emotion}</p>
                <p><span className="text-gray-500">Continuity</span> {shot.continuity_note}</p>
              </div>
            </article>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-4">
          <button
            type="button"
            onClick={onApproveAndGenerate}
            disabled={isGenerating}
            className="rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isGenerating ? 'Generating Anchors...' : 'Approve And Generate Anchors'}
          </button>
          <p className="text-sm leading-6 text-emerald-100/90">
            Approving this plan queues the four anchor shots against the resolved render snapshot.
          </p>
        </div>
      </div>
    </StoryPlannerSection>
  )
}

function Metric({
  label,
  value,
}: {
  label: string
  value: string
}) {
  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/80 px-4 py-3">
      <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">{label}</div>
      <div className="mt-2 break-all text-sm font-semibold text-gray-100">{value}</div>
    </div>
  )
}
