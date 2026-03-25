import { useMemo, useState } from 'react'
import { notify } from '../lib/toast'

const PLATFORM_OPTIONS = [
  { value: 'fanbox', label: 'Fanbox', spec: '1200px JPEG' },
  { value: 'fansly', label: 'Fansly', spec: '1080px JPEG' },
  { value: 'twitter', label: 'Twitter', spec: '1280px JPEG' },
  { value: 'pixiv', label: 'Pixiv', spec: '2048px JPEG' },
  { value: 'custom', label: 'Custom', spec: 'Original size JPEG' },
] as const

type ExportPlatform = (typeof PLATFORM_OPTIONS)[number]['value']

interface ExportModalProps {
  selectedIds: string[]
  onClose: () => void
}

function filenameFromDisposition(contentDisposition: string | null): string | null {
  if (!contentDisposition) return null
  const match = contentDisposition.match(/filename="?([^"]+)"?/)
  if (!match || !match[1]) return null
  return match[1]
}

export default function ExportModal({ selectedIds, onClose }: ExportModalProps) {
  const [platform, setPlatform] = useState<ExportPlatform>('fanbox')
  const [applyWatermark, setApplyWatermark] = useState(true)
  const [includeOriginals, setIncludeOriginals] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const selectedCount = selectedIds.length
  const activePlatform = useMemo(
    () => PLATFORM_OPTIONS.find((item) => item.value === platform),
    [platform],
  )

  const handleExport = async () => {
    if (selectedCount === 0 || isExporting) return
    setError(null)
    setIsExporting(true)

    try {
      const res = await fetch('/api/v1/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          generation_ids: selectedIds,
          platform,
          apply_watermark: applyWatermark,
          include_originals: includeOriginals,
        }),
      })

      if (!res.ok) {
        let detail = `Export failed (${res.status})`
        try {
          const body = await res.json()
          if (body?.detail) {
            detail = String(body.detail)
          }
        } catch {
          // ignore non-json error responses
        }
        throw new Error(detail)
      }

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const filename =
        filenameFromDisposition(res.headers.get('Content-Disposition')) ??
        `export_${platform}_${Date.now()}.zip`
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filename
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      notify.success('내보내기가 완료되었습니다')
      onClose()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to export images'
      setError(message)
      notify.error(message)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm px-4 flex items-center justify-center">
      <div className="w-full max-w-lg rounded-xl border border-gray-800 bg-gray-900 p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-100">
            Export Images ({selectedCount} selected)
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300"
            disabled={isExporting}
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-300">Platform</label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value as ExportPlatform)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-100 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
              disabled={isExporting}
            >
              {PLATFORM_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label} ({item.spec})
                </option>
              ))}
            </select>
            <p className="mt-1 text-xs text-gray-500">Selected spec: {activePlatform?.spec}</p>
          </div>

          <label className="flex cursor-pointer items-center justify-between rounded-lg border border-gray-800 bg-gray-800/40 px-3 py-2 text-sm text-gray-300">
            <span>Apply Watermark</span>
            <input
              type="checkbox"
              checked={applyWatermark}
              onChange={(e) => setApplyWatermark(e.target.checked)}
              className="h-4 w-4 accent-violet-500"
              disabled={isExporting}
            />
          </label>

          <label className="flex cursor-pointer items-center justify-between rounded-lg border border-gray-800 bg-gray-800/40 px-3 py-2 text-sm text-gray-300">
            <span>Include Originals</span>
            <input
              type="checkbox"
              checked={includeOriginals}
              onChange={(e) => setIncludeOriginals(e.target.checked)}
              className="h-4 w-4 accent-violet-500"
              disabled={isExporting}
            />
          </label>

          {isExporting && (
            <div className="flex items-center gap-2 rounded-lg border border-violet-500/30 bg-violet-500/10 px-3 py-2 text-sm text-violet-300">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet-400/40 border-t-violet-300" />
              Preparing export...
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-800/50 bg-red-900/20 px-3 py-2 text-sm text-red-400">
              {error}
            </div>
          )}
        </div>

        <div className="mt-6 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-gray-800 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700"
            disabled={isExporting}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={isExporting || selectedCount === 0}
            className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isExporting ? 'Preparing...' : 'Export'}
          </button>
        </div>
      </div>
    </div>
  )
}
