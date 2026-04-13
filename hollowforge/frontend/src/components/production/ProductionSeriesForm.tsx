import { useMemo, useState } from 'react'
import type {
  ProductionDeliveryMode,
  ProductionSeriesCreate,
  ProductionWorkResponse,
  SequenceContentMode,
} from '../../api/client'

interface ProductionSeriesFormProps {
  works: ProductionWorkResponse[]
  onSubmit: (payload: ProductionSeriesCreate) => void
  isSubmitting?: boolean
}

export default function ProductionSeriesForm({
  works,
  onSubmit,
  isSubmitting = false,
}: ProductionSeriesFormProps) {
  const [workId, setWorkId] = useState('')
  const [title, setTitle] = useState('')
  const [deliveryMode, setDeliveryMode] = useState<ProductionDeliveryMode>('serial')
  const [audienceMode, setAudienceMode] = useState<SequenceContentMode>('adult_nsfw')
  const [visualIdentityNotes, setVisualIdentityNotes] = useState('')

  const selectedWorkId = useMemo(
    () => (workId ? workId : works[0]?.id ?? ''),
    [workId, works],
  )
  const canSubmit = Boolean(selectedWorkId && title.trim())

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (!canSubmit) return

        onSubmit({
          work_id: selectedWorkId,
          title: title.trim(),
          delivery_mode: deliveryMode,
          audience_mode: audienceMode,
          visual_identity_notes: visualIdentityNotes.trim() || null,
        })
      }}
      className="space-y-4 rounded-2xl border border-gray-800 bg-gray-900/70 p-5"
    >
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Create Production Series</h2>
        <p className="mt-1 text-sm text-gray-400">
          Attach a reusable series identity to an existing production work.
        </p>
      </div>

      <label className="space-y-2 text-sm text-gray-300">
        <span>Series Work</span>
        <select
          value={selectedWorkId}
          onChange={(event) => setWorkId(event.target.value)}
          className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
        >
          {works.length === 0 && <option value="">No production works available</option>}
          {works.map((work) => (
            <option key={work.id} value={work.id}>
              {work.title}
            </option>
          ))}
        </select>
      </label>

      <label className="space-y-2 text-sm text-gray-300">
        <span>Series Title</span>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Camila Corridor Nights"
          className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
        />
      </label>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-gray-300">
          <span>Delivery Mode</span>
          <select
            value={deliveryMode}
            onChange={(event) => setDeliveryMode(event.target.value as ProductionDeliveryMode)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            <option value="serial">serial</option>
            <option value="oneshot">oneshot</option>
            <option value="anthology">anthology</option>
          </select>
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Audience Mode</span>
          <select
            value={audienceMode}
            onChange={(event) => setAudienceMode(event.target.value as SequenceContentMode)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            <option value="adult_nsfw">adult_nsfw</option>
            <option value="all_ages">all_ages</option>
          </select>
        </label>
      </div>

      <label className="space-y-2 text-sm text-gray-300">
        <span>Visual Identity Notes</span>
        <input
          value={visualIdentityNotes}
          onChange={(event) => setVisualIdentityNotes(event.target.value)}
          placeholder="Optional style constraints"
          className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
        />
      </label>

      <button
        type="submit"
        disabled={!canSubmit || isSubmitting || works.length === 0}
        className="rounded-xl border border-violet-500/40 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? 'Creating...' : 'Create Series'}
      </button>
    </form>
  )
}
