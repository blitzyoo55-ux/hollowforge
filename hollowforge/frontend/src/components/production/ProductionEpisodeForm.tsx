import { useMemo, useState } from 'react'
import type {
  ProductionEpisodeCreate,
  ProductionSeriesResponse,
  ProductionTargetOutput,
  ProductionWorkResponse,
  SequenceContentMode,
} from '../../api/client'

interface ProductionEpisodeFormProps {
  works: ProductionWorkResponse[]
  series: ProductionSeriesResponse[]
  onSubmit: (payload: ProductionEpisodeCreate) => void
  isSubmitting?: boolean
}

const DEFAULT_TARGET_OUTPUTS: ProductionTargetOutput[] = ['comic', 'animation']

export default function ProductionEpisodeForm({
  works,
  series,
  onSubmit,
  isSubmitting = false,
}: ProductionEpisodeFormProps) {
  const [workId, setWorkId] = useState('')
  const [seriesId, setSeriesId] = useState('__none__')
  const [title, setTitle] = useState('')
  const [synopsis, setSynopsis] = useState('')
  const [contentMode, setContentMode] = useState<SequenceContentMode>('adult_nsfw')
  const [status, setStatus] = useState('draft')
  const [continuitySummary, setContinuitySummary] = useState('')
  const [targetOutputs, setTargetOutputs] = useState<ProductionTargetOutput[]>(DEFAULT_TARGET_OUTPUTS)

  const selectedWorkId = useMemo(
    () => (workId ? workId : works[0]?.id ?? ''),
    [workId, works],
  )
  const filteredSeries = useMemo(
    () => series.filter((item) => item.work_id === selectedWorkId),
    [series, selectedWorkId],
  )

  const canSubmit = Boolean(
    selectedWorkId
    && title.trim()
    && synopsis.trim()
    && targetOutputs.length > 0,
  )

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (!canSubmit) return

        onSubmit({
          work_id: selectedWorkId,
          series_id: seriesId === '__none__' ? null : seriesId,
          title: title.trim(),
          synopsis: synopsis.trim(),
          content_mode: contentMode,
          target_outputs: targetOutputs,
          continuity_summary: continuitySummary.trim() || null,
          status: status.trim() || 'draft',
        })
      }}
      className="space-y-4 rounded-2xl border border-gray-800 bg-gray-900/70 p-5"
    >
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Create Production Episode</h2>
        <p className="mt-1 text-sm text-gray-400">
          Create a shared production episode entry that both comic and animation tracks can open.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-gray-300">
          <span>Episode Work</span>
          <select
            value={selectedWorkId}
            onChange={(event) => {
              setWorkId(event.target.value)
              setSeriesId('__none__')
            }}
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
          <span>Episode Series</span>
          <select
            value={seriesId}
            onChange={(event) => setSeriesId(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            <option value="__none__">Standalone</option>
            {filteredSeries.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="space-y-2 text-sm text-gray-300">
        <span>Episode Title</span>
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Corridor Lock-In"
          className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
        />
      </label>

      <label className="space-y-2 text-sm text-gray-300">
        <span>Episode Synopsis</span>
        <textarea
          value={synopsis}
          onChange={(event) => setSynopsis(event.target.value)}
          rows={3}
          placeholder="Production core synopsis for both tracks."
          className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
        />
      </label>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-gray-300">
          <span>Content Mode</span>
          <select
            value={contentMode}
            onChange={(event) => setContentMode(event.target.value as SequenceContentMode)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            <option value="adult_nsfw">adult_nsfw</option>
            <option value="all_ages">all_ages</option>
          </select>
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Status</span>
          <input
            value={status}
            onChange={(event) => setStatus(event.target.value)}
            placeholder="draft"
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
          />
        </label>
      </div>

      <fieldset className="space-y-2 text-sm text-gray-300">
        <legend className="text-sm text-gray-300">Target Outputs</legend>
        <div className="flex flex-wrap gap-4">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={targetOutputs.includes('comic')}
              onChange={(event) => {
                if (event.target.checked) {
                  setTargetOutputs((prev) => (prev.includes('comic') ? prev : [...prev, 'comic']))
                  return
                }
                setTargetOutputs((prev) => prev.filter((item) => item !== 'comic'))
              }}
            />
            <span>comic</span>
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={targetOutputs.includes('animation')}
              onChange={(event) => {
                if (event.target.checked) {
                  setTargetOutputs((prev) => (prev.includes('animation') ? prev : [...prev, 'animation']))
                  return
                }
                setTargetOutputs((prev) => prev.filter((item) => item !== 'animation'))
              }}
            />
            <span>animation</span>
          </label>
        </div>
      </fieldset>

      <label className="space-y-2 text-sm text-gray-300">
        <span>Continuity Summary</span>
        <input
          value={continuitySummary}
          onChange={(event) => setContinuitySummary(event.target.value)}
          placeholder="Optional continuity summary"
          className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
        />
      </label>

      <button
        type="submit"
        disabled={!canSubmit || isSubmitting || works.length === 0}
        className="rounded-xl border border-violet-500/40 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? 'Creating...' : 'Create Episode'}
      </button>
    </form>
  )
}
