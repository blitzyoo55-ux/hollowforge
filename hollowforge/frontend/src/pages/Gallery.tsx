import { useState, useEffect, useMemo, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { getGallery, getModels } from '../api/client'
import type { GalleryQuery } from '../api/client'
import EmptyState from '../components/EmptyState'
import GalleryGrid from '../components/GalleryGrid'
import ExportModal from '../components/ExportModal'
import Lightbox from '../components/Lightbox'
import { notify } from '../lib/toast'

export default function Gallery() {
  const navigate = useNavigate()
  const location = useLocation()
  const [search, setSearch] = useState('')
  const [checkpoint, setCheckpoint] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  const [favoritesOnly, setFavoritesOnly] = useState(false)
  const [readyToPublish, setReadyToPublish] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const [isSelectMode, setIsSelectMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [showExportModal, setShowExportModal] = useState(false)
  const sentinelRef = useRef<HTMLDivElement | null>(null)

  const debouncedSearch = useDebounce(search, 400)

  const queryParams = useMemo<GalleryQuery>(() => ({
    per_page: 24,
    search: debouncedSearch || undefined,
    checkpoint: checkpoint || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    favorites: favoritesOnly || undefined,
    sort_order: sortOrder,
    publish_approved: readyToPublish ? 1 : undefined,
  }), [debouncedSearch, checkpoint, dateFrom, dateTo, favoritesOnly, sortOrder, readyToPublish])

  const { data, isLoading, isError, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
    queryKey: ['gallery', queryParams],
    queryFn: ({ pageParam = 1 }) => getGallery({ ...queryParams, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (
      lastPage.page < lastPage.total_pages ? lastPage.page + 1 : undefined
    ),
  })

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: getModels,
  })
  const filterableCheckpoints = models?.checkpoints_all ?? models?.checkpoints ?? []

  const items = useMemo(() => (
    data?.pages.flatMap((pageData) => pageData.items) ?? []
  ), [data])

  const total = data?.pages[0]?.total ?? 0
  const safeSelectedIndex =
    selectedIndex === null || items.length === 0
      ? null
      : Math.min(selectedIndex, items.length - 1)

  const toggleSelection = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  const enterSelectMode = () => {
    setIsSelectMode(true)
    setSelectedIndex(null)
  }

  const exitSelectMode = () => {
    setIsSelectMode(false)
    setSelectedIds(new Set())
    setShowExportModal(false)
  }

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

  useEffect(() => {
    const state = location.state as { deleteToast?: 'success' | 'error' } | null
    const stateToast = state?.deleteToast
    const storedToast = sessionStorage.getItem('hf_gallery_delete_toast')
    const toastType =
      stateToast ??
      (storedToast === 'success' || storedToast === 'error' ? storedToast : null)

    if (!toastType) return

    if (toastType === 'success') {
      notify.success('이미지가 삭제되었습니다')
    } else {
      notify.error('이미지 삭제에 실패했습니다')
    }

    sessionStorage.removeItem('hf_gallery_delete_toast')

    if (stateToast) {
      navigate(location.pathname + location.search, { replace: true, state: null })
    }
  }, [location.pathname, location.search, location.state, navigate])

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Gallery</h2>
          <p className="text-sm text-gray-400 mt-1">Browse your generated images</p>
        </div>
        {isSelectMode ? (
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <span className="text-sm text-gray-300">{selectedIds.size} selected</span>
            <button
              type="button"
              onClick={() => setShowExportModal(true)}
              disabled={selectedIds.size === 0}
              className="w-full rounded-lg bg-violet-600 px-3 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              Export Selected
            </button>
            <button
              type="button"
              onClick={exitSelectMode}
              className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 sm:w-auto"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={enterSelectMode}
            className="w-full rounded-lg bg-gray-800 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 sm:w-auto"
          >
            Select
          </button>
        )}
      </div>

      {/* Filter bar */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6">
          {/* Search */}
          <div className="w-full sm:col-span-2 xl:col-span-2">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search prompts..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
          </div>

          {/* Checkpoint filter */}
          <select
            value={checkpoint}
            onChange={(e) => setCheckpoint(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          >
            <option value="">All checkpoints</option>
            {filterableCheckpoints.map((cp) => (
              <option key={cp} value={cp}>{cp}</option>
            ))}
          </select>

          {/* Date from */}
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          />

          {/* Date to */}
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          />

          {/* Sort */}
          <select
            value={sortOrder}
            onChange={(e) => setSortOrder(e.target.value as 'desc' | 'asc')}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          >
            <option value="desc">Newest first</option>
            <option value="asc">Oldest first</option>
          </select>

          <button
            type="button"
            onClick={() => setFavoritesOnly((prev) => !prev)}
            className={`w-full rounded-lg px-3 py-2 text-sm border transition-colors duration-150 ${
              favoritesOnly
                ? 'bg-violet-600/20 border-violet-500/50 text-violet-300'
                : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'
            }`}
          >
            Favorites Only
          </button>

          <button
            type="button"
            onClick={() => setReadyToPublish((prev) => !prev)}
            className={`w-full rounded-lg px-3 py-2 text-sm border transition-colors duration-150 ${
              readyToPublish
                ? 'bg-green-600/20 border-green-500/50 text-green-300'
                : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'
            }`}
          >
            Ready to Go
          </button>
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-[repeat(auto-fill,minmax(250px,1fr))] md:gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="aspect-[3/4] bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="bg-gray-900 rounded-xl border border-red-800/50 p-8 text-center">
          <p className="text-red-400">Failed to load gallery. Is the backend running?</p>
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="아직 생성된 이미지가 없습니다"
          description="프롬프트를 입력하고 첫 이미지를 생성해보세요."
          action={{ label: '생성 시작하기', onClick: () => navigate('/generate') }}
        />
      ) : (
        <>
          <GalleryGrid
            items={items}
            onItemClick={(item) => navigate(`/gallery/${item.id}`)}
            onImageClick={(item, index) => {
              if (isSelectMode) {
                toggleSelection(item.id)
                return
              }
              setSelectedIndex(index)
            }}
            onRegenerateClick={(item) => navigate(`/generate?from=${item.id}`)}
            selectionMode={isSelectMode}
            selectedIds={selectedIds}
            onToggleSelect={(item) => toggleSelection(item.id)}
          />
          <div className="flex flex-col items-center gap-2 pt-3">
            {isFetchingNextPage && (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-400" />
                Loading more images...
              </div>
            )}
            {!hasNextPage && items.length > 0 && (
              <p className="text-sm text-gray-500">모든 이미지를 불러왔습니다</p>
            )}
            {total > 0 && (
              <p className="text-xs text-gray-500">
                Loaded {items.length} / {total} images
              </p>
            )}
          </div>
          <div ref={sentinelRef} className="h-8 w-full" aria-hidden="true" />
          <Lightbox
            isOpen={!isSelectMode && safeSelectedIndex !== null}
            items={items}
            currentIndex={safeSelectedIndex ?? 0}
            onClose={() => setSelectedIndex(null)}
            onIndexChange={(index) => setSelectedIndex(index)}
          />
        </>
      )}
      {showExportModal && (
        <ExportModal
          selectedIds={Array.from(selectedIds)}
          onClose={() => setShowExportModal(false)}
        />
      )}
    </div>
  )
}

function useDebounce(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const handler = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])

  return debounced
}
