import { useMemo, useState, type ReactNode } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  getCaptionVariants,
  getPublishJobs,
  getPublishingReadiness,
  getReadyPublishItems,
  type CaptionVariantResponse,
  type PublishJobPlatform,
  type PublishJobResponse,
  type PublishingChannel,
  type PublishingTone,
  type ReadyPublishItemResponse,
} from '../../api/client'
import PublishingPilotCard from './PublishingPilotCard'

type SharedPlatform = Extract<PublishJobPlatform, 'twitter' | 'fansly' | 'pixiv'>

interface PublishingPilotWorkbenchProps {
  generationIds: string[]
}

interface SharedControls {
  platform: SharedPlatform
  tone: PublishingTone
  channel: PublishingChannel
}

const PLATFORM_OPTIONS: Array<{ value: SharedPlatform; label: string }> = [
  { value: 'pixiv', label: 'Pixiv' },
  { value: 'twitter', label: 'X / Twitter' },
  { value: 'fansly', label: 'Fansly' },
]

const TONE_OPTIONS: Array<{ value: PublishingTone; label: string }> = [
  { value: 'teaser', label: 'Teaser' },
  { value: 'campaign', label: 'Campaign' },
  { value: 'clinical', label: 'Clinical' },
]

const CHANNEL_OPTIONS: Array<{ value: PublishingChannel; label: string }> = [
  { value: 'social_short', label: 'Social Short' },
  { value: 'post_body', label: 'Post Body' },
  { value: 'launch_copy', label: 'Launch Copy' },
]

const DEFAULT_SHARED_CONTROLS: SharedControls = {
  platform: 'pixiv',
  tone: 'teaser',
  channel: 'social_short',
}

const GENERATION_ID_PATTERN = /^[a-zA-Z0-9_-]+$/

function parseGenerationIds(rawGenerationIds: string[]) {
  const validIds: string[] = []
  const invalidIds: string[] = []
  const seen = new Set<string>()

  for (const rawValue of rawGenerationIds) {
    const value = rawValue.trim()
    if (!value || !GENERATION_ID_PATTERN.test(value) || seen.has(value)) {
      if (value && !seen.has(value)) {
        invalidIds.push(value)
      }
      continue
    }

    seen.add(value)
    validIds.push(value)
  }

  return { validIds, invalidIds }
}

export default function PublishingPilotWorkbench({ generationIds }: PublishingPilotWorkbenchProps) {
  const [controls, setControls] = useState<SharedControls>(DEFAULT_SHARED_CONTROLS)
  const { validIds, invalidIds } = useMemo(
    () => parseGenerationIds(generationIds),
    [generationIds],
  )

  const readyItemsQuery = useQuery({
    queryKey: ['publishing-pilot', 'ready-items', validIds],
    queryFn: () => getReadyPublishItems(validIds),
    enabled: validIds.length > 0,
  })

  const readinessQuery = useQuery({
    queryKey: ['publishing-pilot', 'readiness'],
    queryFn: getPublishingReadiness,
    enabled: validIds.length > 0,
    staleTime: 60_000,
  })

  const itemsById = useMemo(
    () =>
      new Map(
        (readyItemsQuery.data ?? []).map((item) => [item.generation_id, item] satisfies [string, ReadyPublishItemResponse]),
      ),
    [readyItemsQuery.data],
  )

  const orderedItems = useMemo(
    () => validIds.map((generationId) => itemsById.get(generationId)).filter(Boolean) as ReadyPublishItemResponse[],
    [validIds, itemsById],
  )

  const missingGenerationIds = useMemo(
    () => validIds.filter((generationId) => !itemsById.has(generationId)),
    [validIds, itemsById],
  )

  const captionQueries = useQueries({
    queries: orderedItems.map((item) => ({
      queryKey: ['publishing-pilot', 'captions', item.generation_id],
      queryFn: () => getCaptionVariants(item.generation_id),
      enabled: readyItemsQuery.isSuccess,
    })),
  })

  const publishJobQueries = useQueries({
    queries: orderedItems.map((item) => ({
      queryKey: ['publishing-pilot', 'publish-jobs', item.generation_id],
      queryFn: () => getPublishJobs(item.generation_id),
      enabled: readyItemsQuery.isSuccess,
    })),
  })

  const approvedCount = captionQueries.reduce((count, query) => {
    if (!query.data?.some((caption) => caption.approved)) {
      return count
    }
    return count + 1
  }, 0)

  const draftCount = publishJobQueries.reduce((count, query) => {
    if (!query.data?.some((job) => job.status === 'draft' && job.platform === controls.platform)) {
      return count
    }
    return count + 1
  }, 0)

  const isInitialLoading = readyItemsQuery.isLoading

  if (isInitialLoading) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-[1.15fr,0.85fr]">
          <div className="h-36 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/70" />
          <div className="h-36 animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/70" />
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {generationIds.map((generationId, index) => (
            <div
              key={`${generationId}-${index}`}
              className="h-[28rem] animate-pulse rounded-2xl border border-zinc-800 bg-zinc-900/70"
            />
          ))}
        </div>
      </div>
    )
  }

  if (readyItemsQuery.isError) {
    return (
      <div className="rounded-2xl border border-red-900/50 bg-red-950/20 p-6">
        <h3 className="text-lg font-semibold text-red-200">Failed to load publishing batch</h3>
        <p className="mt-2 text-sm text-red-200/80">
          The selected ready items could not be loaded. Return to /ready and reselect the batch.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {readinessQuery.data?.degraded_mode === 'draft_only' && (
        <section className="rounded-2xl border border-amber-900/50 bg-amber-950/20 p-4 text-sm text-amber-100/90">
          <p className="font-medium">Draft-only mode</p>
          <p className="mt-1">Caption generation is unavailable until OPENROUTER_API_KEY is configured.</p>
          <p className="mt-1 text-amber-100/80">
            Missing requirements: {readinessQuery.data.missing_requirements.join(', ')}
          </p>
        </section>
      )}
      <section className="grid gap-4 lg:grid-cols-[1.15fr,0.85fr]">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
          <p className="text-xs uppercase tracking-[0.18em] text-emerald-300/80">Selected Batch</p>
          <h3 className="mt-2 text-xl font-semibold text-zinc-100">Publishing pilot intake</h3>
          <p className="mt-2 text-sm text-zinc-400">
            Work through the selected ready items one by one. Generate a caption with the shared
            controls, approve the variant to use, then create an internal draft publish job.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <StatTile label="Requested" value={String(generationIds.length)} />
            <StatTile label="Valid" value={String(validIds.length)} />
            <StatTile label="Approved Captions" value={String(approvedCount)} />
            <StatTile label={`${controls.platform} Drafts`} value={String(draftCount)} />
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <p className="text-xs uppercase tracking-[0.18em] text-violet-300/80">Shared Controls</p>
            <Link
              to="/ready"
              className="rounded-lg border border-emerald-400/40 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-200 transition-colors hover:border-emerald-300/60 hover:bg-emerald-500/15"
            >
              Reselect in /ready
            </Link>
          </div>
          <div className="mt-4 grid gap-4">
            <ControlField label="Platform">
              <select
                value={controls.platform}
                onChange={(event) =>
                  setControls((current) => ({
                    ...current,
                    platform: event.target.value as SharedPlatform,
                  }))
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
              >
                {PLATFORM_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </ControlField>
            <ControlField label="Tone">
              <select
                value={controls.tone}
                onChange={(event) =>
                  setControls((current) => ({
                    ...current,
                    tone: event.target.value as PublishingTone,
                  }))
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
              >
                {TONE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </ControlField>
            <ControlField label="Channel">
              <select
                value={controls.channel}
                onChange={(event) =>
                  setControls((current) => ({
                    ...current,
                    channel: event.target.value as PublishingChannel,
                  }))
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100"
              >
                {CHANNEL_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </ControlField>
          </div>
        </div>
      </section>

      {(invalidIds.length > 0 || missingGenerationIds.length > 0) && (
        <section className="rounded-2xl border border-amber-900/50 bg-amber-950/20 p-4 text-sm text-amber-100/90">
          {invalidIds.length > 0 && (
            <p>Ignored {invalidIds.length} invalid `generation_id` value(s) in the query string.</p>
          )}
          {missingGenerationIds.length > 0 && (
            <p className={invalidIds.length > 0 ? 'mt-2' : undefined}>
              {missingGenerationIds.length} selected item(s) were not returned by the ready-items
              endpoint and are excluded from this workbench.
            </p>
          )}
        </section>
      )}

      {validIds.length === 0 && (
        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-6 text-sm text-zinc-300">
          <p className="font-medium text-zinc-100">No valid selected IDs</p>
          <p className="mt-2 text-zinc-400">
            The workbench opened with `generation_id` params, but none passed validation. Return to
            the ready queue and select the batch again.
          </p>
        </section>
      )}

      {orderedItems.length > 0 && (
        <section className="grid gap-4 xl:grid-cols-2">
          {orderedItems.map((item, index) => (
            <PublishingPilotCard
              key={item.generation_id}
              item={item}
              controls={controls}
              readiness={readinessQuery.data ?? null}
              captionQuery={{
                data: (captionQueries[index]?.data ?? []) as CaptionVariantResponse[],
                isLoading: captionQueries[index]?.isLoading ?? false,
                isError: captionQueries[index]?.isError ?? false,
              }}
              publishJobsQuery={{
                data: (publishJobQueries[index]?.data ?? []) as PublishJobResponse[],
                isLoading: publishJobQueries[index]?.isLoading ?? false,
                isError: publishJobQueries[index]?.isError ?? false,
              }}
            />
          ))}
        </section>
      )}
    </div>
  )
}

function ControlField({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <label className="grid gap-2">
      <span className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-400">{label}</span>
      {children}
    </label>
  )
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 px-3 py-3">
      <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-zinc-100">{value}</p>
    </div>
  )
}
