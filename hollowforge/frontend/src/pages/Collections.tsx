import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createCollection,
  deleteCollection,
  getCollection,
  getCollections,
  removeFromCollection,
} from '../api/client'
import EmptyState from '../components/EmptyState'

export default function Collections() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const isDetail = Boolean(id)

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDescription, setNewDescription] = useState('')
  const [detailPagesById, setDetailPagesById] = useState<Record<string, number>>({})
  const page = id ? (detailPagesById[id] ?? 1) : 1

  const collectionsQuery = useQuery({
    queryKey: ['collections'],
    queryFn: () => getCollections(),
    enabled: !isDetail,
  })

  const detailQuery = useQuery({
    queryKey: ['collection', id, page],
    queryFn: () => getCollection(id!, page, 48),
    enabled: !!id,
  })

  const createMutation = useMutation({
    mutationFn: () => createCollection({
      name: newName.trim(),
      description: newDescription.trim() || undefined,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      setShowCreateModal(false)
      setNewName('')
      setNewDescription('')
    },
  })

  const removeItemMutation = useMutation({
    mutationFn: ({ collectionId, generationId }: { collectionId: string; generationId: string }) => (
      removeFromCollection(collectionId, generationId)
    ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collection', id] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (collectionId: string) => deleteCollection(collectionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      navigate('/collections')
    },
  })

  const handleCreate = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!newName.trim()) return
    createMutation.mutate()
  }

  if (isDetail) {
    const detail = detailQuery.data

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <Link
              to="/collections"
              className="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-gray-200"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
              Back to Collections
            </Link>
            <h2 className="text-2xl font-bold text-gray-100 mt-2">{detail?.collection.name ?? 'Collection'}</h2>
            <p className="text-sm text-gray-400 mt-1">
              {detail ? `${detail.total} image${detail.total === 1 ? '' : 's'}` : 'Loading...'}
            </p>
          </div>

          {id && (
            <button
              type="button"
              onClick={() => {
                if (window.confirm('Delete this collection? This cannot be undone.')) {
                  deleteMutation.mutate(id)
                }
              }}
              disabled={deleteMutation.isPending}
              className="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium"
            >
              Delete Collection
            </button>
          )}
        </div>

        {detailQuery.isLoading ? (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
            {Array.from({ length: 10 }).map((_, idx) => (
              <div key={idx} className="aspect-[3/4] bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
            ))}
          </div>
        ) : detailQuery.isError || !detail ? (
          <div className="bg-gray-900 border border-red-800/50 rounded-xl p-8 text-center">
            <p className="text-red-400">Failed to load collection</p>
          </div>
        ) : detail.items.length === 0 ? (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
            <p className="text-gray-400">This collection is empty</p>
            <p className="text-sm text-gray-500 mt-1">Add images from Gallery or Image Detail.</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-4">
              {detail.items.map((item) => (
                <div
                  key={item.id}
                  className="group relative aspect-[3/4] rounded-xl border border-gray-800 overflow-hidden bg-gray-900"
                >
                  <button
                    type="button"
                    onClick={() => navigate(`/gallery/${item.id}`)}
                    className="absolute inset-0"
                    aria-label="Open image detail"
                  />

                  {item.thumbnail_path ? (
                    <img
                      src={`/data/${item.thumbnail_path}`}
                      alt={item.prompt.slice(0, 80)}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-700">
                      <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
                      </svg>
                    </div>
                  )}

                  <div className="absolute inset-0 bg-gradient-to-t from-black/70 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      if (!id) return
                      removeItemMutation.mutate({ collectionId: id, generationId: item.id })
                    }}
                    className="absolute top-3 right-3 bg-red-600/90 hover:bg-red-500 text-white rounded-lg px-2.5 py-1.5 text-xs font-medium border border-red-300/30"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            {detail.total_pages > 1 && (
              <div className="flex items-center justify-center gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    if (!id) return
                    setDetailPagesById((prev) => ({
                      ...prev,
                      [id]: Math.max(1, (prev[id] ?? 1) - 1),
                    }))
                  }}
                  disabled={detail.page <= 1}
                  className="px-3 py-1.5 rounded-lg text-sm border border-gray-700 text-gray-300 bg-gray-900 hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {'<'}
                </button>
                <span className="text-xs text-gray-500">
                  Page {detail.page} of {detail.total_pages}
                </span>
                <button
                  type="button"
                  onClick={() => {
                    if (!id) return
                    setDetailPagesById((prev) => ({
                      ...prev,
                      [id]: Math.min(detail.total_pages, (prev[id] ?? 1) + 1),
                    }))
                  }}
                  disabled={detail.page >= detail.total_pages}
                  className="px-3 py-1.5 rounded-lg text-sm border border-gray-700 text-gray-300 bg-gray-900 hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {'>'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Collections</h2>
          <p className="text-sm text-gray-400 mt-1">Organize your generated images into curated groups</p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreateModal(true)}
          className="bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-4 py-2 text-sm font-medium"
        >
          New Collection
        </button>
      </div>

      {collectionsQuery.isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, idx) => (
            <div key={idx} className="h-64 bg-gray-900 border border-gray-800 rounded-xl animate-pulse" />
          ))}
        </div>
      ) : collectionsQuery.isError ? (
        <div className="bg-gray-900 border border-red-800/50 rounded-xl p-8 text-center">
          <p className="text-red-400">Failed to load collections</p>
        </div>
      ) : !collectionsQuery.data || collectionsQuery.data.length === 0 ? (
        <EmptyState
          title="컬렉션이 없습니다"
          description="새 컬렉션을 만들고 이미지를 정리해보세요."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {collectionsQuery.data.map((collection) => (
            <button
              type="button"
              key={collection.id}
              onClick={() => navigate(`/collections/${collection.id}`)}
              className="text-left bg-gray-900 border border-gray-800 rounded-xl overflow-hidden hover:border-violet-500/40 transition-colors"
            >
              <div className="aspect-[16/10] bg-gray-950">
                {collection.cover_thumbnail_path ? (
                  <img
                    src={`/data/${collection.cover_thumbnail_path}`}
                    alt={collection.name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-700">
                    <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h3.086a2.25 2.25 0 001.591-.659l.828-.828a2.25 2.25 0 011.591-.659H19.5A2.25 2.25 0 0121.75 9.75v8.25A2.25 2.25 0 0119.5 20.25h-15A2.25 2.25 0 012.25 18V12.75z" />
                    </svg>
                  </div>
                )}
              </div>
              <div className="p-4 space-y-1.5">
                <p className="text-sm font-semibold text-gray-100">{collection.name}</p>
                <p className="text-xs text-gray-400">{collection.image_count} image{collection.image_count === 1 ? '' : 's'}</p>
                {collection.description && (
                  <p className="text-xs text-gray-500 line-clamp-2">{collection.description}</p>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm px-4 flex items-center justify-center">
          <div className="w-full max-w-lg bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-100">New Collection</h3>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-gray-500 hover:text-gray-300"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Name</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Description</label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  rows={3}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none resize-y"
                />
              </div>

              {createMutation.isError && (
                <div className="bg-red-900/20 border border-red-800/50 rounded-lg p-3">
                  <p className="text-sm text-red-400">Failed to create collection</p>
                </div>
              )}

              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || !newName.trim()}
                  className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
