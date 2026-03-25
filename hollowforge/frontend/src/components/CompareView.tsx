import { useCallback, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type TouchEvent as ReactTouchEvent } from 'react'
import ReactDOM from 'react-dom'

interface CompareImage {
  url: string
  label: string
}

interface CompareViewProps {
  leftImage: CompareImage
  rightImage: CompareImage
  onClose: () => void
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export default function CompareView({ leftImage, rightImage, onClose }: CompareViewProps) {
  const [sliderPct, setSliderPct] = useState<number>(50)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const containerRef = useRef<HTMLDivElement | null>(null)

  const updateSliderByClientX = useCallback((clientX: number) => {
    const bounds = containerRef.current?.getBoundingClientRect()
    if (!bounds || bounds.width === 0) return

    const relativeX = clientX - bounds.left
    const percentage = (relativeX / bounds.width) * 100
    setSliderPct(clamp(percentage, 0, 100))
  }, [])

  const stopDragging = useCallback(() => {
    setIsDragging(false)
  }, [])

  const startDragging = useCallback(
    (clientX: number) => {
      setIsDragging(true)
      updateSliderByClientX(clientX)
    },
    [updateSliderByClientX],
  )

  const handleMouseDown = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      event.preventDefault()
      startDragging(event.clientX)
    },
    [startDragging],
  )

  const handleTouchStart = useCallback(
    (event: ReactTouchEvent<HTMLDivElement>) => {
      if (event.touches.length === 0) return
      event.preventDefault()
      startDragging(event.touches[0].clientX)
    },
    [startDragging],
  )

  const handleMouseMove = useCallback(
    (event: globalThis.MouseEvent) => {
      if (!isDragging) return
      updateSliderByClientX(event.clientX)
    },
    [isDragging, updateSliderByClientX],
  )

  const handleTouchMove = useCallback(
    (event: globalThis.TouchEvent) => {
      if (!isDragging || event.touches.length === 0) return
      event.preventDefault()
      updateSliderByClientX(event.touches[0].clientX)
    },
    [isDragging, updateSliderByClientX],
  )

  useEffect(() => {
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
  }, [onClose])

  useEffect(() => {
    if (!isDragging) return

    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', stopDragging)
    window.addEventListener('mouseleave', stopDragging)
    window.addEventListener('touchmove', handleTouchMove, { passive: false })
    window.addEventListener('touchend', stopDragging)
    window.addEventListener('touchcancel', stopDragging)

    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', stopDragging)
      window.removeEventListener('mouseleave', stopDragging)
      window.removeEventListener('touchmove', handleTouchMove)
      window.removeEventListener('touchend', stopDragging)
      window.removeEventListener('touchcancel', stopDragging)
    }
  }, [handleMouseMove, handleTouchMove, isDragging, stopDragging])

  return ReactDOM.createPortal(
    <div
      className="fixed inset-0 z-50 bg-black/90"
      onClick={onClose}
      onMouseLeave={stopDragging}
      role="dialog"
      aria-modal="true"
      aria-label="Image comparison view"
    >
      <div className="absolute inset-0 p-3 sm:p-6" onClick={(event) => event.stopPropagation()}>
        <div className="relative h-full w-full overflow-hidden rounded-xl border border-gray-800 bg-gray-950">
          <button
            type="button"
            onClick={onClose}
            className="absolute right-3 top-3 z-30 rounded-lg border border-white/20 bg-black/60 px-2 py-1 text-xs text-white hover:bg-black/80"
            aria-label="Close compare view"
          >
            ESC
          </button>

          <div
            ref={containerRef}
            className="relative h-full w-full select-none touch-none"
          >
            <img
              src={rightImage.url}
              alt={rightImage.label}
              className="pointer-events-none absolute inset-0 h-full w-full object-contain"
              draggable={false}
            />
            <img
              src={leftImage.url}
              alt={leftImage.label}
              className="pointer-events-none absolute inset-0 h-full w-full object-contain"
              style={{ clipPath: `inset(0 ${100 - sliderPct}% 0 0)` }}
              draggable={false}
            />

            <div className="absolute left-4 top-4 z-20 rounded-full bg-black/60 px-2 py-1 text-xs text-white">
              {leftImage.label}
            </div>
            <div className="absolute right-4 top-4 z-20 rounded-full bg-black/60 px-2 py-1 text-xs text-white">
              {rightImage.label}
            </div>

            <div
              className="absolute inset-y-0 z-20 w-8 -translate-x-1/2 cursor-ew-resize touch-none"
              style={{ left: `${sliderPct}%` }}
              onMouseDown={handleMouseDown}
              onTouchStart={handleTouchStart}
            >
              <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-white" />
              <div className="absolute left-1/2 top-1/2 flex h-8 w-8 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white shadow-lg">
                <svg
                  aria-hidden="true"
                  viewBox="0 0 20 20"
                  className="h-4 w-4 text-gray-900"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.8}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 6 4 10l4 4" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="m12 6 4 4-4 4" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
