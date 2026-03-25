import { useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import {
  getFavoriteUpscaleStatus,
  getGallery,
  type GalleryQuery,
  type GenerationResponse,
} from '../api/client'
import CaptionModal from '../components/tools/CaptionModal'

function toDataUrl(path: string | null): string | null {
  if (!path) return null
  if (path.startsWith('/data/')) return path
  return `/data/${path.replace(/^\/+/, '')}`
}

function formatClock(hour: number, minute: number): string {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

export default function Favorites() {
  const [selectedItem, setSelectedItem] = useState<GenerationResponse | null>(null)
  const sentinelRef = useRef<HTMLDivElement | null>(null)

  const queryParams = useMemo<GalleryQuery>(
    () => ({
      per_page: 24,
      favorites: true,
      sort_order: 'desc',
    }),
    [],
  )

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['favorites-gallery', queryParams],
    queryFn: ({ pageParam = 1 }) => getGallery({ ...queryParams, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined
    ),
  })

  const { data: upscaleStatus } = useQuery({
    queryKey: ['favorite-upscale-status'],
    queryFn: getFavoriteUpscaleStatus,
    refetchInterval: 5000,
  })

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0]
        if (!entry?.isIntersecting) return
        if (hasNextPage && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { rootMargin: '280px 0px' },
    )

    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])

  const items = useMemo(() => (
    data?.pages.flatMap((pageData) => pageData.items) ?? []
  ), [data])

  const total = data?.pages[0]?.total ?? 0

  return (
    <div className="space-y-6 rounded-2xl border border-zinc-900 bg-zinc-950 p-4 sm:p-6">
      <header>
        <h2 className="text-2xl font-bold text-zinc-100">Favorites Gallery</h2>
        <p className="mt-1 text-sm text-zinc-400">
          Open any favorited image and generate a caption instantly.
        </p>
      </header>

      {upscaleStatus && (
        <section className="overflow-hidden rounded-2xl border border-emerald-900/50 bg-gradient-to-br from-zinc-950 via-zinc-950 to-emerald-950/30">
          <div className="grid gap-4 p-4 sm:grid-cols-[1.4fr_1fr] sm:p-5">
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-emerald-300/80">
                    Favorite Upscale Backlog
                  </p>
                  <h3 className="text-lg font-semibold text-zinc-100">
                    {upscaleStatus.upscaled_done} / {upscaleStatus.favorites_total} complete
                  </h3>
                </div>
                <div className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-sm font-medium text-emerald-200">
                  {upscaleStatus.completion_pct.toFixed(1)}%
                </div>
              </div>

              <div className="h-2.5 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-emerald-300 to-lime-300 transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, upscaleStatus.completion_pct))}%` }}
                />
              </div>

              <div className="grid grid-cols-2 gap-3 text-sm text-zinc-300 sm:grid-cols-4">
                <div className="rounded-xl border border-zinc-800 bg-black/20 p-3">
                  <p className="text-xs text-zinc-500">Done</p>
                  <p className="mt-1 text-lg font-semibold text-zinc-100">{upscaleStatus.upscaled_done}</p>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-black/20 p-3">
                  <p className="text-xs text-zinc-500">Queued</p>
                  <p className="mt-1 text-lg font-semibold text-zinc-100">{upscaleStatus.queued}</p>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-black/20 p-3">
                  <p className="text-xs text-zinc-500">Running</p>
                  <p className="mt-1 text-lg font-semibold text-zinc-100">{upscaleStatus.running}</p>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-black/20 p-3">
                  <p className="text-xs text-zinc-500">Pending</p>
                  <p className="mt-1 text-lg font-semibold text-zinc-100">{upscaleStatus.pending}</p>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-black/20 p-3">
                  <p className="text-xs text-zinc-500">Next Daily Batch</p>
                  <p className="mt-1 text-lg font-semibold text-zinc-100">{upscaleStatus.daily_candidates}</p>
                </div>
              </div>
            </div>

            <div className="space-y-3 rounded-2xl border border-zinc-800 bg-black/20 p-4">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Batch Policy</p>
                <p className="mt-1 text-sm text-zinc-200">
                  All favorite images without an upscale are queued once per day at{' '}
                  <span className="font-mono text-emerald-300">
                    {formatClock(upscaleStatus.daily_hour, upscaleStatus.daily_minute)}
                  </span>
                  {upscaleStatus.daily_batch_limit == null ? (
                    <>.</>
                  ) : (
                    <>
                      , up to{' '}
                      <span className="font-mono text-emerald-300">
                        {upscaleStatus.daily_batch_limit}
                      </span>{' '}
                      images per run.
                    </>
                  )}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-zinc-500">Backlog Window</p>
                <p className="mt-1 text-sm text-zinc-200">
                  {formatClock(upscaleStatus.backlog_window_start_hour, 0)}-
                  {formatClock(upscaleStatus.backlog_window_end_hour, 0)} / mode{' '}
                  <span className="font-mono text-emerald-300">{upscaleStatus.mode}</span>
                </p>
              </div>
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 px-3 py-2 text-sm">
                <span className="text-zinc-500">Status: </span>
                <span className={upscaleStatus.backlog_window_open ? 'text-emerald-300' : 'text-amber-300'}>
                  {upscaleStatus.backlog_window_open ? 'Backlog running now' : 'Backlog paused until next window'}
                </span>
              </div>
            </div>
          </div>
        </section>
      )}

      {isLoading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 12 }).map((_, index) => (
            <div
              key={`favorite-skeleton-${index}`}
              className="aspect-[3/4] animate-pulse rounded-xl border border-zinc-800 bg-zinc-900"
            />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-red-800/60 bg-zinc-900 p-6 text-center">
          <p className="text-red-300">Failed to load favorites.</p>
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-8 text-center">
          <p className="text-sm text-zinc-300">
            No favorites yet. Heart images in the gallery to see them here.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {items.map((item) => {
              const imageSrc = toDataUrl(item.upscaled_preview_path || item.thumbnail_path || item.image_path)

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedItem(item)}
                  className="group relative aspect-[3/4] overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900 text-left transition-colors duration-150 hover:border-emerald-500/50"
                >
                  {imageSrc ? (
                    <img
                      src={imageSrc}
                      alt={item.prompt.slice(0, 120)}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-zinc-600">
                      <svg className="h-10 w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                      </svg>
                    </div>
                  )}

                  <span className="absolute right-2 top-2 rounded-full border border-red-300/50 bg-red-600/90 px-2 py-1 text-xs font-semibold text-white">
                    ♥
                  </span>

                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 to-transparent p-3">
                    <p className="line-clamp-1 text-xs text-zinc-200">{item.prompt}</p>
                  </div>
                </button>
              )
            })}
          </div>

          <div className="flex flex-col items-center gap-2 pt-3">
            {isFetchingNextPage && (
              <div className="flex items-center gap-2 text-sm text-zinc-400">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
                Loading more favorites...
              </div>
            )}
            {!hasNextPage && items.length > 0 && (
              <p className="text-sm text-zinc-500">All favorites are loaded</p>
            )}
            {total > 0 && (
              <p className="text-xs text-zinc-500">
                Loaded {items.length} / {total} favorites
              </p>
            )}
          </div>

          <div ref={sentinelRef} className="h-8 w-full" aria-hidden="true" />
        </>
      )}

      <CaptionModal
        isOpen={selectedItem !== null}
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
      />
    </div>
  )
}
