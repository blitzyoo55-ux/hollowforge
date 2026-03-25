import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { cancelAllQueued, cancelGeneration, getQueueSummary } from '../api/client'
import type { QueueItem } from '../api/client'
import EmptyState from '../components/EmptyState'

function formatEstimate(sec: number): string {
  if (sec <= 0) return '~0s'
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  if (m === 0) return `~${s}s`
  return `~${m}m ${s}s`
}

function stripSafetensors(name: string): string {
  return name.replace(/\.safetensors$/i, '')
}

export default function QueuePage() {
  const queryClient = useQueryClient()
  const [cancellingId, setCancellingId] = useState<string | null>(null)
  const [cancellingAll, setCancellingAll] = useState(false)

  const { data: summary, isLoading, isError } = useQuery({
    queryKey: ['queue-summary'],
    queryFn: getQueueSummary,
    refetchInterval: 5000,
  })

  const cancelMutation = useMutation({
    mutationFn: cancelGeneration,
    onSettled: () => setCancellingId(null),
    onSuccess: () => {
      toast.success('Generation cancelled')
      queryClient.invalidateQueries({ queryKey: ['queue-summary'] })
      queryClient.invalidateQueries({ queryKey: ['active-generations'] })
    },
    onError: () => toast.error('Failed to cancel generation'),
  })

  const cancelAllMutation = useMutation({
    mutationFn: cancelAllQueued,
    onSettled: () => setCancellingAll(false),
    onSuccess: (data) => {
      toast.success(`Cancelled ${data.cancelled} queued items`)
      queryClient.invalidateQueries({ queryKey: ['queue-summary'] })
      queryClient.invalidateQueries({ queryKey: ['active-generations'] })
    },
    onError: () => toast.error('Failed to cancel all queued'),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-6 h-6 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (isError || !summary) {
    return (
      <div className="text-center py-20 text-red-400">
        Failed to load queue data.
      </div>
    )
  }

  const hasItems = summary.queue_items.length > 0

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-2xl font-bold text-gray-100">Queue</h1>
        {hasItems && summary.total_queued > 0 && (
          <button
            type="button"
            disabled={cancellingAll}
            onClick={() => {
              setCancellingAll(true)
              cancelAllMutation.mutate()
            }}
            className="w-full rounded-lg border border-red-500/40 bg-red-600/10 px-4 py-2 text-sm font-medium text-red-300 hover:bg-red-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 sm:w-auto"
          >
            {cancellingAll ? 'Cancelling...' : 'Cancel All Queued'}
          </button>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Queued</p>
          <p className="mt-1 text-2xl font-bold text-amber-400">{summary.total_queued}</p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Running</p>
          <p className="mt-1 text-2xl font-bold text-emerald-400">{summary.total_running}</p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/70 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Est. Remaining</p>
          <p className="mt-1 text-2xl font-bold text-violet-400">
            {formatEstimate(summary.estimated_remaining_sec)}
          </p>
        </div>
      </div>

      {/* Queue items */}
      {!hasItems ? (
        <EmptyState
          title="Queue is empty"
          description="No generations are currently queued or running."
        />
      ) : (
        <div className="space-y-3">
          {summary.queue_items.map((item: QueueItem) => {
            const isRunning = item.status === 'running'
            return (
              <div
                key={item.id}
                className="rounded-xl border border-gray-800 bg-gray-900/70 p-4 space-y-3"
              >
                {/* Header row */}
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-sm font-mono text-gray-500">#{item.position}</span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        isRunning
                          ? 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/30'
                          : 'bg-amber-600/20 text-amber-300 border border-amber-500/30'
                      }`}
                    >
                      {item.status}
                    </span>
                    <span className="text-sm font-medium text-gray-200 truncate">
                      {stripSafetensors(item.checkpoint)}
                    </span>
                  </div>
                  <button
                    type="button"
                    disabled={cancellingId !== null}
                    onClick={() => {
                      setCancellingId(item.id)
                      cancelMutation.mutate(item.id)
                    }}
                    className="w-full shrink-0 text-xs px-3 py-1.5 rounded-lg border border-red-500/40 text-red-300 hover:bg-red-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200 sm:w-auto"
                  >
                    {cancellingId === item.id ? 'Cancelling...' : 'Cancel'}
                  </button>
                </div>

                {/* Prompt */}
                <p className="text-sm text-gray-400 line-clamp-2" title={item.prompt}>
                  {item.prompt.length > 100 ? item.prompt.slice(0, 100) + '...' : item.prompt}
                </p>

                {/* LoRAs */}
                {item.loras.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {item.loras.map((lora, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-0.5 rounded-md bg-violet-600/15 text-violet-300 border border-violet-500/20"
                      >
                        {stripSafetensors(lora.filename)}
                        <span className="ml-1 text-violet-400/60">{lora.strength}</span>
                      </span>
                    ))}
                  </div>
                )}

                {/* Params grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-1 text-xs text-gray-500 font-mono">
                  <span>
                    {item.width}x{item.height}
                  </span>
                  <span>steps: {item.steps}</span>
                  <span>cfg: {item.cfg}</span>
                  <span>sampler: {item.sampler}</span>
                </div>

                {/* Tags & notes */}
                {item.tags && item.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {item.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-[11px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400 border border-gray-700"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
                {item.notes && (
                  <p className="text-xs text-gray-500 italic truncate">{item.notes}</p>
                )}

                {/* Time estimates */}
                <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs text-gray-500">
                  <span>
                    Start: <span className="text-violet-300 font-mono">{formatEstimate(item.estimated_start_sec)}</span>
                  </span>
                  <span>
                    Done: <span className="text-violet-300 font-mono">{formatEstimate(item.estimated_done_sec)}</span>
                  </span>
                  <span className="text-gray-600 font-mono text-[11px] sm:ml-auto">{item.id.slice(0, 8)}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
