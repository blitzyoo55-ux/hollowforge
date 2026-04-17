import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'
import { Link } from 'react-router-dom'

import {
  createProductionEpisode,
  createProductionSeries,
  createProductionWork,
  listProductionEpisodes,
  listProductionSeries,
  listProductionWorks,
  type ProductionEpisodeCreate,
  type ProductionEpisodeDetailResponse,
  type ProductionSeriesCreate,
  type ProductionWorkCreate,
} from '../api/client'
import EmptyState from '../components/EmptyState'
import ProductionEpisodeForm from '../components/production/ProductionEpisodeForm'
import ProductionSeriesForm from '../components/production/ProductionSeriesForm'
import ProductionWorkForm from '../components/production/ProductionWorkForm'
import VerificationHistoryPanel from '../components/production/VerificationHistoryPanel'
import VerificationOpsCard from '../components/production/VerificationOpsCard'
import { buildProductionTrackHref } from '../lib/productionEntry'
import { notify } from '../lib/toast'

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as AxiosError<{ detail?: string }>)?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (error instanceof Error && error.message.trim()) return error.message
  return fallback
}

function formatDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

function countLinkedTracks(
  episodes: ProductionEpisodeDetailResponse[],
  track: 'comic_track_count' | 'animation_track_count',
): number {
  return episodes.filter((episode) => episode[track] > 0).length
}

function ContentModeBadge({ mode }: { mode: ProductionEpisodeDetailResponse['content_mode'] }) {
  const className = mode === 'adult_nsfw'
    ? 'border-rose-500/30 bg-rose-500/10 text-rose-200'
    : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'

  return (
    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide ${className}`}>
      {mode}
    </span>
  )
}

function TrackStatusBadge({ linked }: { linked: boolean }) {
  return (
    <span
      className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide ${
        linked
          ? 'border-violet-500/30 bg-violet-500/10 text-violet-200'
          : 'border-gray-700 bg-gray-900 text-gray-400'
      }`}
    >
      {linked ? 'Linked' : 'Not linked'}
    </span>
  )
}

function SummaryCard({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: 'violet' | 'emerald' | 'sky'
}) {
  const toneClassName = {
    violet: 'border-violet-500/30 bg-violet-500/10 text-violet-200',
    emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200',
    sky: 'border-sky-500/30 bg-sky-500/10 text-sky-200',
  }[tone]

  return (
    <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
      <p className="text-[11px] uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`mt-2 inline-flex rounded-full border px-3 py-1 text-2xl font-semibold ${toneClassName}`}>
        {value}
      </p>
    </div>
  )
}

function TrackBoundaryCard({
  title,
  description,
  href,
  cta,
}: {
  title: string
  description: string
  href: string
  cta: string
}) {
  return (
    <article className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
      <p className="mt-2 text-sm text-gray-400">{description}</p>
      <Link
        to={href}
        className="mt-4 inline-flex rounded-xl border border-violet-500/40 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20"
      >
        {cta}
      </Link>
    </article>
  )
}

export default function ProductionHub() {
  const queryClient = useQueryClient()

  const worksQuery = useQuery({
    queryKey: ['production-works'],
    queryFn: () => listProductionWorks(),
    refetchInterval: 30_000,
  })

  const seriesQuery = useQuery({
    queryKey: ['production-series'],
    queryFn: () => listProductionSeries(),
    refetchInterval: 30_000,
  })

  const episodesQuery = useQuery({
    queryKey: ['production-episodes'],
    queryFn: () => listProductionEpisodes(),
    refetchInterval: 30_000,
  })

  const createWorkMutation = useMutation({
    mutationFn: (payload: ProductionWorkCreate) => createProductionWork(payload),
    onSuccess: async () => {
      notify.success('Production work created')
      await queryClient.invalidateQueries({ queryKey: ['production-works'] })
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to create production work'))
    },
  })

  const createSeriesMutation = useMutation({
    mutationFn: (payload: ProductionSeriesCreate) => createProductionSeries(payload),
    onSuccess: async () => {
      notify.success('Production series created')
      await queryClient.invalidateQueries({ queryKey: ['production-series'] })
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to create production series'))
    },
  })

  const createEpisodeMutation = useMutation({
    mutationFn: (payload: ProductionEpisodeCreate) => createProductionEpisode(payload),
    onSuccess: async () => {
      notify.success('Production episode created')
      await queryClient.invalidateQueries({ queryKey: ['production-episodes'] })
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to create production episode'))
    },
  })

  const works = worksQuery.data ?? []
  const series = seriesQuery.data ?? []
  const episodes = episodesQuery.data ?? []
  const comicLinkedCount = countLinkedTracks(episodes, 'comic_track_count')
  const animationLinkedCount = countLinkedTracks(episodes, 'animation_track_count')

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="space-y-3">
            <span className="inline-flex rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-violet-300">
              Shared Production Core
            </span>
            <div>
              <h1 className="text-2xl font-bold text-gray-100">Production Hub</h1>
              <p className="mt-2 max-w-3xl text-sm text-gray-400">
                Track work, series, and episode-level production state in one place. HollowForge owns orchestration,
                review, and handoff packaging here, while final authoring stays in CLIP STUDIO EX and the external
                animation editor.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <SummaryCard label="Episodes" value={episodes.length} tone="violet" />
            <SummaryCard label="Comic Linked" value={comicLinkedCount} tone="emerald" />
            <SummaryCard label="Animation Linked" value={animationLinkedCount} tone="sky" />
          </div>
        </div>
      </section>

      <VerificationOpsCard />

      <VerificationHistoryPanel />

      <section className="grid gap-6 xl:grid-cols-3">
        <ProductionWorkForm
          onSubmit={(payload) => createWorkMutation.mutate(payload)}
          isSubmitting={createWorkMutation.isPending}
        />
        <ProductionSeriesForm
          works={works}
          onSubmit={(payload) => createSeriesMutation.mutate(payload)}
          isSubmitting={createSeriesMutation.isPending}
        />
        <ProductionEpisodeForm
          works={works}
          series={series}
          onSubmit={(payload) => createEpisodeMutation.mutate(payload)}
          isSubmitting={createEpisodeMutation.isPending}
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <TrackBoundaryCard
          title="Comic Handoff"
          description="Move approved production episodes into page-ready comic packaging. This lane is for render review, dialogue drafting, assembly, and export preparation before CLIP STUDIO finishing."
          href="/comic"
          cta="Open Comic Handoff"
        />
        <TrackBoundaryCard
          title="Animation Track"
          description="Plan and review animation-oriented sequence blueprints and rough cuts. This lane is for shot orchestration and preview validation before external editorial finishing."
          href="/sequences"
          cta="Open Animation Track"
        />
      </div>

      <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Episode Registry</h2>
            <p className="text-sm text-gray-400">
              Shared episode state, normalized content mode, and current linkage into comic and animation tracks.
            </p>
          </div>
        </div>

        {episodesQuery.isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
          </div>
        ) : episodesQuery.isError ? (
          <div className="mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            Failed to load production episodes.
          </div>
        ) : episodes.length === 0 ? (
          <div className="mt-4">
            <EmptyState
              title="No production episodes yet"
              description="Create shared production-core episodes first so the comic and animation tracks can link back to one source of truth."
            />
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {episodes.map((episode) => {
              const comicLinkHref = buildProductionTrackHref('comic', episode)
              const animationLinkHref = buildProductionTrackHref('animation', episode)
              const comicLinked = episode.comic_track_count > 0 || episode.comic_track !== null
              const animationLinked = episode.animation_track_count > 0 || episode.animation_track !== null

              return (
                <article
                  key={episode.id}
                  className="rounded-2xl border border-gray-800 bg-gray-950/70 p-5"
                >
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="space-y-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <ContentModeBadge mode={episode.content_mode} />
                        <span className="rounded-full border border-gray-700 bg-gray-900 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-gray-300">
                          {episode.status}
                        </span>
                        {episode.target_outputs.map((target) => (
                          <span
                            key={`${episode.id}-${target}`}
                            className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-1 text-[11px] font-medium uppercase tracking-wide text-sky-200"
                          >
                            {target}
                          </span>
                        ))}
                      </div>

                      <div>
                        <h3 className="text-lg font-semibold text-gray-100">{episode.title}</h3>
                        <p className="mt-1 max-w-3xl text-sm text-gray-400">{episode.synopsis}</p>
                      </div>

                      <div className="flex flex-wrap gap-4 text-xs text-gray-500">
                        <span>Work: {episode.work_id}</span>
                        <span>Series: {episode.series_id ?? 'standalone'}</span>
                        <span>Updated: {formatDate(episode.updated_at)}</span>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Link
                        to={comicLinkHref}
                        className="inline-flex rounded-xl border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 transition hover:border-violet-500/40 hover:text-white"
                      >
                        Open Comic Handoff
                      </Link>
                      <Link
                        to={animationLinkHref}
                        className="inline-flex rounded-xl border border-gray-700 bg-gray-900 px-4 py-2 text-sm font-medium text-gray-200 transition hover:border-violet-500/40 hover:text-white"
                      >
                        Open Animation Track
                      </Link>
                    </div>
                  </div>

                  {(episode.comic_track_count > 1 || episode.animation_track_count > 1) && (
                    <div className="mt-4 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">
                      {episode.comic_track_count > 1 && (
                        <p>Comic track count is {episode.comic_track_count}; review duplicate links before final handoff.</p>
                      )}
                      {episode.animation_track_count > 1 && (
                        <p>Animation track count is {episode.animation_track_count}; review duplicate links before final handoff.</p>
                      )}
                    </div>
                  )}

                  <div className="mt-5 grid gap-4 xl:grid-cols-2">
                    <section className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="text-sm font-semibold text-gray-100">Comic Track</h4>
                        <TrackStatusBadge linked={comicLinked} />
                      </div>
                      {episode.comic_track ? (
                        <div className="mt-3 space-y-1 text-sm text-gray-300">
                          <p>Status: {episode.comic_track.status}</p>
                          <p>Target Output: {episode.comic_track.target_output}</p>
                          <p>Character: {episode.comic_track.character_id}</p>
                        </div>
                      ) : (
                        <p className="mt-3 text-sm text-gray-400">
                          {episode.comic_track_count > 0
                            ? `No single comic handoff is selected (${episode.comic_track_count} linked).`
                            : 'No comic handoff episode is linked yet.'}
                        </p>
                      )}
                    </section>

                    <section className="rounded-xl border border-gray-800 bg-gray-900/60 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <h4 className="text-sm font-semibold text-gray-100">Animation Track</h4>
                        <TrackStatusBadge linked={animationLinked} />
                      </div>
                      {episode.animation_track ? (
                        <div className="mt-3 space-y-1 text-sm text-gray-300">
                          <p>Content Mode: {episode.animation_track.content_mode}</p>
                          <p>Policy Profile: {episode.animation_track.policy_profile_id}</p>
                          <p>Shot Count: {episode.animation_track.shot_count}</p>
                          <p>Executor Policy: {episode.animation_track.executor_policy}</p>
                        </div>
                      ) : (
                        <p className="mt-3 text-sm text-gray-400">
                          {episode.animation_track_count > 0
                            ? `No single animation blueprint is selected (${episode.animation_track_count} linked).`
                            : 'No animation-track blueprint is linked yet.'}
                        </p>
                      )}
                    </section>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
