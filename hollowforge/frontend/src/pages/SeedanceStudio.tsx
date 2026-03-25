import { useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteSeedanceJob,
  getSeedanceJob,
  listSeedanceJobs,
  submitSeedanceJob,
  type SeedanceJobStatus,
} from '../api/client'
import VideoPlayer from '../components/VideoPlayer'
import { notify } from '../lib/toast'

interface ImageItem {
  file: File
  previewUrl: string
}

interface TimedItem {
  file: File
  durationSec: number
}

function formatDate(value: string | null): string {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

function statusClass(status: string): string {
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

function fileExt(name: string): string {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx).toLowerCase() : ''
}

function isImageFile(file: File): boolean {
  const ext = fileExt(file.name)
  return file.type.startsWith('image/') || ['.jpg', '.jpeg', '.png', '.webp'].includes(ext)
}

function isVideoFile(file: File): boolean {
  const ext = fileExt(file.name)
  return file.type.startsWith('video/') || ['.mp4', '.mov', '.webm'].includes(ext)
}

function isAudioFile(file: File): boolean {
  const ext = fileExt(file.name)
  return file.type.startsWith('audio/') || ext === '.mp3'
}

function loadMediaDuration(file: File, kind: 'video' | 'audio'): Promise<number> {
  return new Promise((resolve) => {
    const media = kind === 'video' ? document.createElement('video') : document.createElement('audio')
    const objectUrl = URL.createObjectURL(file)
    media.preload = 'metadata'
    media.src = objectUrl
    media.onloadedmetadata = () => {
      const duration = Number.isFinite(media.duration) ? Math.max(0, media.duration) : 0
      URL.revokeObjectURL(objectUrl)
      resolve(duration)
    }
    media.onerror = () => {
      URL.revokeObjectURL(objectUrl)
      resolve(0)
    }
  })
}

export default function SeedanceStudio() {
  const queryClient = useQueryClient()
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const imageInputRef = useRef<HTMLInputElement | null>(null)
  const videoInputRef = useRef<HTMLInputElement | null>(null)
  const audioInputRef = useRef<HTMLInputElement | null>(null)
  const imagesRef = useRef<ImageItem[]>([])
  const terminalStatusRef = useRef<string | null>(null)

  const [prompt, setPrompt] = useState('')
  const [durationSec, setDurationSec] = useState(8)
  const [images, setImages] = useState<ImageItem[]>([])
  const [videos, setVideos] = useState<TimedItem[]>([])
  const [audios, setAudios] = useState<TimedItem[]>([])
  const [isImageDragging, setIsImageDragging] = useState(false)
  const [isVideoDragging, setIsVideoDragging] = useState(false)
  const [isAudioDragging, setIsAudioDragging] = useState(false)
  const [showMentionMenu, setShowMentionMenu] = useState(false)
  const [activeJobId, setActiveJobId] = useState<string | null>(null)

  useEffect(() => {
    imagesRef.current = images
  }, [images])

  useEffect(() => {
    return () => {
      for (const item of imagesRef.current) {
        URL.revokeObjectURL(item.previewUrl)
      }
    }
  }, [])

  const totalFiles = images.length + videos.length + audios.length
  const totalVideoDuration = useMemo(
    () => videos.reduce((sum, item) => sum + item.durationSec, 0),
    [videos],
  )
  const totalAudioDuration = useMemo(
    () => audios.reduce((sum, item) => sum + item.durationSec, 0),
    [audios],
  )

  const validation = {
    images: images.length > 9,
    videos: videos.length > 3,
    audios: audios.length > 3,
    total: totalFiles > 12,
    videoDuration: totalVideoDuration > 15,
    audioDuration: totalAudioDuration > 15,
  }
  const hasValidationError = Object.values(validation).some(Boolean)

  const mentionItems = useMemo(() => {
    const labels: string[] = []
    images.forEach((_, index) => labels.push(`Image ${index + 1}`))
    videos.forEach((_, index) => labels.push(`Video ${index + 1}`))
    audios.forEach((_, index) => labels.push(`Audio ${index + 1}`))
    return labels
  }, [images, videos, audios])

  const submitMutation = useMutation({
    mutationFn: () => submitSeedanceJob({
      prompt: prompt.trim(),
      duration_sec: durationSec,
      image_files: images.map((item) => item.file),
      video_files: videos.map((item) => item.file),
      audio_files: audios.map((item) => item.file),
    }),
    onSuccess: async (result) => {
      terminalStatusRef.current = null
      setActiveJobId(result.job_id)
      notify.success('Seedance job submitted')
      await queryClient.invalidateQueries({ queryKey: ['seedance-jobs'] })
      await queryClient.invalidateQueries({ queryKey: ['seedance-job', result.job_id] })
    },
    onError: () => {
      notify.error('Failed to submit Seedance job')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => deleteSeedanceJob(jobId),
    onSuccess: async () => {
      notify.success('Seedance job removed')
      await queryClient.invalidateQueries({ queryKey: ['seedance-jobs'] })
    },
    onError: () => {
      notify.error('Failed to delete Seedance job')
    },
  })

  const jobsQuery = useQuery({
    queryKey: ['seedance-jobs'],
    queryFn: listSeedanceJobs,
    refetchInterval: (query) => {
      const rows = query.state.data as SeedanceJobStatus[] | undefined
      if (!rows || rows.length === 0) return 10_000
      return rows.some((row) => row.status === 'processing' || row.status === 'pending')
        ? 5000
        : 10_000
    },
  })

  const activeJobQuery = useQuery({
    queryKey: ['seedance-job', activeJobId],
    queryFn: () => getSeedanceJob(activeJobId as string),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const row = query.state.data as SeedanceJobStatus | undefined
      if (!row) return 5000
      return row.status === 'processing' || row.status === 'pending' ? 5000 : false
    },
  })

  useEffect(() => {
    const status = activeJobQuery.data?.status
    if (!status) return

    if (status === 'succeeded' && terminalStatusRef.current !== 'succeeded') {
      terminalStatusRef.current = 'succeeded'
      notify.success('Seedance video is ready')
      queryClient.invalidateQueries({ queryKey: ['seedance-jobs'] })
    } else if (status === 'failed' && terminalStatusRef.current !== 'failed') {
      terminalStatusRef.current = 'failed'
      notify.error(activeJobQuery.data?.error_msg || 'Seedance generation failed')
      queryClient.invalidateQueries({ queryKey: ['seedance-jobs'] })
    }
  }, [activeJobQuery.data?.error_msg, activeJobQuery.data?.status, queryClient])

  const handleAddImages = (incoming: File[]) => {
    const accepted = incoming.filter((file) => isImageFile(file))
    if (accepted.length === 0) return
    const nextItems = accepted.map((file) => ({ file, previewUrl: URL.createObjectURL(file) }))
    setImages((prev) => [...prev, ...nextItems])
  }

  const handleAddVideos = async (incoming: File[]) => {
    const accepted = incoming.filter((file) => isVideoFile(file))
    if (accepted.length === 0) return
    const nextItems = await Promise.all(
      accepted.map(async (file) => ({
        file,
        durationSec: await loadMediaDuration(file, 'video'),
      })),
    )
    setVideos((prev) => [...prev, ...nextItems])
  }

  const handleAddAudios = async (incoming: File[]) => {
    const accepted = incoming.filter((file) => isAudioFile(file))
    if (accepted.length === 0) return

    const nonMp3 = accepted.find((file) => fileExt(file.name) !== '.mp3')
    if (nonMp3) {
      notify.error('Audio input supports MP3 only')
      return
    }

    const nextItems = await Promise.all(
      accepted.map(async (file) => ({
        file,
        durationSec: await loadMediaDuration(file, 'audio'),
      })),
    )
    setAudios((prev) => [...prev, ...nextItems])
  }

  const handlePromptInput = (value: string) => {
    setPrompt(value)
    const textarea = textareaRef.current
    if (!textarea) return
    const cursor = textarea.selectionStart ?? value.length
    const before = value.slice(0, cursor)
    const atIndex = before.lastIndexOf('@')
    if (atIndex < 0) {
      setShowMentionMenu(false)
      return
    }
    const token = before.slice(atIndex + 1)
    if (token.includes(' ') || token.includes('\n')) {
      setShowMentionMenu(false)
      return
    }
    setShowMentionMenu(mentionItems.length > 0)
  }

  const insertMention = (label: string) => {
    const textarea = textareaRef.current
    if (!textarea) return

    const cursorStart = textarea.selectionStart ?? prompt.length
    const cursorEnd = textarea.selectionEnd ?? cursorStart
    const before = prompt.slice(0, cursorStart)
    const atIndex = before.lastIndexOf('@')
    const replaceStart = atIndex >= 0 ? atIndex : cursorStart
    const nextPrompt = `${prompt.slice(0, replaceStart)}@${label} ${prompt.slice(cursorEnd)}`
    setPrompt(nextPrompt)
    setShowMentionMenu(false)

    requestAnimationFrame(() => {
      const nextPos = replaceStart + label.length + 2
      textarea.focus()
      textarea.setSelectionRange(nextPos, nextPos)
    })
  }

  const removeImage = (index: number) => {
    setImages((prev) => {
      const item = prev[index]
      if (item) URL.revokeObjectURL(item.previewUrl)
      return prev.filter((_, idx) => idx !== index)
    })
  }

  const removeVideo = (index: number) => {
    setVideos((prev) => prev.filter((_, idx) => idx !== index))
  }

  const removeAudio = (index: number) => {
    setAudios((prev) => prev.filter((_, idx) => idx !== index))
  }

  const handleSubmit = () => {
    if (!prompt.trim()) {
      notify.error('Prompt is required')
      return
    }
    if (hasValidationError) {
      notify.error('Fix validation errors before generating')
      return
    }
    submitMutation.mutate()
  }

  const recentJobs = (jobsQuery.data ?? []).slice(0, 5)
  const activeOutputPath = activeJobQuery.data?.output_path

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Seedance Studio</h2>
        <p className="text-sm text-gray-400 mt-1">
          Mix image/video/audio references with prompt mentions for cinematic motion generation
        </p>
      </div>

      <section className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-5">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded border px-2 py-1 ${validation.total ? 'border-red-700 text-red-300 bg-red-900/20' : 'border-gray-700 text-gray-300 bg-gray-800/50'}`}>
            {totalFiles} / 12 files
          </span>
          <span className={`rounded border px-2 py-1 ${validation.images ? 'border-red-700 text-red-300 bg-red-900/20' : 'border-gray-700 text-gray-300 bg-gray-800/50'}`}>
            Images: {images.length}/9
          </span>
          <span className={`rounded border px-2 py-1 ${validation.videos || validation.videoDuration ? 'border-red-700 text-red-300 bg-red-900/20' : 'border-gray-700 text-gray-300 bg-gray-800/50'}`}>
            Videos: {videos.length}/3 ({totalVideoDuration.toFixed(1)}s/15s)
          </span>
          <span className={`rounded border px-2 py-1 ${validation.audios || validation.audioDuration ? 'border-red-700 text-red-300 bg-red-900/20' : 'border-gray-700 text-gray-300 bg-gray-800/50'}`}>
            Audio: {audios.length}/3 ({totalAudioDuration.toFixed(1)}s/15s)
          </span>
        </div>

        {hasValidationError && (
          <div className="rounded-lg border border-red-800/50 bg-red-900/20 px-3 py-2 text-sm text-red-300">
            One or more Seedance input limits are exceeded.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-200">Images</h3>
              <span className="text-xs text-gray-500">{images.length}/9</span>
            </div>
            <DropZone
              dragging={isImageDragging}
              label="Drop images or click to add"
              help="JPG/JPEG/PNG/WEBP"
              onClick={() => imageInputRef.current?.click()}
              onDragState={setIsImageDragging}
              onDrop={async (files) => handleAddImages(files)}
            />
            <input
              ref={imageInputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.webp,image/*"
              multiple
              className="hidden"
              onChange={(event) => {
                const files = Array.from(event.target.files ?? [])
                handleAddImages(files)
                event.currentTarget.value = ''
              }}
            />
            <div className="grid grid-cols-3 gap-2">
              {images.map((item, index) => (
                <div key={`${item.file.name}-${index}`} className="relative rounded border border-gray-700 overflow-hidden">
                  <img src={item.previewUrl} alt={`Image ${index + 1}`} className="aspect-square object-cover w-full" />
                  <button
                    type="button"
                    onClick={() => removeImage(index)}
                    className="absolute top-1 right-1 rounded bg-black/70 px-1.5 py-0.5 text-[10px] text-white"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-200">Videos</h3>
              <span className="text-xs text-gray-500">{videos.length}/3</span>
            </div>
            <DropZone
              dragging={isVideoDragging}
              label="Drop videos or click to add"
              help="MP4/MOV/WEBM (≤15s total)"
              onClick={() => videoInputRef.current?.click()}
              onDragState={setIsVideoDragging}
              onDrop={handleAddVideos}
            />
            <input
              ref={videoInputRef}
              type="file"
              accept=".mp4,.mov,.webm,video/*"
              multiple
              className="hidden"
              onChange={async (event) => {
                const files = Array.from(event.target.files ?? [])
                await handleAddVideos(files)
                event.currentTarget.value = ''
              }}
            />
            <div className="space-y-1">
              {videos.map((item, index) => (
                <div
                  key={`${item.file.name}-${index}`}
                  className="flex items-center justify-between rounded border border-gray-700 bg-gray-800/40 px-2 py-1.5 text-xs"
                >
                  <span className="truncate text-gray-200">{item.file.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="rounded border border-gray-600 px-1.5 py-0.5 text-gray-300">
                      {item.durationSec.toFixed(1)}s
                    </span>
                    <button
                      type="button"
                      onClick={() => removeVideo(index)}
                      className="text-gray-400 hover:text-red-300"
                    >
                      ×
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-200">Audio</h3>
              <span className="text-xs text-gray-500">{audios.length}/3</span>
            </div>
            <DropZone
              dragging={isAudioDragging}
              label="Drop MP3 or click to add"
              help="MP3 only (≤15s total)"
              onClick={() => audioInputRef.current?.click()}
              onDragState={setIsAudioDragging}
              onDrop={handleAddAudios}
            />
            <input
              ref={audioInputRef}
              type="file"
              accept=".mp3,audio/mpeg"
              multiple
              className="hidden"
              onChange={async (event) => {
                const files = Array.from(event.target.files ?? [])
                await handleAddAudios(files)
                event.currentTarget.value = ''
              }}
            />
            <div className="space-y-1">
              {audios.map((item, index) => (
                <div
                  key={`${item.file.name}-${index}`}
                  className="flex items-center justify-between rounded border border-gray-700 bg-gray-800/40 px-2 py-1.5 text-xs"
                >
                  <span className="truncate text-gray-200">{item.file.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="rounded border border-gray-600 px-1.5 py-0.5 text-gray-300">
                      {item.durationSec.toFixed(1)}s
                    </span>
                    <button
                      type="button"
                      onClick={() => removeAudio(index)}
                      className="text-gray-400 hover:text-red-300"
                    >
                      ×
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-2 relative">
          <label className="block text-sm font-medium text-gray-300">@ Mention Prompt</label>
          <textarea
            ref={textareaRef}
            rows={5}
            value={prompt}
            onChange={(event) => handlePromptInput(event.target.value)}
            onKeyUp={(event) => {
              const target = event.currentTarget
              const cursor = target.selectionStart ?? target.value.length
              const before = target.value.slice(0, cursor)
              const token = before.slice(before.lastIndexOf('@') + 1)
              if (before.endsWith('@')) {
                setShowMentionMenu(mentionItems.length > 0)
              } else if (token.includes(' ') || token.includes('\n')) {
                setShowMentionMenu(false)
              }
            }}
            onBlur={() => {
              window.setTimeout(() => setShowMentionMenu(false), 120)
            }}
            className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
            placeholder='e.g. "@Image 1 as the first frame, @Video 1 for camera reference"'
          />
          {showMentionMenu && mentionItems.length > 0 && (
            <ul className="absolute left-2 bottom-12 z-10 max-h-44 w-56 overflow-auto rounded-lg border border-gray-700 bg-gray-900 shadow-lg">
              {mentionItems.map((label) => (
                <li key={label}>
                  <button
                    type="button"
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => insertMention(label)}
                    className="w-full px-3 py-2 text-left text-xs text-gray-200 hover:bg-gray-800"
                  >
                    @{label}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <p className="text-xs text-gray-500">
            e.g. "@Image 1 as the first frame, @Video 1 for camera reference"
          </p>
        </div>

        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-300">Output Duration: {durationSec}s</label>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="range"
              min={4}
              max={15}
              value={durationSec}
              onChange={(event) => setDurationSec(Math.max(4, Math.min(15, Number(event.target.value) || 8)))}
              className="flex-1 min-w-[180px]"
            />
            <input
              type="number"
              min={4}
              max={15}
              value={durationSec}
              onChange={(event) => setDurationSec(Math.max(4, Math.min(15, Number(event.target.value) || 8)))}
              className="w-20 rounded border border-gray-700 bg-gray-800 px-2 py-1 text-sm text-gray-100"
            />
          </div>
        </div>

        <div className="flex items-center justify-end">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitMutation.isPending || hasValidationError}
            className="rounded-lg bg-violet-600 px-5 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
          >
            {submitMutation.isPending ? 'Generating...' : 'Generate Video'}
          </button>
        </div>
      </section>

      {activeJobId && (
        <section className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-100">Generating...</h3>
            <span className={`rounded border px-2 py-1 text-xs ${statusClass(activeJobQuery.data?.status ?? 'pending')}`}>
              {activeJobQuery.data?.status ?? 'pending'}
            </span>
          </div>

          <div className="h-2 rounded bg-gray-800">
            <div
              className="h-full rounded bg-violet-500 transition-all duration-300"
              style={{ width: `${Math.max(0, Math.min(100, activeJobQuery.data?.progress ?? 0))}%` }}
            />
          </div>
          <p className="text-xs text-right text-gray-400">{activeJobQuery.data?.progress ?? 0}%</p>

          {activeOutputPath && (
            <VideoPlayer src={activeOutputPath} />
          )}
        </section>
      )}

      <section className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-100">Recent Jobs</h3>
          <span className="text-xs text-gray-500">Last 5</span>
        </div>

        {jobsQuery.isLoading ? (
          <p className="text-sm text-gray-400">Loading jobs...</p>
        ) : recentJobs.length === 0 ? (
          <p className="text-sm text-gray-500">No Seedance jobs yet.</p>
        ) : (
          <div className="space-y-2">
            {recentJobs.map((job) => (
              <div
                key={job.job_id}
                className="rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`rounded border px-2 py-0.5 text-[11px] ${statusClass(job.status)}`}>
                      {job.status}
                    </span>
                    <span className="text-xs text-gray-500">{formatDate(job.created_at)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {job.output_path && (
                      <a
                        href={`/data/${job.output_path}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-violet-300 hover:text-violet-200"
                      >
                        View Video
                      </a>
                    )}
                    <button
                      type="button"
                      onClick={() => {
                        if (!window.confirm('Delete this Seedance job?')) return
                        deleteMutation.mutate(job.job_id)
                      }}
                      className="text-xs text-red-300 hover:text-red-200"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                {job.error_msg && (
                  <p className="mt-1 text-xs text-red-300">{job.error_msg}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

interface DropZoneProps {
  dragging: boolean
  label: string
  help: string
  onClick: () => void
  onDrop: (files: File[]) => Promise<void> | void
  onDragState: (value: boolean) => void
}

function DropZone({
  dragging,
  label,
  help,
  onClick,
  onDrop,
  onDragState,
}: DropZoneProps) {
  const handleDrop = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    onDragState(false)
    const files = Array.from(event.dataTransfer.files ?? [])
    await onDrop(files)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onClick()
        }
      }}
      onDragOver={(event) => {
        event.preventDefault()
        onDragState(true)
      }}
      onDragLeave={() => onDragState(false)}
      onDrop={handleDrop}
      className={`rounded-lg border-2 border-dashed px-3 py-6 text-center transition-colors cursor-pointer ${
        dragging
          ? 'border-violet-400 bg-violet-500/10'
          : 'border-gray-700 bg-gray-950/50 hover:border-violet-500/70'
      }`}
    >
      <p className="text-sm text-gray-300">{label}</p>
      <p className="mt-1 text-xs text-gray-500">{help}</p>
    </div>
  )
}
