import { useEffect, useMemo, useRef, useState } from 'react'
import { useInfiniteQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getGallery, type GalleryQuery } from '../api/client'
import type { GenerationResponse } from '../api/client'
import EmptyState from '../components/EmptyState'
import GalleryGrid from '../components/GalleryGrid'
import Lightbox from '../components/Lightbox'
import { notify } from '../lib/toast'

export default function ReadyToGo() {
  const navigate = useNavigate()
  const sentinelRef = useRef<HTMLDivElement | null>(null)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [selectionMode, setSelectionMode] = useState(false)
  const [selectedIdsState, setSelectedIdsState] = useState<Set<string>>(new Set())

  const queryParams = useMemo<GalleryQuery>(
    () => ({
      per_page: 24,
      sort_order: 'desc',
      publish_approved: 1,
    }),
    [],
  )

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['ready-gallery', queryParams],
    queryFn: ({ pageParam = 1 }) => getGallery({ ...queryParams, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined
    ),
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

  const items = useMemo<GenerationResponse[]>(
    () => data?.pages.flatMap((pageData) => pageData.items) ?? [],
    [data],
  )
  const itemIds = useMemo(() => new Set(items.map((item) => item.id)), [items])
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedIdsState((prev) => {
      const next = new Set<string>()
      prev.forEach((generationId) => {
        if (itemIds.has(generationId)) {
          next.add(generationId)
        }
      })

      if (next.size === prev.size) {
        return prev
      }

      return next
    })
  }, [itemIds])

  const selectedIds = selectedIdsState

  const total = data?.pages[0]?.total ?? 0
  const selectedCount = selectedIds.size
  const safeSelectedIndex =
    selectedIndex === null || items.length === 0
      ? null
      : Math.min(selectedIndex, items.length - 1)

  const toggleSelectionMode = () => {
    setSelectionMode((prev) => !prev)
  }

  const handleToggleSelect = (item: GenerationResponse) => {
    if (!selectionMode) return

    setSelectedIdsState((prev) => {
      const next = new Set(prev)
      if (next.has(item.id)) {
        next.delete(item.id)
        return next
      }
      if (next.size >= 10) {
        notify.info('You can select up to 10 items for the publishing pilot.')
        return prev
      }
      next.add(item.id)
      return next
    })
  }

  const launchPublishingPilot = () => {
    if (selectedIds.size === 0) return

    const params = new URLSearchParams()
    selectedIds.forEach((generationId) => {
      params.append('generation_id', generationId)
    })
    navigate(`/marketing?${params.toString()}`)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Ready to Go</h2>
          <p className="mt-1 text-sm text-gray-400">
            Ready-to-publish images only. Click the green check to cancel the ready status.
          </p>
          <p className="mt-2 text-sm text-emerald-300">
            {selectionMode
              ? `${selectedCount} selected for publishing pilot`
              : 'Enable batch selection to hand off ready items to marketing.'}
          </p>
        </div>
        <div className="flex flex-col items-end gap-3">
          <div className="rounded-xl border border-emerald-900/50 bg-emerald-950/20 px-4 py-3 text-right">
            <p className="text-xs uppercase tracking-[0.16em] text-emerald-300/70">Ready Count</p>
            <p className="mt-1 text-2xl font-semibold text-zinc-100">{total}</p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              type="button"
              onClick={toggleSelectionMode}
              className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                selectionMode
                  ? 'border-violet-400/50 bg-violet-500/15 text-violet-200'
                  : 'border-gray-700 bg-gray-900 text-gray-200 hover:border-violet-500/50 hover:bg-gray-800'
              }`}
            >
              {selectionMode ? 'Exit batch select' : 'Select for publishing pilot'}
            </button>
            <button
              type="button"
              onClick={launchPublishingPilot}
              disabled={!selectionMode || selectedCount === 0}
              className="rounded-lg border border-emerald-400/40 bg-emerald-500/15 px-4 py-2 text-sm font-semibold text-emerald-200 transition-colors disabled:cursor-not-allowed disabled:border-gray-800 disabled:bg-gray-900 disabled:text-gray-500"
            >
              Launch marketing handoff
            </button>
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-[repeat(auto-fill,minmax(250px,1fr))] md:gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="aspect-[3/4] animate-pulse rounded-xl border border-gray-800 bg-gray-900" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-red-800/50 bg-gray-900 p-8 text-center">
          <p className="text-red-400">Failed to load ready-to-go images.</p>
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="Ready to Go 이미지가 없습니다"
          description="갤러리에서 초록 체크로 ready 상태를 지정하면 이곳에 모입니다."
          action={{ label: 'Gallery 열기', onClick: () => navigate('/gallery') }}
        />
      ) : (
        <>
          <GalleryGrid
            items={items}
            onItemClick={(item) => navigate(`/gallery/${item.id}`)}
            onImageClick={(_item, index) => setSelectedIndex(index)}
            onRegenerateClick={(item) => navigate(`/generate?from=${item.id}`)}
            selectionMode={selectionMode}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
          />
          <div className="flex flex-col items-center gap-2 pt-3">
            {isFetchingNextPage && (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
                Loading more ready images...
              </div>
            )}
            {!hasNextPage && items.length > 0 && (
              <p className="text-sm text-gray-500">All ready images are loaded</p>
            )}
            {total > 0 && (
              <p className="text-xs text-gray-500">
                Loaded {items.length} / {total} ready images
              </p>
            )}
          </div>
          <div ref={sentinelRef} className="h-8 w-full" aria-hidden="true" />
          <Lightbox
            isOpen={safeSelectedIndex !== null}
            items={items}
            currentIndex={safeSelectedIndex ?? 0}
            onClose={() => setSelectedIndex(null)}
            onIndexChange={(index) => setSelectedIndex(index)}
          />
        </>
      )}
    </div>
  )
}
