import { useState, useEffect, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getGallery, getModels } from '../api/client'
import type { GalleryQuery } from '../api/client'
import GalleryGrid from '../components/GalleryGrid'

export default function Gallery() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [checkpoint, setCheckpoint] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc')
  const [page, setPage] = useState(() => {
    const raw = Number(searchParams.get('page') ?? '1')
    return Number.isInteger(raw) && raw > 0 ? raw : 1
  })

  const debouncedSearch = useDebounce(search, 400)

  useEffect(() => {
    const raw = Number(searchParams.get('page') ?? '1')
    const nextPage = Number.isInteger(raw) && raw > 0 ? raw : 1
    if (nextPage !== page) {
      setPage(nextPage)
    }
  }, [searchParams, page])

  useEffect(() => {
    const current = Number(searchParams.get('page') ?? '1')
    if (current === page) return

    const next = new URLSearchParams(searchParams)
    if (page <= 1) {
      next.delete('page')
    } else {
      next.set('page', String(page))
    }
    setSearchParams(next, { replace: true })
  }, [page, searchParams, setSearchParams])

  const queryParams = useMemo<GalleryQuery>(() => ({
    page,
    per_page: 24,
    search: debouncedSearch || undefined,
    checkpoint: checkpoint || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    sort_order: sortOrder,
  }), [page, debouncedSearch, checkpoint, dateFrom, dateTo, sortOrder])

  const { data, isLoading, isError } = useQuery({
    queryKey: ['gallery', queryParams],
    queryFn: () => getGallery(queryParams),
  })

  useEffect(() => {
    if (!data) return
    if (page > data.total_pages) {
      setPage(data.total_pages)
    }
  }, [data, page])

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: getModels,
  })
  const filterableCheckpoints = models?.checkpoints_all ?? models?.checkpoints ?? []

  const visiblePages = useMemo(() => {
    if (!data) return []

    const total = data.total_pages
    const current = data.page
    const pages: Array<number | 'ellipsis'> = []

    const addPage = (p: number) => {
      if (!pages.includes(p)) pages.push(p)
    }

    addPage(1)
    if (current - 1 > 2) pages.push('ellipsis')
    for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p += 1) {
      addPage(p)
    }
    if (current + 1 < total - 1) pages.push('ellipsis')
    if (total > 1) addPage(total)

    return pages
  }, [data])

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Gallery</h2>
        <p className="text-sm text-gray-400 mt-1">Browse your generated images</p>
      </div>

      {/* Filter bar */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <div className="flex flex-wrap gap-3">
          {/* Search */}
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              placeholder="Search prompts..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
          </div>

          {/* Checkpoint filter */}
          <select
            value={checkpoint}
            onChange={(e) => { setCheckpoint(e.target.value); setPage(1) }}
            className="bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
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
            onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
            className="bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          />

          {/* Date to */}
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
            className="bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          />

          {/* Sort */}
          <select
            value={sortOrder}
            onChange={(e) => { setSortOrder(e.target.value as 'desc' | 'asc'); setPage(1) }}
            className="bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          >
            <option value="desc">Newest first</option>
            <option value="asc">Oldest first</option>
          </select>
        </div>
      </div>

      {/* Results */}
      {isLoading ? (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(250px,1fr))] gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="aspect-[3/4] bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="bg-gray-900 rounded-xl border border-red-800/50 p-8 text-center">
          <p className="text-red-400">Failed to load gallery. Is the backend running?</p>
        </div>
      ) : (
        <>
          <GalleryGrid
            items={data?.items ?? []}
            onItemClick={(item) => navigate(`/gallery/${item.id}`)}
            onRegenerateClick={(item) => navigate(`/generate?from=${item.id}`)}
          />

          {data && data.total_pages > 1 && (
            <div className="flex flex-col items-center gap-3 pt-2">
              <p className="text-xs text-gray-500">
                Page {data.page} of {data.total_pages} ({data.total} images)
              </p>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={data.page === 1}
                  className="px-3 py-1.5 rounded-lg text-sm border border-gray-700 text-gray-300 bg-gray-900 hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {'<'}
                </button>

                {visiblePages.map((entry, idx) => {
                  if (entry === 'ellipsis') {
                    return (
                      <span key={`ellipsis-${idx}`} className="px-2 text-gray-500">
                        ...
                      </span>
                    )
                  }

                  const isActive = entry === data.page
                  return (
                    <button
                      key={entry}
                      onClick={() => setPage(entry)}
                      className={`min-w-9 px-3 py-1.5 rounded-lg text-sm border transition-colors duration-150 ${
                        isActive
                          ? 'bg-violet-600 border-violet-500 text-white'
                          : 'bg-gray-900 border-gray-700 text-gray-300 hover:bg-gray-800'
                      }`}
                    >
                      {entry}
                    </button>
                  )
                })}

                <button
                  onClick={() => setPage((p) => Math.min(data.total_pages, p + 1))}
                  disabled={data.page === data.total_pages}
                  className="px-3 py-1.5 rounded-lg text-sm border border-gray-700 text-gray-300 bg-gray-900 hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {'>'}
                </button>
              </div>
            </div>
          )}
        </>
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
