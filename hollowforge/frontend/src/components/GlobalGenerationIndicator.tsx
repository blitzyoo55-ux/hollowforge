import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { cancelGeneration, getActiveGenerations } from '../api/client'

function formatDuration(totalSec: number): string {
  const sec = Math.max(0, Math.floor(totalSec))
  const minutes = Math.floor(sec / 60)
  const seconds = sec % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

export default function GlobalGenerationIndicator() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [nowMs, setNowMs] = useState(Date.now())
  const [expanded, setExpanded] = useState(false)

  const { data: activeGenerations } = useQuery({
    queryKey: ['active-generations'],
    queryFn: getActiveGenerations,
    refetchInterval: 3000,
  })

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  const freshGenerations = useMemo(() => {
    return activeGenerations?.filter((g) => {
      const age = (Date.now() - new Date(g.created_at).getTime()) / 1000
      return age < 1800 // 30 minutes
    }) ?? []
  }, [activeGenerations])

  const earliestCreatedAt = useMemo(() => {
    if (freshGenerations.length === 0) {
      return null
    }

    let earliest: number | null = null
    for (const gen of freshGenerations) {
      const timestamp = Date.parse(gen.created_at)
      if (Number.isNaN(timestamp)) {
        continue
      }
      if (earliest === null || timestamp < earliest) {
        earliest = timestamp
      }
    }

    return earliest
  }, [freshGenerations])

  const sortedGenerations = useMemo(() => {
    return [...freshGenerations].sort(
      (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)
    )
  }, [freshGenerations])

  const cancelTarget = useMemo(() => {
    if (sortedGenerations.length === 0) return null
    const running = sortedGenerations.find((g) => g.status === 'running')
    if (running) return running
    return sortedGenerations[0] ?? null
  }, [sortedGenerations])

  const cancelMutation = useMutation({
    mutationFn: cancelGeneration,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['active-generations'] })
      queryClient.invalidateQueries({ queryKey: ['system-health'] })
      queryClient.invalidateQueries({ queryKey: ['generation-status'] })
      queryClient.invalidateQueries({ queryKey: ['generation-progress'] })
    },
  })

  if (freshGenerations.length === 0) {
    return null
  }

  const elapsedSec = earliestCreatedAt != null ? Math.max(0, Math.floor((nowMs - earliestCreatedAt) / 1000)) : 0

  return (
    <div className="w-full bg-violet-600/20 border border-violet-500/30 rounded-lg px-3 py-2">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left hover:bg-violet-600/20 rounded-md p-1 -m-1 transition-colors duration-200"
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-violet-300 font-medium">Generating...</span>
          </div>
          <svg
            className={`w-4 h-4 text-violet-300 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </div>
        <div className="mt-1 flex items-center justify-between">
          <span className="text-xs text-violet-200/90 font-mono">{formatDuration(elapsedSec)}</span>
          <span className="text-[11px] text-violet-200/80 font-mono">
            {freshGenerations.length} active
          </span>
        </div>
      </button>
      <div className="mt-2 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => navigate('/generate')}
          className="text-xs px-2 py-1 rounded border border-violet-400/40 text-violet-200 hover:bg-violet-600/20 transition-colors duration-200"
        >
          Open Generate
        </button>
        <button
          type="button"
          disabled={!cancelTarget || cancelMutation.isPending}
          onClick={() => {
            if (!cancelTarget) return
            cancelMutation.mutate(cancelTarget.id)
          }}
          className="text-xs px-2 py-1 rounded border border-red-500/40 text-red-300 hover:bg-red-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-200"
        >
          {cancelMutation.isPending ? 'Cancelling...' : 'Cancel'}
        </button>
      </div>
      {expanded && (
        <div className="mt-2 border-t border-violet-400/20 pt-2 space-y-2 max-h-56 overflow-y-auto">
          {sortedGenerations.map((gen, index) => {
            const createdMs = Date.parse(gen.created_at)
            const rowElapsed = Number.isNaN(createdMs)
              ? 0
              : Math.max(0, Math.floor((nowMs - createdMs) / 1000))
            const isRunning = gen.status === 'running'
            const checkpoint = (gen.checkpoint ?? 'unknown').replace(/\.safetensors$/i, '')
            const sizeLabel = gen.width && gen.height ? `${gen.width}x${gen.height}` : '-'
            return (
              <div
                key={gen.id}
                className="rounded-md border border-violet-400/20 bg-gray-900/40 p-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-violet-200 font-medium">
                    #{index + 1} {isRunning ? 'Running' : 'Queued'}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
                      isRunning ? 'bg-emerald-600/20 text-emerald-300' : 'bg-amber-600/20 text-amber-300'
                    }`}
                  >
                    {gen.status}
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-violet-100 truncate" title={gen.checkpoint ?? ''}>
                  {checkpoint}
                </p>
                <div className="mt-1 grid grid-cols-2 gap-x-2 gap-y-1 text-[10px] text-violet-200/80 font-mono">
                  <span>seed: {gen.seed ?? '-'}</span>
                  <span>steps: {gen.steps ?? '-'}</span>
                  <span>size: {sizeLabel}</span>
                  <span>elapsed: {formatDuration(rowElapsed)}</span>
                </div>
                <div className="mt-1 text-[10px] text-violet-200/70 font-mono truncate">
                  id: {gen.id}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
