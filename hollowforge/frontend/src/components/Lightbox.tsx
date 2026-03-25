import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactDOM from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toggleFavorite, toggleReadyToGo, type GenerationResponse } from '../api/client'

interface LightboxProps {
  isOpen: boolean
  items: GenerationResponse[]
  currentIndex: number
  onClose: () => void
  onIndexChange: (index: number) => void
}

function resolveImagePath(item: GenerationResponse): string | null {
  return (
    item.upscaled_preview_path
    || item.upscaled_image_path
    || item.image_path
    || item.thumbnail_path
  )
}

export default function Lightbox({
  isOpen,
  items,
  currentIndex,
  onClose,
  onIndexChange,
}: LightboxProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [favoriteOverrides, setFavoriteOverrides] = useState<Record<string, boolean>>({})
  const [readyOverrides, setReadyOverrides] = useState<Record<string, number>>({})

  const currentItem = useMemo(
    () => (currentIndex >= 0 && currentIndex < items.length ? items[currentIndex] : null),
    [currentIndex, items],
  )

  const canGoPrev = currentIndex > 0
  const canGoNext = currentIndex < items.length - 1

  const goPrev = useCallback(() => {
    if (!canGoPrev) return
    onIndexChange(currentIndex - 1)
  }, [canGoPrev, currentIndex, onIndexChange])

  const goNext = useCallback(() => {
    if (!canGoNext) return
    onIndexChange(currentIndex + 1)
  }, [canGoNext, currentIndex, onIndexChange])

  const favoriteMutation = useMutation({
    mutationFn: (generationId: string) => toggleFavorite(generationId),
    onSuccess: (data) => {
      setFavoriteOverrides((prev) => ({ ...prev, [data.id]: data.is_favorite }))
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
      queryClient.invalidateQueries({ queryKey: ['ready-gallery'] })
      queryClient.invalidateQueries({ queryKey: ['generation', data.id] })
    },
  })

  const readyMutation = useMutation({
    mutationFn: (generationId: string) => toggleReadyToGo(generationId),
    onSuccess: (data) => {
      setReadyOverrides((prev) => ({ ...prev, [data.id]: data.publish_approved }))
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
      queryClient.invalidateQueries({ queryKey: ['ready-gallery'] })
      queryClient.invalidateQueries({ queryKey: ['generation', data.id] })
    },
  })

  useEffect(() => {
    if (!isOpen) return

    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
        return
      }
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        goPrev()
        return
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        goNext()
      }
    }

    document.addEventListener('keydown', onKeyDown)

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = originalOverflow
    }
  }, [goNext, goPrev, isOpen, onClose])

  if (!isOpen || !currentItem) return null

  const imagePath = resolveImagePath(currentItem)
  const isFavorite = favoriteOverrides[currentItem.id] ?? currentItem.is_favorite
  const isReadyToGo = (readyOverrides[currentItem.id] ?? currentItem.publish_approved ?? 0) === 1

  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 z-50 bg-black/90 backdrop-blur-sm"
      onClick={onClose}
      aria-modal="true"
      role="dialog"
    >
      <div
        className="absolute inset-0 flex items-center justify-center p-3 sm:p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="relative flex h-full w-full max-w-[96vw] max-h-[96vh] flex-col overflow-hidden rounded-xl border border-gray-800 bg-gray-950/95 shadow-2xl">
          <button
            type="button"
            onClick={onClose}
            className="absolute right-3 top-3 z-20 rounded-lg border border-white/20 bg-black/50 px-2 py-1 text-sm text-gray-100 hover:bg-black/70"
            aria-label="Close lightbox"
          >
            ESC
          </button>

          <button
            type="button"
            onClick={goPrev}
            disabled={!canGoPrev}
            className="absolute left-3 top-1/2 z-20 -translate-y-1/2 rounded-full border border-white/20 bg-black/50 p-3 text-white hover:bg-black/70 disabled:cursor-not-allowed disabled:opacity-30"
            aria-label="Previous image"
          >
            <span className="text-lg leading-none">‹</span>
          </button>

          <button
            type="button"
            onClick={goNext}
            disabled={!canGoNext}
            className="absolute right-3 top-1/2 z-20 -translate-y-1/2 rounded-full border border-white/20 bg-black/50 p-3 text-white hover:bg-black/70 disabled:cursor-not-allowed disabled:opacity-30"
            aria-label="Next image"
          >
            <span className="text-lg leading-none">›</span>
          </button>

          <div className="flex min-h-0 flex-1 items-center justify-center px-4 pt-12 pb-4 sm:px-8">
            {imagePath ? (
              <img
                src={`/data/${imagePath}`}
                alt={currentItem.prompt.slice(0, 120)}
                className="max-h-[90vh] max-w-[90vw] object-contain"
              />
            ) : (
              <div className="flex h-[50vh] w-full items-center justify-center rounded-lg border border-gray-800 bg-gray-900 text-sm text-gray-500">
                No image available
              </div>
            )}
          </div>

          <div className="border-t border-gray-800 bg-gray-900/80 px-4 py-3 sm:px-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-gray-300">
                {currentIndex + 1} / {items.length}
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => favoriteMutation.mutate(currentItem.id)}
                  disabled={favoriteMutation.isPending}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                    isFavorite
                      ? 'border-amber-300/50 bg-amber-500/20 text-amber-300'
                      : 'border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700'
                  }`}
                >
                  {isFavorite ? '★ Favorited' : '☆ Favorite'}
                </button>
                <button
                  type="button"
                  onClick={() => readyMutation.mutate(currentItem.id)}
                  disabled={readyMutation.isPending}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                    isReadyToGo
                      ? 'border-emerald-300/50 bg-emerald-500/20 text-emerald-300'
                      : 'border-gray-700 bg-gray-800 text-gray-200 hover:bg-gray-700'
                  }`}
                >
                  {isReadyToGo ? '✓ Ready to Go' : '○ Ready to Go'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onClose()
                    navigate(`/gallery/${currentItem.id}`)
                  }}
                  className="rounded-lg border border-violet-500/50 bg-violet-600/20 px-3 py-1.5 text-xs font-medium text-violet-300 hover:bg-violet-600/30"
                >
                  View Detail
                </button>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-300 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wide text-gray-500">Checkpoint</p>
                <p className="mt-1 truncate font-mono text-gray-200">{currentItem.checkpoint}</p>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wide text-gray-500">Seed</p>
                <p className="mt-1 font-mono text-gray-200">{currentItem.seed}</p>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wide text-gray-500">Steps</p>
                <p className="mt-1 font-mono text-gray-200">{currentItem.steps}</p>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2">
                <p className="text-[11px] uppercase tracking-wide text-gray-500">Created</p>
                <p className="mt-1 text-gray-200">{new Date(currentItem.created_at).toLocaleString()}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
