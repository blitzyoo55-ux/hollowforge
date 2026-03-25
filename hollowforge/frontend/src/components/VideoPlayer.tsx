import { useEffect, useMemo, useState } from 'react'

interface VideoPlayerProps {
  src: string
  className?: string
}

function resolveVideoSrc(src: string): string {
  if (!src) return src
  if (src.startsWith('http://') || src.startsWith('https://') || src.startsWith('/')) {
    return src
  }
  return `/data/${src}`
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export default function VideoPlayer({ src, className = '' }: VideoPlayerProps) {
  const [sizeInfo, setSizeInfo] = useState<{ src: string; bytes: number | null }>({
    src: '',
    bytes: null,
  })
  const resolvedSrc = useMemo(() => resolveVideoSrc(src), [src])
  const sizeBytes = sizeInfo.src === resolvedSrc ? sizeInfo.bytes : null

  useEffect(() => {
    let cancelled = false

    const loadSize = async () => {
      if (!resolvedSrc) {
        if (!cancelled) {
          setSizeInfo({ src: resolvedSrc, bytes: null })
        }
        return
      }
      try {
        const res = await fetch(resolvedSrc, { method: 'HEAD' })
        const contentLength = res.headers.get('content-length')
        if (!cancelled && contentLength) {
          const parsed = Number(contentLength)
          if (Number.isFinite(parsed) && parsed > 0) {
            setSizeInfo({ src: resolvedSrc, bytes: parsed })
            return
          }
        }
      } catch {
        // Cross-origin or missing HEAD support: silently skip file size.
      }
      if (!cancelled) {
        setSizeInfo({ src: resolvedSrc, bytes: null })
      }
    }

    void loadSize()
    return () => {
      cancelled = true
    }
  }, [resolvedSrc])

  return (
    <div className={`space-y-2 ${className}`}>
      <video controls autoPlay={false} loop className="w-full rounded-lg border border-gray-700 bg-black">
        <source src={resolvedSrc} />
      </video>
      <div className="flex items-center justify-between text-xs text-gray-400">
        <span>{sizeBytes != null ? `File size: ${formatFileSize(sizeBytes)}` : 'File size: unknown'}</span>
        <a
          href={resolvedSrc}
          download
          className="rounded-md border border-gray-700 bg-gray-800 px-2.5 py-1 text-gray-200 hover:bg-gray-700"
        >
          Download
        </a>
      </div>
    </div>
  )
}
