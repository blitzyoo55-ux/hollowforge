import { useState } from 'react'
import type {
  ProductionFormatFamily,
  ProductionWorkCreate,
  SequenceContentMode,
} from '../../api/client'

interface ProductionWorkFormProps {
  onSubmit: (payload: ProductionWorkCreate) => void
  isSubmitting?: boolean
}

export default function ProductionWorkForm({
  onSubmit,
  isSubmitting = false,
}: ProductionWorkFormProps) {
  const [title, setTitle] = useState('')
  const [formatFamily, setFormatFamily] = useState<ProductionFormatFamily>('mixed')
  const [defaultContentMode, setDefaultContentMode] = useState<SequenceContentMode>('adult_nsfw')
  const [status, setStatus] = useState('draft')
  const [canonNotes, setCanonNotes] = useState('')

  const canSubmit = Boolean(title.trim())

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (!canSubmit) return

        onSubmit({
          title: title.trim(),
          format_family: formatFamily,
          default_content_mode: defaultContentMode,
          status: status.trim() || 'draft',
          canon_notes: canonNotes.trim() || null,
        })
      }}
      className="space-y-4 rounded-2xl border border-gray-800 bg-gray-900/70 p-5"
    >
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Create Production Work</h2>
        <p className="mt-1 text-sm text-gray-400">
          Register a top-level production work for downstream series and episode entries.
        </p>
      </div>

      <label className="space-y-2 text-sm text-gray-300">
        <span>Work Title</span>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Camila Pilot Arc"
          className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
        />
      </label>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-gray-300">
          <span>Format Family</span>
          <select
            value={formatFamily}
            onChange={(event) => setFormatFamily(event.target.value as ProductionFormatFamily)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            <option value="mixed">mixed</option>
            <option value="comic">comic</option>
            <option value="animation">animation</option>
          </select>
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Default Content Mode</span>
          <select
            value={defaultContentMode}
            onChange={(event) => setDefaultContentMode(event.target.value as SequenceContentMode)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            <option value="adult_nsfw">adult_nsfw</option>
            <option value="all_ages">all_ages</option>
          </select>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-gray-300">
          <span>Status</span>
          <input
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            placeholder="draft"
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
          />
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Canon Notes</span>
          <input
            value={canonNotes}
            onChange={(event) => setCanonNotes(event.target.value)}
            placeholder="Optional continuity anchor"
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={!canSubmit || isSubmitting}
        className="rounded-xl border border-violet-500/40 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? 'Creating...' : 'Create Work'}
      </button>
    </form>
  )
}
