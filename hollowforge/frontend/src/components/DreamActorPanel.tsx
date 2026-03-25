import { useEffect, useRef, useState, type DragEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { GenerationResponse } from '../api/client'
import { getDreamActorStatus, submitDreamActor } from '../api/client'
import { notify } from '../lib/toast'
import VideoPlayer from './VideoPlayer'

interface DreamActorPanelProps {
  generation: GenerationResponse
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'succeeded':
      return 'bg-green-900/40 text-green-300 border-green-700/50'
    case 'failed':
      return 'bg-red-900/40 text-red-300 border-red-700/50'
    case 'processing':
      return 'bg-blue-900/40 text-blue-300 border-blue-700/50'
    default:
      return 'bg-gray-700/70 text-gray-200 border-gray-600'
  }
}

export default function DreamActorPanel({ generation }: DreamActorPanelProps) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const terminalStatusRef = useRef<string | null>(null)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [localTaskId, setLocalTaskId] = useState<string | null>(null)

  const submitMutation = useMutation({
    mutationFn: (templateVideo: File) => submitDreamActor(generation.id, templateVideo),
    onSuccess: async (data) => {
      notify.success('DreamActor task submitted')
      setIsModalOpen(false)
      setSelectedFile(null)
      setLocalTaskId(data.task_id)
      terminalStatusRef.current = null
      await queryClient.invalidateQueries({ queryKey: ['generation', generation.id] })
    },
    onError: () => {
      notify.error('Failed to submit DreamActor task')
    },
  })

  const isPendingDreamActor =
    generation.dreamactor_status === 'processing' || Boolean(generation.dreamactor_task_id || localTaskId)

  const statusQuery = useQuery({
    queryKey: ['dreamactor-status', generation.id],
    queryFn: () => getDreamActorStatus(generation.id),
    enabled: isPendingDreamActor,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return isPendingDreamActor ? 5000 : false
      return data.status === 'processing' ? 5000 : false
    },
  })

  useEffect(() => {
    const currentStatus = statusQuery.data?.status
    if (!currentStatus) return

    if (currentStatus === 'succeeded') {
      if (terminalStatusRef.current !== 'succeeded') {
        notify.success('DreamActor video is ready')
        terminalStatusRef.current = 'succeeded'
      }
      void queryClient.invalidateQueries({ queryKey: ['generation', generation.id] })
      return
    }

    if (currentStatus === 'failed') {
      if (terminalStatusRef.current !== 'failed') {
        notify.error('DreamActor task failed')
        terminalStatusRef.current = 'failed'
      }
    }
  }, [generation.id, queryClient, statusQuery.data?.status])

  const effectiveStatus =
    statusQuery.data?.status ||
    (generation.dreamactor_path ? 'succeeded' : generation.dreamactor_status) ||
    'idle'

  const effectiveProgress =
    statusQuery.data?.progress != null
      ? statusQuery.data.progress
      : effectiveStatus === 'succeeded'
        ? 100
        : 0

  const resultPath = statusQuery.data?.dreamactor_path ?? generation.dreamactor_path
  const resultVideoUrl = statusQuery.data?.video_url ?? (resultPath ? `/data/${resultPath}` : null)
  const showStatus = Boolean(generation.dreamactor_path || generation.dreamactor_task_id || statusQuery.data)

  const openFileDialog = () => {
    fileInputRef.current?.click()
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    const file = event.dataTransfer.files?.[0]
    if (!file) return
    setSelectedFile(file)
  }

  const handleSubmit = () => {
    if (!selectedFile) {
      notify.error('Please select a template video first')
      return
    }
    submitMutation.mutate(selectedFile)
  }

  return (
    <>
      <section className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-gray-100">Animate Character</h3>
            <p className="text-xs text-gray-500 mt-1">
              DreamActor M2.0 • 720P / 25FPS output
            </p>
          </div>
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            disabled={submitMutation.isPending || !generation.image_path}
            className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            Animate
          </button>
        </div>

        {showStatus && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-gray-400">Status</span>
            <span className={`rounded border px-2 py-1 ${statusBadgeClass(effectiveStatus)}`}>
              {effectiveStatus}
            </span>
          </div>
        )}

        {effectiveStatus === 'processing' && (
          <div className="space-y-1">
            <div className="h-2 rounded bg-gray-800">
              <div
                className="h-full rounded bg-blue-500 transition-all duration-300"
                style={{ width: `${Math.max(0, Math.min(100, effectiveProgress))}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 text-right">{effectiveProgress}%</p>
          </div>
        )}

        {effectiveStatus === 'failed' && (
          <p className="text-sm text-red-300">Animation failed. Upload a new template and try again.</p>
        )}

        {resultVideoUrl && (
          <VideoPlayer src={resultVideoUrl} className="pt-2" />
        )}
      </section>

      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm px-4 flex items-center justify-center">
          <div className="w-full max-w-xl rounded-xl border border-gray-800 bg-gray-900 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-lg font-semibold text-gray-100">Animate Character</h4>
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="text-gray-500 hover:text-gray-300"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div
              role="button"
              tabIndex={0}
              onClick={openFileDialog}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  openFileDialog()
                }
              }}
              onDragOver={(event) => {
                event.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className={`rounded-lg border-2 border-dashed px-4 py-8 text-center cursor-pointer transition-colors ${
                isDragging
                  ? 'border-violet-400 bg-violet-500/10'
                  : 'border-gray-700 bg-gray-950/50 hover:border-violet-500/70'
              }`}
            >
              <p className="text-sm text-gray-300">Drop template video here or click to select</p>
              <p className="mt-1 text-xs text-gray-500">Accepted: .mp4, .mov, .webm (≤30s recommended)</p>
              {selectedFile && (
                <p className="mt-3 text-xs text-violet-300">{selectedFile.name}</p>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".mp4,.mov,.webm"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null
                  setSelectedFile(file)
                }}
              />
            </div>

            <div className="rounded-lg border border-violet-700/30 bg-violet-900/20 px-4 py-3 text-xs text-violet-200">
              Processing time: ~3 min per 10s of output. Cost: $0.05/sec
            </div>

            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="rounded-lg bg-gray-800 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitMutation.isPending || !selectedFile}
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
              >
                {submitMutation.isPending ? 'Submitting...' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
