import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getDirectionReferences,
  createDirectionReference,
  deleteDirectionReference,
  type DirectionReference,
} from '../api/client'
import EmptyState from '../components/EmptyState'
import { notify } from '../lib/toast'

function parseTags(tags: string | null): string[] {
  if (!tags) return []
  try {
    const parsed = JSON.parse(tags)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function ReferenceCard({
  item,
  onDelete,
}: {
  item: DirectionReference
  onDelete: (id: string) => void
}) {
  const [imgError, setImgError] = useState(false)
  const tags = parseTags(item.tags)

  const imageUrl = item.source === 'external'
    ? item.external_url ?? null
    : item.generation_id
      ? `/data/thumbs/${item.generation_id}.jpg`
      : null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden hover:border-violet-500/40 transition-colors group">
      {/* Image */}
      <div className="aspect-[4/3] bg-gray-950 overflow-hidden">
        {imageUrl && !imgError ? (
          <img
            src={imageUrl}
            alt={item.title}
            className="w-full h-full object-cover"
            loading="lazy"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-700">
            <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
            </svg>
          </div>
        )}
      </div>

      {/* Card body */}
      <div className="p-3 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-semibold text-gray-100 line-clamp-2 flex-1">{item.title}</p>
          <button
            type="button"
            onClick={() => onDelete(item.id)}
            className="shrink-0 p-1 rounded-lg text-gray-600 hover:text-red-400 hover:bg-red-900/20 transition-colors opacity-0 group-hover:opacity-100"
            aria-label="Delete reference"
            title="Delete"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
            </svg>
          </button>
        </div>

        {tags.length > 0 && (
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
        )}

        {item.notes && (
          <p className="text-xs text-gray-500 line-clamp-3">{item.notes}</p>
        )}

        <div className="flex items-center gap-1.5 pt-0.5">
          <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
            item.source === 'external'
              ? 'bg-blue-900/40 border border-blue-700/40 text-blue-300'
              : 'bg-violet-900/40 border border-violet-700/40 text-violet-300'
          }`}>
            {item.source === 'external' ? 'External' : 'Internal'}
          </span>
          <span className="text-[10px] text-gray-600">
            {new Date(item.created_at).toLocaleDateString()}
          </span>
        </div>
      </div>
    </div>
  )
}

interface AddModalProps {
  onClose: () => void
  onSubmit: (data: { title: string; external_url?: string; notes?: string; tags?: string[] }) => void
  isPending: boolean
}

function AddReferenceModal({ onClose, onSubmit, isPending }: AddModalProps) {
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [tags, setTags] = useState('')
  const [notes, setNotes] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    const parsedTags = tags
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean)
    onSubmit({
      title: title.trim(),
      external_url: url.trim() || undefined,
      notes: notes.trim() || undefined,
      tags: parsedTags.length > 0 ? parsedTags : undefined,
    })
  }

  return (
    <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm px-4 flex items-center justify-center">
      <div className="w-full max-w-lg bg-gray-900 border border-gray-800 rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-100">Add Reference</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Title *</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Reference title"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Image URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/image.jpg"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Tags (comma-separated)</label>
            <input
              type="text"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="latex, pose, lighting"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              placeholder="What makes this reference useful..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none resize-y"
            />
          </div>

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !title.trim()}
              className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium"
            >
              {isPending ? 'Adding...' : 'Add Reference'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function DirectionBoard() {
  const queryClient = useQueryClient()
  const [showAddModal, setShowAddModal] = useState(false)

  const { data: references = [], isLoading, isError } = useQuery({
    queryKey: ['direction-references'],
    queryFn: getDirectionReferences,
  })

  const createMutation = useMutation({
    mutationFn: createDirectionReference,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['direction-references'] })
      setShowAddModal(false)
      notify.success('Reference added')
    },
    onError: () => notify.error('Failed to add reference'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteDirectionReference,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['direction-references'] })
      notify.success('Reference removed')
    },
    onError: () => notify.error('Failed to delete reference'),
  })

  const handleDelete = (id: string) => {
    if (window.confirm('Remove this reference?')) {
      deleteMutation.mutate(id)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Direction Board</h2>
          <p className="text-sm text-gray-400 mt-1">Pinterest-style reference board for content direction</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 rounded-lg bg-violet-600 hover:bg-violet-500 px-4 py-2 text-sm font-medium text-white"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            Add Reference
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="columns-2 sm:columns-3 xl:columns-4 gap-4 space-y-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="break-inside-avoid bg-gray-900 border border-gray-800 rounded-xl animate-pulse"
              style={{ height: `${180 + (i % 3) * 60}px` }}
            />
          ))}
        </div>
      ) : isError ? (
        <div className="bg-gray-900 rounded-xl border border-red-800/50 p-8 text-center">
          <p className="text-red-400">Failed to load references. Is the backend running?</p>
        </div>
      ) : references.length === 0 ? (
        <EmptyState
          title="No references yet"
          description="Add external image URLs or pin generations from the Gallery to build your direction board."
          action={{ label: 'Add Reference', onClick: () => setShowAddModal(true) }}
        />
      ) : (
        <div className="columns-2 sm:columns-3 xl:columns-4 gap-4">
          {references.map((item) => (
            <div key={item.id} className="break-inside-avoid mb-4">
              <ReferenceCard item={item} onDelete={handleDelete} />
            </div>
          ))}
        </div>
      )}

      {showAddModal && (
        <AddReferenceModal
          onClose={() => setShowAddModal(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          isPending={createMutation.isPending}
        />
      )}
    </div>
  )
}
