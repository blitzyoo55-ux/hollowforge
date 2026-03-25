import { useEffect, useState } from 'react'
import ReactDOM from 'react-dom'
import { generateCaptionById, type GenerationResponse } from '../../api/client'
import { notify } from '../../lib/toast'

interface CaptionModalProps {
  isOpen: boolean
  item: GenerationResponse | null
  onClose: () => void
}

interface ApiErrorResponse {
  detail?: string
}

function toDataUrl(path: string | null): string | null {
  if (!path) return null
  if (path.startsWith('/data/')) return path
  return `/data/${path.replace(/^\/+/, '')}`
}

function parseApiError(error: unknown): string {
  if (typeof error === 'object' && error !== null) {
    const maybeResponse = (error as { response?: { data?: ApiErrorResponse } }).response
    const detail = maybeResponse?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }

    const maybeMessage = (error as { message?: unknown }).message
    if (typeof maybeMessage === 'string' && maybeMessage.trim()) {
      return maybeMessage
    }
  }
  return 'Failed to generate caption'
}

export default function CaptionModal({ isOpen, item, onClose }: CaptionModalProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [hasGenerated, setHasGenerated] = useState(false)
  const [story, setStory] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return

    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = originalOverflow
    }
  }, [isOpen, onClose])

  useEffect(() => {
    if (!isOpen) return
    setIsLoading(false)
    setHasGenerated(false)
    setStory('')
    setHashtags('')
    setErrorMessage(null)
  }, [isOpen, item?.id])

  if (!isOpen || !item) return null

  const imageSrc = toDataUrl(item.image_path || item.thumbnail_path)

  const handleGenerate = async () => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const result = await generateCaptionById(item.id)
      setStory(result.story)
      setHashtags(result.hashtags)
      setHasGenerated(true)
    } catch (error: unknown) {
      const message = parseApiError(error)
      setErrorMessage(message)
      notify.error(message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCopyAll = async () => {
    if (!story && !hashtags) return
    try {
      await navigator.clipboard.writeText(`${story}\n\n${hashtags}`.trim())
      notify.success('Story and hashtags copied')
    } catch {
      notify.error('Clipboard copy failed')
    }
  }

  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
      aria-modal="true"
      role="dialog"
    >
      <div
        className="relative h-[90vh] w-full max-w-7xl overflow-hidden rounded-2xl border border-zinc-700 bg-zinc-900 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 z-20 rounded-lg border border-zinc-600 bg-zinc-900/80 px-2 py-1 text-sm text-zinc-200 hover:bg-zinc-800"
          aria-label="Close caption modal"
        >
          X
        </button>

        <div className="grid h-full grid-cols-1 lg:grid-cols-2">
          <div className="flex min-h-0 items-center justify-center bg-zinc-950 p-4 pt-12 lg:pt-6">
            {imageSrc ? (
              <img
                src={imageSrc}
                alt={item.prompt.slice(0, 120)}
                className="max-h-full max-w-full rounded-xl border border-zinc-800 object-contain"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900 text-sm text-zinc-400">
                Image not available
              </div>
            )}
          </div>

          <div className="flex min-h-0 flex-col bg-zinc-800 p-5 pt-12 lg:pt-6">
            <h3 className="text-base font-semibold tracking-wide text-emerald-400">CAPTION GENERATOR</h3>
            <p className="mt-2 text-xs text-zinc-400">
              Image ID: <span className="font-mono text-zinc-300">{item.id}</span>
            </p>

            <div className="mt-4 flex items-center gap-3">
              <button
                type="button"
                onClick={handleGenerate}
                disabled={isLoading}
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading ? (
                  <>
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeOpacity="0.25" strokeWidth="4" />
                      <path d="M22 12a10 10 0 00-10-10" stroke="currentColor" strokeWidth="4" />
                    </svg>
                    Generating...
                  </>
                ) : (
                  'Generate Caption'
                )}
              </button>
              {errorMessage && <p className="text-sm text-red-400">{errorMessage}</p>}
            </div>

            <div className="mt-4 flex min-h-0 flex-1 flex-col gap-3">
              <div className="flex min-h-0 flex-1 flex-col">
                <label className="mb-1.5 block text-sm font-medium text-emerald-400">Story</label>
                <textarea
                  rows={7}
                  value={story}
                  onChange={(event) => setStory(event.target.value)}
                  className="min-h-0 flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  placeholder="Generate a caption to populate this field."
                />
              </div>

              <div>
                <label className="mb-1.5 block text-sm font-medium text-emerald-400">Hashtags</label>
                <textarea
                  rows={4}
                  value={hashtags}
                  onChange={(event) => setHashtags(event.target.value)}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                  placeholder="#Tag1 #Tag2 #Tag3"
                />
              </div>

              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-zinc-500">
                  {hasGenerated ? 'Result ready. Edit before copying if needed.' : 'Click Generate Caption to begin.'}
                </p>
                <button
                  type="button"
                  onClick={handleCopyAll}
                  disabled={!story && !hashtags}
                  className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-300 hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Copy All
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
