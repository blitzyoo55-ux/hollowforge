import { useState, useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient, type InfiniteData } from '@tanstack/react-query'
import {
  addToCollection,
  getCollections,
  toggleFavorite,
  toggleReadyToGo,
  pinGenerationToDirection,
  type GenerationResponse,
  type PaginatedResponse,
} from '../api/client'
import { notify } from '../lib/toast'

interface GalleryGridProps {
  items: GenerationResponse[]
  onItemClick: (item: GenerationResponse) => void
  onImageClick?: (item: GenerationResponse, index: number) => void
  onRegenerateClick?: (item: GenerationResponse) => void
  selectionMode?: boolean
  selectedIds?: Set<string>
  onToggleSelect?: (item: GenerationResponse) => void
}

export default function GalleryGrid({
  items,
  onItemClick,
  onImageClick,
  onRegenerateClick,
  selectionMode = false,
  selectedIds,
  onToggleSelect,
}: GalleryGridProps) {
  const queryClient = useQueryClient()
  const [openCollectionMenuFor, setOpenCollectionMenuFor] = useState<string | null>(null)
  const [pendingFavoriteIds, setPendingFavoriteIds] = useState<Set<string>>(new Set())
  const [pendingReadyIds, setPendingReadyIds] = useState<Set<string>>(new Set())

  const { data: collections } = useQuery({
    queryKey: ['collections'],
    queryFn: () => getCollections(),
  })

  const favoriteMutation = useMutation({
    mutationFn: (generationId: string) => toggleFavorite(generationId),
    onMutate: (generationId: string) => {
      setPendingFavoriteIds((prev) => new Set(prev).add(generationId))
    },
    onSuccess: (data) => {
      // Update the infinite query cache in-place without refetching all pages
      queryClient.setQueriesData<InfiniteData<PaginatedResponse<GenerationResponse>>>(
        { queryKey: ['gallery'] },
        (old) => {
          if (!old) return old
          return {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((item) =>
                item.id === data.id ? { ...item, is_favorite: data.is_favorite } : item,
              ),
            })),
          }
        },
      )
      queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
      queryClient.invalidateQueries({ queryKey: ['ready-gallery'] })
      queryClient.invalidateQueries({ queryKey: ['generation', data.id] })
    },
    onSettled: (_data, _error, generationId) => {
      setPendingFavoriteIds((prev) => {
        const next = new Set(prev)
        next.delete(generationId)
        return next
      })
    },
  })

  const readyMutation = useMutation({
    mutationFn: (generationId: string) => toggleReadyToGo(generationId),
    onMutate: (generationId: string) => {
      setPendingReadyIds((prev) => new Set(prev).add(generationId))
    },
    onSuccess: (data) => {
      queryClient.setQueriesData<InfiniteData<PaginatedResponse<GenerationResponse>>>(
        { queryKey: ['gallery'] },
        (old) => {
          if (!old) return old
          return {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((item) =>
                item.id === data.id ? { ...item, publish_approved: data.publish_approved } : item,
              ),
            })),
          }
        },
      )
      queryClient.setQueriesData<InfiniteData<PaginatedResponse<GenerationResponse>>>(
        { queryKey: ['ready-gallery'] },
        (old) => {
          if (!old) return old
          return {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((item) =>
                item.id === data.id ? { ...item, publish_approved: data.publish_approved } : item,
              ),
            })),
          }
        },
      )
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
      queryClient.invalidateQueries({ queryKey: ['ready-gallery'] })
      queryClient.invalidateQueries({ queryKey: ['generation', data.id] })
    },
    onSettled: (_data, _error, generationId) => {
      setPendingReadyIds((prev) => {
        const next = new Set(prev)
        next.delete(generationId)
        return next
      })
    },
  })

  const addToCollectionMutation = useMutation({
    mutationFn: ({ collectionId, generationId }: { collectionId: string; generationId: string }) => (
      addToCollection(collectionId, generationId)
    ),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      queryClient.invalidateQueries({ queryKey: ['collection'] })
      queryClient.invalidateQueries({ queryKey: ['collections', vars.generationId] })
      setOpenCollectionMenuFor(null)
    },
  })

  const pinMutation = useMutation({
    mutationFn: (generationId: string) => pinGenerationToDirection(generationId),
    onSuccess: () => {
      notify.success('Pinned to Direction Board')
    },
    onError: () => {
      notify.error('Failed to pin')
    },
  })

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <svg className="w-16 h-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
        </svg>
        <p className="text-lg font-medium">No images yet</p>
        <p className="text-sm mt-1">Generate your first image!</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-[repeat(auto-fill,minmax(250px,1fr))] md:gap-4">
      {items.map((item, index) => {
        const isSelected = !!(selectionMode && selectedIds?.has(item.id))

        const activateCard = () => {
          if (selectionMode) {
            onToggleSelect?.(item)
            return
          }
          if (onImageClick) {
            onImageClick(item, index)
            return
          }
          onItemClick(item)
        }

        return (
          <div
            key={item.id}
            role="button"
            tabIndex={0}
            onClick={activateCard}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                activateCard()
              }
            }}
            className={`group relative aspect-[3/4] bg-gray-900 rounded-xl border overflow-hidden transition-colors duration-200 text-left ${
              isSelected
                ? 'border-violet-500 ring-2 ring-violet-500/40'
                : 'border-gray-800 hover:border-violet-500/50'
            }`}
          >
            {(item.upscaled_preview_path || item.thumbnail_path) ? (
              <LazyImage
                src={`/data/${item.upscaled_preview_path || item.thumbnail_path}`}
                alt={item.prompt.slice(0, 80)}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-700">
                <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                </svg>
              </div>
            )}

            {selectionMode && (
              <div className="absolute top-3 left-3 z-20">
                <div
                  className={`h-6 w-6 rounded-md border flex items-center justify-center ${
                    isSelected
                      ? 'bg-violet-500 border-violet-300 text-white'
                      : 'bg-black/55 border-white/40 text-transparent'
                  }`}
                  aria-hidden="true"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              </div>
            )}

            {item.upscaled_image_path && (
              <div
                className={`absolute bg-blue-600/80 text-white text-[10px] font-semibold px-2 py-1 rounded-full border border-blue-300/40 ${
                  selectionMode ? 'top-12 left-3' : 'top-3 left-3'
                }`}
              >
                UPSCALED
              </div>
            )}

            {item.publish_approved === 1 && (
              <div
                className={`absolute bg-emerald-600/85 text-white text-[10px] font-semibold px-2 py-1 rounded-full border border-emerald-300/40 ${
                  selectionMode || item.upscaled_image_path ? 'top-20 left-3' : 'top-12 left-3'
                }`}
              >
                READY
              </div>
            )}

            {!selectionMode && (
              <div className="absolute top-3 right-3 z-20 flex items-start gap-2">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!pendingFavoriteIds.has(item.id)) {
                      favoriteMutation.mutate(item.id)
                    }
                  }}
                  disabled={pendingFavoriteIds.has(item.id)}
                  className={`rounded-lg p-2 border transition-all duration-150 ${
                    item.is_favorite
                      ? 'opacity-100 bg-amber-500/85 border-amber-300/60 text-white'
                      : 'opacity-100 md:opacity-0 md:group-hover:opacity-100 bg-black/50 hover:bg-black/70 border-white/20 text-gray-200'
                  }`}
                  aria-label="Toggle favorite"
                  title="Favorite"
                >
                  <span className="text-sm leading-none">★</span>
                </button>

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!pendingReadyIds.has(item.id)) {
                      readyMutation.mutate(item.id)
                    }
                  }}
                  disabled={pendingReadyIds.has(item.id)}
                  className={`rounded-lg p-2 border transition-all duration-150 ${
                    item.publish_approved === 1
                      ? 'opacity-100 bg-emerald-500/85 border-emerald-300/60 text-white'
                      : 'opacity-100 md:opacity-0 md:group-hover:opacity-100 bg-black/50 hover:bg-black/70 border-white/20 text-gray-200'
                  }`}
                  aria-label="Toggle ready to go"
                  title={item.publish_approved === 1 ? 'Remove from Ready to Go' : 'Mark as Ready to Go'}
                >
                  <span className="text-sm leading-none">✓</span>
                </button>

                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    pinMutation.mutate(item.id)
                  }}
                  disabled={pinMutation.isPending}
                  className="rounded-lg p-2 border bg-black/50 hover:bg-black/70 border-white/20 text-gray-200 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-150 disabled:opacity-40"
                  aria-label="Pin to Direction Board"
                  title="Pin to Direction Board"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.5-2.25v7.5l-4.5-2.25M3.75 6A2.25 2.25 0 016 3.75h8.25A2.25 2.25 0 0116.5 6v8.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6z" />
                  </svg>
                </button>

                <div className="relative">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setOpenCollectionMenuFor((prev) => (prev === item.id ? null : item.id))
                    }}
                    className="rounded-lg p-2 border bg-black/50 hover:bg-black/70 border-white/20 text-gray-200 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-150"
                    aria-label="Add to collection"
                    title="Add to Collection"
                  >
                    <span className="text-sm leading-none">+</span>
                  </button>

                  {openCollectionMenuFor === item.id && (
                    <div
                      className="absolute right-0 mt-2 w-56 bg-gray-900 border border-gray-700 rounded-lg shadow-xl p-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <p className="text-[11px] text-gray-500 px-2 py-1.5 uppercase tracking-wide">Add to Collection</p>
                      {!collections || collections.length === 0 ? (
                        <p className="text-xs text-gray-500 px-2 py-2">No collections yet</p>
                      ) : (
                        <div className="max-h-56 overflow-y-auto">
                          {collections.map((collection) => (
                            <button
                              key={collection.id}
                              type="button"
                              onClick={() => {
                                addToCollectionMutation.mutate({
                                  collectionId: collection.id,
                                  generationId: item.id,
                                })
                              }}
                              className="w-full text-left text-sm px-2 py-1.5 text-gray-300 rounded hover:bg-gray-800 transition-colors"
                            >
                              {collection.name}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div
              className={`absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent transition-opacity duration-200 flex flex-col justify-end p-4 ${
                selectionMode ? 'opacity-100' : 'opacity-100 md:opacity-0 md:group-hover:opacity-100'
              }`}
            >
              {onRegenerateClick && !selectionMode && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    onRegenerateClick(item)
                  }}
                  className="absolute top-3 left-3 bg-black/50 hover:bg-black/70 text-white rounded-lg p-2 border border-white/20 transition-colors duration-200"
                  aria-label="Edit and regenerate"
                  title="Edit & Regenerate"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                  </svg>
                </button>
              )}
              <p className="text-sm text-gray-200 line-clamp-2">{item.prompt}</p>
              <div className="flex items-center gap-2 mt-2 text-xs text-gray-400">
                <span>{item.checkpoint}</span>
                <span>-</span>
                <span>{new Date(item.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Unloads img src when the card is >2000px away from the viewport to reduce
// memory pressure during long infinite-scroll sessions.
function LazyImage({ src, alt }: { src: string; alt: string }) {
  const ref = useRef<HTMLImageElement>(null)
  const [activeSrc, setActiveSrc] = useState<string | undefined>(undefined)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setActiveSrc(src)
        } else {
          setActiveSrc(undefined)
        }
      },
      { rootMargin: '2000px 0px' },
    )

    observer.observe(el)
    return () => observer.disconnect()
  }, [src])

  return (
    <img
      ref={ref}
      src={activeSrc}
      alt={alt}
      className="w-full h-full object-cover"
    />
  )
}
