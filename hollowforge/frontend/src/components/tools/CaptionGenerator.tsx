import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { notify } from '../../lib/toast'

interface CaptionResponse {
  story: string
  hashtags: string
}

interface ApiErrorResponse {
  detail?: string
}

function isImageFile(file: File): boolean {
  return file.type.startsWith('image/')
}

function parseApiError(payload: unknown): string {
  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as ApiErrorResponse).detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }
  return 'Failed to generate caption'
}

export default function CaptionGenerator() {
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [hasGenerated, setHasGenerated] = useState(false)
  const [story, setStory] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl)
      }
    }
  }, [previewUrl])

  const setSelectedFile = (nextFile: File) => {
    setFile(nextFile)
    setStory('')
    setHashtags('')
    setHasGenerated(false)
    setErrorMessage(null)
    setPreviewUrl((previous) => {
      if (previous) {
        URL.revokeObjectURL(previous)
      }
      return URL.createObjectURL(nextFile)
    })
  }

  const handleIncomingFiles = (files: File[]) => {
    const imageFile = files.find((candidate) => isImageFile(candidate))
    if (!imageFile) {
      notify.error('Please upload an image file')
      return
    }
    setSelectedFile(imageFile)
  }

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    handleIncomingFiles(files)
    event.currentTarget.value = ''
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    setIsDragging(false)
    const files = Array.from(event.dataTransfer.files ?? [])
    handleIncomingFiles(files)
  }

  const handleGenerate = async () => {
    if (!file) {
      notify.error('Select an image first')
      return
    }

    setIsLoading(true)
    setErrorMessage(null)

    const formData = new FormData()
    formData.append('image', file)

    try {
      const response = await fetch('/api/tools/generate-caption', {
        method: 'POST',
        body: formData,
      })

      const rawText = await response.text()
      let payload: unknown = null

      if (rawText) {
        try {
          payload = JSON.parse(rawText)
        } catch {
          if (!response.ok) {
            throw new Error(rawText)
          }
        }
      }

      if (!response.ok) {
        throw new Error(parseApiError(payload))
      }

      if (!payload || typeof payload !== 'object') {
        throw new Error('Server returned an invalid response')
      }

      const data = payload as Partial<CaptionResponse>
      if (typeof data.story !== 'string' || typeof data.hashtags !== 'string') {
        throw new Error('Server returned incomplete caption fields')
      }

      setStory(data.story)
      setHashtags(data.hashtags)
      setHasGenerated(true)
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Failed to generate caption'
      setErrorMessage(message)
      notify.error(message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleCopyAll = async () => {
    if (!story && !hashtags) return
    const combined = `${story}\n\n${hashtags}`.trim()
    try {
      await navigator.clipboard.writeText(combined)
      notify.success('Story and hashtags copied')
    } catch {
      notify.error('Clipboard copy failed')
    }
  }

  return (
    <div className="space-y-5">
      <section className="rounded-xl border border-zinc-700 bg-zinc-900 p-5 shadow-[0_0_0_1px_rgba(16,185,129,0.04)]">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-lg font-semibold text-emerald-400">Image-to-Caption Generator</h3>
            <p className="text-sm text-zinc-400">
              Drop one image and generate a classified story log plus hashtags.
            </p>
          </div>
        </div>

        <div
          role="button"
          tabIndex={0}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(event) => {
            event.preventDefault()
            setIsDragging(true)
          }}
          onDragEnter={() => setIsDragging(true)}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
              setIsDragging(false)
            }
          }}
          onDrop={handleDrop}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              fileInputRef.current?.click()
            }
          }}
          className={`group rounded-xl border-2 border-dashed p-6 transition-colors cursor-pointer ${
            isDragging
              ? 'border-emerald-400 bg-zinc-800'
              : 'border-zinc-700 bg-zinc-900/60 hover:border-emerald-500 hover:bg-zinc-800'
          }`}
          aria-label="Upload image for caption generation"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,.png,.jpg,.jpeg,.webp"
            className="hidden"
            onChange={handleInputChange}
          />

          {!previewUrl ? (
            <div className="text-center space-y-2">
              <p className="text-sm font-medium text-zinc-200">Drag and drop image here</p>
              <p className="text-xs text-zinc-500">or click to browse PNG / JPG / WEBP</p>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <img
                src={previewUrl}
                alt={file?.name ?? 'Selected preview'}
                className="h-28 w-28 rounded-lg border border-zinc-700 object-cover"
              />
              <div>
                <p className="text-sm font-medium text-zinc-100 truncate max-w-[18rem]">{file?.name}</p>
                <p className="text-xs text-zinc-400 mt-1">
                  {(file ? file.size / 1024 / 1024 : 0).toFixed(2)} MB
                </p>
                <p className="text-xs text-emerald-400 mt-2">Click or drop another image to replace</p>
              </div>
            </div>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={isLoading || !file}
            className="inline-flex items-center gap-2 rounded-lg border border-emerald-500 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-300 transition-colors hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <svg
                  className="h-4 w-4 animate-spin"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
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
      </section>

      {hasGenerated && (
        <section className="rounded-xl border border-zinc-700 bg-zinc-800 p-5 space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-emerald-400">Story</label>
            <textarea
              rows={4}
              value={story}
              onChange={(event) => setStory(event.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-emerald-400">Hashtags</label>
            <textarea
              rows={3}
              value={hashtags}
              onChange={(event) => setHashtags(event.target.value)}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleCopyAll}
              className="rounded-lg border border-emerald-500 bg-emerald-500/10 px-3.5 py-2 text-sm font-medium text-emerald-300 hover:bg-emerald-500/20"
            >
              Copy All
            </button>
          </div>
        </section>
      )}
    </div>
  )
}
