import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  approveCaptionVariant,
  createPublishJob,
  generateCaptionVariant,
  type CaptionVariantResponse,
  type PublishJobPlatform,
  type PublishJobResponse,
  type PublishingChannel,
  type PublishingTone,
  type ReadyPublishItemResponse,
} from '../../api/client'

type SharedPlatform = Extract<PublishJobPlatform, 'twitter' | 'fansly' | 'pixiv'>

interface PublishingPilotCardProps {
  item: ReadyPublishItemResponse
  controls: {
    platform: SharedPlatform
    tone: PublishingTone
    channel: PublishingChannel
  }
  captionQuery: {
    data: CaptionVariantResponse[]
    isLoading: boolean
    isError: boolean
  }
  publishJobsQuery: {
    data: PublishJobResponse[]
    isLoading: boolean
    isError: boolean
  }
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    return (error.response?.data as { detail?: string } | undefined)?.detail || error.message || fallback
  }
  if (error instanceof Error && error.message) {
    return error.message
  }
  return fallback
}

function formatDateTime(value: string | null) {
  if (!value) return 'Not available'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

function getAssetPath(path: string | null) {
  return path ? `/data/${path}` : null
}

function getCaptionSummary(caption: CaptionVariantResponse) {
  if (!caption.story.trim()) return 'No story text'
  return caption.story.length > 160 ? `${caption.story.slice(0, 157)}...` : caption.story
}

export default function PublishingPilotCard({
  item,
  controls,
  captionQuery,
  publishJobsQuery,
}: PublishingPilotCardProps) {
  const queryClient = useQueryClient()
  const [localError, setLocalError] = useState<string | null>(null)

  const approvedCaption = useMemo(
    () =>
      captionQuery.data.find(
        (caption) =>
          caption.approved &&
          caption.platform === controls.platform &&
          caption.channel === controls.channel,
      ) ?? null,
    [captionQuery.data, controls.channel, controls.platform],
  )

  const existingDraft = useMemo(
    () =>
      publishJobsQuery.data.find(
        (job) => job.platform === controls.platform && job.status === 'draft',
      ) ?? null,
    [controls.platform, publishJobsQuery.data],
  )

  const sortedJobs = useMemo(
    () =>
      [...publishJobsQuery.data].sort(
        (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
      ),
    [publishJobsQuery.data],
  )

  const invalidateItemQueries = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: ['publishing-pilot', 'captions', item.generation_id],
      }),
      queryClient.invalidateQueries({
        queryKey: ['publishing-pilot', 'publish-jobs', item.generation_id],
      }),
      queryClient.invalidateQueries({
        queryKey: ['publishing-pilot', 'ready-items'],
        exact: false,
      }),
    ])
  }

  const generateMutation = useMutation({
    mutationFn: () =>
      generateCaptionVariant(item.generation_id, {
        platform: controls.platform,
        tone: controls.tone,
        channel: controls.channel,
      }),
    onMutate: () => setLocalError(null),
    onSuccess: async () => {
      await invalidateItemQueries()
    },
    onError: (error) => {
      setLocalError(getErrorMessage(error, 'Failed to generate caption variant.'))
    },
  })

  const approveMutation = useMutation({
    mutationFn: (captionId: string) => approveCaptionVariant(captionId),
    onMutate: () => setLocalError(null),
    onSuccess: async () => {
      await invalidateItemQueries()
    },
    onError: (error) => {
      setLocalError(getErrorMessage(error, 'Failed to approve caption variant.'))
    },
  })

  const createDraftMutation = useMutation({
    mutationFn: () =>
      createPublishJob({
        generation_id: item.generation_id,
        caption_variant_id: approvedCaption?.id,
        platform: controls.platform,
        status: 'draft',
      }),
    onMutate: () => setLocalError(null),
    onSuccess: async () => {
      await invalidateItemQueries()
    },
    onError: (error) => {
      setLocalError(getErrorMessage(error, 'Failed to create draft publish job.'))
    },
  })

  const previewPath = getAssetPath(item.thumbnail_path ?? item.image_path)
  const hasApprovedCaption = Boolean(approvedCaption?.id)

  return (
    <article className="overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-900/80">
      <div className="grid lg:grid-cols-[0.92fr,1.08fr]">
        <div className="border-b border-zinc-800 bg-zinc-950 lg:border-b-0 lg:border-r">
          <div className="aspect-[3/4] bg-zinc-950">
            {previewPath ? (
              <img src={previewPath} alt={item.prompt} className="h-full w-full object-cover" />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-zinc-500">
                No preview available
              </div>
            )}
          </div>
          <div className="space-y-3 p-4">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Checkpoint</p>
              <p className="mt-1 text-sm font-medium text-zinc-100">{item.checkpoint}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Prompt</p>
              <p className="mt-1 text-sm leading-6 text-zinc-300">{item.prompt}</p>
            </div>
            <dl className="grid gap-3 sm:grid-cols-2">
              <MetaItem label="Created" value={formatDateTime(item.created_at)} />
              <MetaItem
                label="Animation"
                value={item.latest_animation_status ? item.latest_animation_status : 'Unavailable'}
              />
              <MetaItem
                label="Latest Publish"
                value={item.latest_publish_status ? item.latest_publish_status : 'No jobs yet'}
              />
              <MetaItem label="Anim Score" value={String(item.latest_animation_score ?? 'N/A')} />
              <MetaItem label="Existing Captions" value={String(item.caption_count)} />
              <MetaItem label="Publish Jobs" value={String(item.publish_job_count)} />
            </dl>
          </div>
        </div>

        <div className="space-y-5 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-[0.16em] text-emerald-300/80">Generation</p>
              <h3 className="mt-2 text-lg font-semibold text-zinc-100">{item.generation_id}</h3>
              <p className="mt-1 text-sm text-zinc-400">
                Platform {controls.platform} · Tone {controls.tone} · Channel {controls.channel}
              </p>
            </div>
            <button
              type="button"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending}
              className="rounded-lg border border-violet-400/40 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-100 transition-colors hover:border-violet-300/60 hover:bg-violet-500/15 disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-950 disabled:text-zinc-500"
            >
              {generateMutation.isPending ? 'Generating...' : 'Generate caption'}
            </button>
          </div>

          {localError && (
            <div className="rounded-xl border border-red-900/50 bg-red-950/20 px-3 py-2 text-sm text-red-200">
              {localError}
            </div>
          )}

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold uppercase tracking-[0.16em] text-zinc-400">
                Caption Variants
              </h4>
              {captionQuery.isLoading && <span className="text-xs text-zinc-500">Loading...</span>}
            </div>

            {captionQuery.isError ? (
              <div className="rounded-xl border border-red-900/40 bg-red-950/20 px-3 py-3 text-sm text-red-200">
                Failed to load captions for this item.
              </div>
            ) : captionQuery.data.length === 0 ? (
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 px-3 py-4 text-sm text-zinc-500">
                No caption variants yet. Generate one with the shared controls.
              </div>
            ) : (
              <div className="space-y-3">
                {captionQuery.data.map((caption) => (
                  <div
                    key={caption.id}
                    className={`rounded-xl border px-4 py-4 ${
                      caption.approved
                        ? 'border-emerald-500/40 bg-emerald-500/10'
                        : 'border-zinc-800 bg-zinc-950/80'
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-zinc-100">{getCaptionSummary(caption)}</p>
                        <p className="mt-2 text-xs text-zinc-500">
                          {caption.platform} · {caption.tone} · {caption.channel} ·{' '}
                          {formatDateTime(caption.created_at)}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => approveMutation.mutate(caption.id)}
                        disabled={approveMutation.isPending || caption.approved}
                        className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                          caption.approved
                            ? 'border border-emerald-500/30 bg-emerald-500/15 text-emerald-200'
                            : 'border border-emerald-400/40 bg-emerald-500/10 text-emerald-100 hover:border-emerald-300/60 hover:bg-emerald-500/15'
                        } disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-950 disabled:text-zinc-500`}
                      >
                        {caption.approved ? 'Approved' : approveMutation.isPending ? 'Saving...' : 'Approve'}
                      </button>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-zinc-300">
                      {caption.story}
                    </p>
                    {caption.hashtags.trim() && (
                      <p className="mt-3 text-sm text-violet-200/90">{caption.hashtags}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h4 className="text-sm font-semibold uppercase tracking-[0.16em] text-zinc-400">
                  Draft Job
                </h4>
                <p className="mt-2 text-sm text-zinc-400">
                  Create one internal draft for the approved caption on {controls.platform} using
                  the active {controls.channel} publishing context.
                </p>
              </div>
              <button
                type="button"
                onClick={() => createDraftMutation.mutate()}
                disabled={!hasApprovedCaption || Boolean(existingDraft) || createDraftMutation.isPending}
                className="rounded-lg border border-emerald-400/40 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-100 transition-colors hover:border-emerald-300/60 hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:border-zinc-800 disabled:bg-zinc-900 disabled:text-zinc-500"
              >
                {createDraftMutation.isPending ? 'Creating...' : 'Create draft'}
              </button>
            </div>

            {!hasApprovedCaption && (
              <p className="mt-3 text-sm text-amber-200/90">
                Approve a caption variant that matches the active platform and channel before
                creating the draft job.
              </p>
            )}

            {existingDraft ? (
              <div className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm">
                <p className="font-medium text-emerald-100">Existing draft found</p>
                <p className="mt-2 text-emerald-100/90">
                  Job {existingDraft.id} · {existingDraft.platform} · {formatDateTime(existingDraft.created_at)}
                </p>
                <p className="mt-1 text-emerald-100/80">
                  Caption {existingDraft.caption_variant_id ?? 'unlinked'} · status {existingDraft.status}
                </p>
              </div>
            ) : publishJobsQuery.isError ? (
              <div className="mt-4 rounded-xl border border-red-900/40 bg-red-950/20 px-4 py-3 text-sm text-red-200">
                Failed to load publish jobs for this item.
              </div>
            ) : publishJobsQuery.isLoading ? (
              <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-500">
                Loading publish jobs...
              </div>
            ) : sortedJobs.length === 0 ? (
              <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-500">
                No publish jobs exist for this item yet.
              </div>
            ) : (
              <div className="mt-4 space-y-2">
                {sortedJobs.slice(0, 3).map((job) => (
                  <div
                    key={job.id}
                    className="rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm text-zinc-300"
                  >
                    <p className="font-medium text-zinc-100">
                      {job.platform} · {job.status}
                    </p>
                    <p className="mt-1 text-zinc-500">
                      Job {job.id} · {formatDateTime(job.created_at)}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </article>
  )
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 px-3 py-2">
      <dt className="text-xs uppercase tracking-[0.16em] text-zinc-500">{label}</dt>
      <dd className="mt-1 text-sm text-zinc-200">{value}</dd>
    </div>
  )
}
