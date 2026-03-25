import { useEffect, useCallback, useRef } from 'react'
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getCurationQueue,
  approveCurationItem,
  rejectCurationItem,
  recalculateCurationScores,
  autoApproveCuration,
  toggleFavorite,
  getCollections,
  addToCollection,
  type CurationItem,
  type CollectionResponse,
} from '../api/client'
import EmptyState from '../components/EmptyState'
import { notify } from '../lib/toast'

function QualityBadge({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <span className="inline-flex items-center rounded-full bg-gray-700 px-2.5 py-0.5 text-xs font-medium text-gray-300">
        Unscored
      </span>
    )
  }
  if (score >= 80) {
    return (
      <span className="inline-flex items-center rounded-full bg-green-900/60 border border-green-700/50 px-2.5 py-0.5 text-xs font-medium text-green-300">
        High ({score})
      </span>
    )
  }
  if (score >= 60) {
    return (
      <span className="inline-flex items-center rounded-full bg-yellow-900/60 border border-yellow-700/50 px-2.5 py-0.5 text-xs font-medium text-yellow-300">
        Medium ({score})
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full bg-red-900/60 border border-red-700/50 px-2.5 py-0.5 text-xs font-medium text-red-300">
      Low ({score})
    </span>
  )
}

function parseTags(tags: string | null): string[] {
  if (!tags) return []
  try {
    const parsed = JSON.parse(tags)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export default function CurationPage() {
  const queryClient = useQueryClient()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [collectionOpen, setCollectionOpen] = useState(false)
  const collectionDropdownRef = useRef<HTMLDivElement>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['curation-queue'],
    queryFn: getCurationQueue,
  })

  const { data: collections } = useQuery({
    queryKey: ['collections'],
    queryFn: () => getCollections(),
  })

  const items: CurationItem[] = data?.items ?? []
  const pendingCount = items.length
  const approvedToday = data?.approved_today ?? 0

  const safeIndex = Math.min(currentIndex, Math.max(0, items.length - 1))
  const current = items[safeIndex] ?? null

  const approveMutation = useMutation({
    mutationFn: (id: string) => approveCurationItem(id),
    onSuccess: () => {
      notify.success('Approved')
      queryClient.invalidateQueries({ queryKey: ['curation-queue'] })
      setCurrentIndex((prev) => Math.min(prev, items.length - 2))
    },
    onError: () => notify.error('Failed to approve'),
  })

  const rejectMutation = useMutation({
    mutationFn: (id: string) => rejectCurationItem(id),
    onSuccess: () => {
      notify.error('Rejected')
      queryClient.invalidateQueries({ queryKey: ['curation-queue'] })
      setCurrentIndex((prev) => Math.min(prev, items.length - 2))
    },
    onError: () => notify.error('Failed to reject'),
  })

  const recalcMutation = useMutation({
    mutationFn: recalculateCurationScores,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['curation-queue'] })
      notify.success('Scores recalculated')
    },
    onError: () => notify.error('Failed to recalculate'),
  })

  const autoApproveMutation = useMutation({
    mutationFn: () => autoApproveCuration(70),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['curation-queue'] })
      notify.success(`Auto-approved ${res.approved} items`)
    },
    onError: () => notify.error('Auto-approve failed'),
  })

  const favoriteMutation = useMutation({
    mutationFn: (id: string) => toggleFavorite(id),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['curation-queue'] })
      notify.success(res.is_favorite ? 'Added to favorites' : 'Removed from favorites')
    },
    onError: () => notify.error('Failed to toggle favorite'),
  })

  const addToCollectionMutation = useMutation({
    mutationFn: ({ collectionId, generationId }: { collectionId: string; generationId: string }) =>
      addToCollection(collectionId, generationId),
    onSuccess: () => {
      setCollectionOpen(false)
      notify.success('Added to collection')
    },
    onError: () => notify.error('Failed to add to collection'),
  })

  // Close collection dropdown on outside click
  useEffect(() => {
    if (!collectionOpen) return
    const handler = (e: MouseEvent) => {
      if (collectionDropdownRef.current && !collectionDropdownRef.current.contains(e.target as Node)) {
        setCollectionOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [collectionOpen])

  const handleApprove = useCallback(() => {
    if (!current || approveMutation.isPending) return
    approveMutation.mutate(current.id)
  }, [current, approveMutation])

  const handleReject = useCallback(() => {
    if (!current || rejectMutation.isPending) return
    rejectMutation.mutate(current.id)
  }, [current, rejectMutation])

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      switch (e.key) {
        case 'ArrowLeft':
          setCurrentIndex((prev) => Math.max(0, prev - 1))
          break
        case 'ArrowRight':
          setCurrentIndex((prev) => Math.min(items.length - 1, prev + 1))
          break
        case ' ':
          e.preventDefault()
          handleApprove()
          break
        case 'Delete':
        case 'Backspace':
          e.preventDefault()
          handleReject()
          break
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [items.length, handleApprove, handleReject])

  const imageUrl = current
    ? current.upscaled_preview_path
      ? `/data/${current.upscaled_preview_path}`
      : current.thumbnail_path
        ? `/data/${current.thumbnail_path}`
        : current.image_path
          ? `/data/${current.image_path}`
          : null
    : null

  const tags = parseTags(current?.tags ?? null)
  const isBusy = approveMutation.isPending || rejectMutation.isPending

  return (
    <div className="flex flex-col gap-0 min-h-0 md:h-[calc(100vh-8rem)]">
      {/* Top bar */}
      <div className="flex flex-col gap-3 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Curation Queue</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            {pendingCount} pending &middot; {approvedToday} approved today
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <button
            type="button"
            onClick={() => recalcMutation.mutate()}
            disabled={recalcMutation.isPending}
            className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-50 sm:w-auto"
          >
            {recalcMutation.isPending ? 'Recalculating...' : 'Recalc Scores'}
          </button>
          <button
            type="button"
            onClick={() => autoApproveMutation.mutate()}
            disabled={autoApproveMutation.isPending}
            className="w-full rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 px-3 py-2 text-sm font-medium text-white sm:w-auto"
          >
            {autoApproveMutation.isPending ? 'Running...' : 'Auto-Approve ≥70'}
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex flex-1 items-center justify-center">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-400" />
        </div>
      ) : isError ? (
        <div className="bg-gray-900 rounded-xl border border-red-800/50 p-8 text-center">
          <p className="text-red-400">Failed to load curation queue. Is the backend running?</p>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <EmptyState
            title="Queue empty!"
            description="All items have been reviewed. Generate more images or recalculate scores."
          />
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-4 min-h-0 xl:flex-row">
          {/* Main image area */}
          <div className="flex flex-col flex-1 gap-3 min-w-0">
            {/* Navigation hint */}
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-gray-500">
              <span>← → navigate</span>
              <span>Space = approve</span>
              <span>Delete = reject</span>
              <span className="text-gray-600">{safeIndex + 1} / {items.length}</span>
            </div>

            {/* Image */}
            <div className="relative flex-1 flex items-center justify-center bg-gray-950 rounded-xl border border-gray-800 overflow-hidden min-h-[48vh] xl:min-h-0">
              {imageUrl ? (
                <img
                  key={current?.id}
                  src={imageUrl}
                  alt={current?.prompt?.slice(0, 80)}
                  className="max-h-full max-w-full object-contain"
                />
              ) : (
                <div className="flex flex-col items-center gap-3 text-gray-700">
                  <svg className="w-16 h-16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                  </svg>
                  <p className="text-sm">No image available</p>
                </div>
              )}

              {/* Left/Right navigation arrows */}
              <button
                type="button"
                onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
                disabled={safeIndex === 0}
                className="absolute left-3 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white rounded-lg p-2 border border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                aria-label="Previous"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
                </svg>
              </button>
              <button
                type="button"
                onClick={() => setCurrentIndex((prev) => Math.min(items.length - 1, prev + 1))}
                disabled={safeIndex === items.length - 1}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white rounded-lg p-2 border border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                aria-label="Next"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
              </button>
            </div>

            {/* Bottom action bar */}
            <div className="flex flex-wrap items-center justify-center gap-3">
              <button
                type="button"
                onClick={handleReject}
                disabled={isBusy}
                className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl bg-red-600/20 border border-red-500/50 hover:bg-red-600/30 text-red-300 px-6 py-3 text-base font-semibold disabled:opacity-50 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
                Reject
              </button>
              <button
                type="button"
                onClick={handleApprove}
                disabled={isBusy}
                className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl bg-green-600/20 border border-green-500/50 hover:bg-green-600/30 text-green-300 px-6 py-3 text-base font-semibold disabled:opacity-50 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
                Approve
              </button>

              {/* Favorite toggle */}
              <button
                type="button"
                onClick={() => current && favoriteMutation.mutate(current.id)}
                disabled={!current || favoriteMutation.isPending}
                title={current?.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
                className={`w-full sm:w-auto rounded-xl border px-4 py-3 text-xl disabled:opacity-50 transition-colors ${
                  current?.is_favorite
                    ? 'bg-yellow-500/20 border-yellow-400/50 text-yellow-300 hover:bg-yellow-500/30'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-700 hover:text-yellow-300'
                }`}
              >
                {current?.is_favorite ? '★' : '☆'}
              </button>

              {/* Collection dropdown */}
              <div className="relative" ref={collectionDropdownRef}>
                <button
                  type="button"
                  onClick={() => setCollectionOpen((v) => !v)}
                  disabled={!current}
                  className="w-full sm:w-auto rounded-xl bg-gray-800 border border-gray-700 hover:bg-gray-700 text-gray-300 px-4 py-3 text-sm font-medium disabled:opacity-50 transition-colors flex items-center justify-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                  Collection
                </button>
                {collectionOpen && current && (
                  <div className="absolute bottom-full mb-2 right-0 w-52 bg-gray-900 border border-gray-700 rounded-xl shadow-xl overflow-hidden z-50">
                    {collections && collections.length > 0 ? (
                      collections.map((col: CollectionResponse) => (
                        <button
                          key={col.id}
                          type="button"
                          onClick={() =>
                            addToCollectionMutation.mutate({
                              collectionId: col.id,
                              generationId: current.id,
                            })
                          }
                          disabled={addToCollectionMutation.isPending}
                          className="w-full text-left px-4 py-2.5 text-sm text-gray-300 hover:bg-gray-800 transition-colors truncate disabled:opacity-50"
                        >
                          {col.name}
                        </button>
                      ))
                    ) : (
                      <p className="px-4 py-3 text-xs text-gray-500">No collections yet</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right sidebar: metadata */}
          {current && (
            <div className="w-full xl:w-64 xl:shrink-0 flex flex-col gap-3 overflow-y-auto">
              <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 space-y-3">
                <div>
                  <p className="text-[11px] text-gray-500 uppercase tracking-wide mb-1">Quality Score</p>
                  <QualityBadge score={current.quality_score} />
                </div>
                <div>
                  <p className="text-[11px] text-gray-500 uppercase tracking-wide mb-1">Checkpoint</p>
                  <p className="text-xs text-gray-300 break-all">{current.checkpoint}</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-[11px] text-gray-500 uppercase tracking-wide mb-1">Steps</p>
                    <p className="text-xs text-gray-300">{current.steps}</p>
                  </div>
                  <div>
                    <p className="text-[11px] text-gray-500 uppercase tracking-wide mb-1">CFG</p>
                    <p className="text-xs text-gray-300">{current.cfg}</p>
                  </div>
                </div>
                {tags.length > 0 && (
                  <div>
                    <p className="text-[11px] text-gray-500 uppercase tracking-wide mb-1.5">Tags</p>
                    <div className="flex flex-wrap gap-1">
                      {tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex rounded-full bg-violet-900/40 border border-violet-700/40 px-2 py-0.5 text-[10px] text-violet-300"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <div>
                  <p className="text-[11px] text-gray-500 uppercase tracking-wide mb-1">Prompt</p>
                  <p className="text-xs text-gray-400 line-clamp-6">{current.prompt}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
