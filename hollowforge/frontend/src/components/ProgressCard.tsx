import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getGenerationStatus, getGeneration, cancelGeneration } from '../api/client'
import type { GenerationResponse } from '../api/client'

interface ProgressCardProps {
  generationId: string
  onComplete: (gen: GenerationResponse) => void
  onError: (error: string, gen?: GenerationResponse) => void
}

function formatDuration(totalSec: number): string {
  const sec = Math.max(0, Math.floor(totalSec))
  const minutes = Math.floor(sec / 60)
  const seconds = sec % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

export default function ProgressCard({ generationId, onComplete, onError }: ProgressCardProps) {
  const [elapsed, setElapsed] = useState(0)
  const [cancelling, setCancelling] = useState(false)

  const { data: generation } = useQuery({
    queryKey: ['generation-progress', generationId],
    queryFn: () => getGeneration(generationId),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })

  const { data: status } = useQuery({
    queryKey: ['generation-status', generationId],
    queryFn: () => getGenerationStatus(generationId),
    refetchInterval: (query) => {
      const s = query.state.data?.status
      if (s === 'completed' || s === 'failed' || s === 'cancelled') return false
      return 2000
    },
  })

  useEffect(() => {
    if (generation?.created_at) {
      const createdAtMs = Date.parse(generation.created_at)
      if (!Number.isNaN(createdAtMs)) {
        const updateElapsed = () => {
          const sec = Math.floor((Date.now() - createdAtMs) / 1000)
          setElapsed(Math.max(0, sec))
        }
        updateElapsed()
        const timer = setInterval(updateElapsed, 1000)
        return () => clearInterval(timer)
      }
    }

    const timer = setInterval(() => setElapsed((prev) => prev + 1), 1000)
    return () => clearInterval(timer)
  }, [generation?.created_at])

  const handleComplete = useCallback(() => {
    if (status?.status === 'completed') {
      getGeneration(generationId).then(onComplete)
    }
  }, [status?.status, generationId, onComplete])

  useEffect(() => {
    handleComplete()
  }, [handleComplete])

  useEffect(() => {
    if (status?.status === 'failed') {
      getGeneration(generationId).then((gen) => {
        onError(gen.error_message || 'Generation failed', gen)
      }).catch(() => {
        onError('Generation failed')
      })
    }
  }, [status?.status, generationId, onError])

  useEffect(() => {
    if (status?.status === 'cancelled') {
      getGeneration(generationId).then((gen) => {
        onError('Generation cancelled', gen)
      }).catch(() => {
        onError('Generation cancelled')
      })
    }
  }, [status?.status, generationId, onError])

  const handleCancel = async () => {
    setCancelling(true)
    try {
      await cancelGeneration(generationId)
    } catch {
      onError('Failed to cancel generation')
      setCancelling(false)
    }
  }

  const etaSec = status?.estimated_time_sec != null ? Math.round(status.estimated_time_sec) : null
  const elapsedText = formatDuration(elapsed)
  const etaText = etaSec != null ? formatDuration(etaSec) : null
  const progressPercent = etaSec && etaSec > 0 ? Math.min(100, Math.round((elapsed / etaSec) * 100)) : null
  const isActive = status?.status !== 'completed' && status?.status !== 'failed' && status?.status !== 'cancelled'
  const generatingLabel = etaText != null
    ? `Generating... ${elapsedText} / ~${etaText}`
    : `Generating... ${elapsedText}`

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-sm font-medium text-gray-200">
          {status?.status === 'cancelled' ? 'Cancelled' : generatingLabel}
        </span>
      </div>

      {isActive && progressPercent != null && (
        <div className="mb-4">
          <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-violet-500 transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="mt-1 text-xs text-gray-500 text-right">{progressPercent}%</div>
        </div>
      )}

      <div className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Status</span>
          <span className="text-gray-200 capitalize">{status?.status ?? 'queued'}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">{etaText != null ? 'Time' : 'Elapsed'}</span>
          <span className="text-gray-200 font-mono">
            {etaText != null ? `${elapsedText} / ~${etaText}` : elapsedText}
          </span>
        </div>
        {status?.generation_time_sec != null && (
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Gen Time</span>
            <span className="text-gray-200 font-mono">{status.generation_time_sec.toFixed(1)}s</span>
          </div>
        )}
      </div>

      {isActive && (
        <button
          onClick={handleCancel}
          disabled={cancelling}
          className="mt-4 w-full bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm transition-colors duration-200"
        >
          {cancelling ? 'Cancelling...' : 'Cancel'}
        </button>
      )}
    </div>
  )
}
