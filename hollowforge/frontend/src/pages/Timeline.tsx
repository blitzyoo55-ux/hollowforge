import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getGalleryTimeline } from '../api/client'
import type { TimelineDailyItem } from '../api/client'

const DAY_OPTIONS = [7, 30, 90] as const

function formatDate(value: string): string {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

function formatDateLong(value: string): string {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function formatAvgSeconds(value: number | null): string {
  if (value == null) return '-'
  return `${value.toFixed(1)}s`
}

function heatColor(count: number, maxCount: number): string {
  if (count <= 0) return 'rgba(55, 65, 81, 0.45)'
  if (maxCount <= 0) return 'rgba(124, 58, 237, 0.35)'
  const ratio = count / maxCount
  if (ratio < 0.25) return 'rgba(124, 58, 237, 0.35)'
  if (ratio < 0.5) return 'rgba(124, 58, 237, 0.55)'
  if (ratio < 0.75) return 'rgba(124, 58, 237, 0.75)'
  return 'rgba(139, 92, 246, 0.95)'
}

function buildHeatCells(daily: TimelineDailyItem[]): Array<{ key: string; date: string | null; count: number }> {
  if (daily.length === 0) return []
  const firstDate = new Date(`${daily[0].date}T00:00:00Z`)
  const leading = firstDate.getUTCDay()
  const cells: Array<{ key: string; date: string | null; count: number }> = []

  for (let i = 0; i < leading; i += 1) {
    cells.push({ key: `pad-${i}`, date: null, count: 0 })
  }

  for (const item of daily) {
    cells.push({ key: item.date, date: item.date, count: item.count })
  }

  return cells
}

export default function Timeline() {
  const [days, setDays] = useState<(typeof DAY_OPTIONS)[number]>(30)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['gallery-timeline', days],
    queryFn: () => getGalleryTimeline(days),
    staleTime: 30_000,
  })

  const todayIso = new Date().toISOString().slice(0, 10)

  const todayCount = useMemo(() => {
    if (!data) return 0
    return data.daily.find((item) => item.date === todayIso)?.count ?? 0
  }, [data, todayIso])

  const weekCount = useMemo(() => {
    if (!data) return 0
    return data.daily.slice(-7).reduce((sum, item) => sum + item.count, 0)
  }, [data])

  const heatCells = useMemo(() => buildHeatCells(data?.daily ?? []), [data])

  const maxDailyCount = useMemo(() => {
    return Math.max(1, ...(data?.daily ?? []).map((item) => item.count))
  }, [data])

  const dailyChart = useMemo(() => {
    const daily = data?.daily ?? []
    const chartHeight = 220
    const top = 18
    const bottom = 40
    const left = 36
    const right = 12
    const plotHeight = chartHeight - top - bottom
    const barWidth = 8
    const gap = 4
    const width = Math.max(680, left + right + daily.length * (barWidth + gap))
    const labelStep = Math.max(1, Math.ceil(daily.length / 10))

    return {
      daily,
      chartHeight,
      left,
      top,
      plotHeight,
      width,
      barWidth,
      gap,
      labelStep,
      max: Math.max(1, ...daily.map((item) => item.count)),
      bottom,
    }
  }, [data])

  const hourChart = useMemo(() => {
    const hours = data?.by_hour ?? Array.from({ length: 24 }, (_, hour) => ({ hour, count: 0 }))
    const chartHeight = 180
    const top = 12
    const bottom = 28
    const left = 12
    const right = 12
    const plotHeight = chartHeight - top - bottom
    const barWidth = 14
    const gap = 6
    const width = Math.max(640, left + right + hours.length * (barWidth + gap))
    const max = Math.max(1, ...hours.map((item) => item.count))

    return {
      hours,
      chartHeight,
      top,
      bottom,
      left,
      right,
      plotHeight,
      width,
      barWidth,
      gap,
      max,
    }
  }, [data])

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Timeline</h2>
          <p className="text-sm text-gray-400 mt-1">Generation history, streaks, and usage patterns</p>
        </div>
        <div className="inline-flex w-full rounded-lg border border-gray-700 bg-gray-900 p-1 sm:w-auto">
          {DAY_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setDays(option)}
              className={`flex-1 px-3 py-1.5 text-xs rounded-md transition-colors sm:flex-none ${
                days === option
                  ? 'bg-violet-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800'
              }`}
            >
              {option}D
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <div key={`stat-skeleton-${idx}`} className="h-24 rounded-xl border border-gray-800 bg-gray-900 animate-pulse" />
            ))}
          </div>
          <div className="h-56 rounded-xl border border-gray-800 bg-gray-900 animate-pulse" />
          <div className="h-72 rounded-xl border border-gray-800 bg-gray-900 animate-pulse" />
        </div>
      ) : isError || !data ? (
        <div className="bg-gray-900 rounded-xl border border-red-800/50 p-5 text-sm text-red-300">
          Timeline 데이터를 불러오지 못했습니다.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Total</p>
              <p className="text-2xl font-semibold text-gray-100 mt-1">{data.total}</p>
              <p className="text-xs text-gray-500 mt-1">Last {days} days</p>
            </div>
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Today</p>
              <p className="text-2xl font-semibold text-gray-100 mt-1">{todayCount}</p>
              <p className="text-xs text-gray-500 mt-1">UTC 기준</p>
            </div>
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wide">This Week</p>
              <p className="text-2xl font-semibold text-gray-100 mt-1">{weekCount}</p>
              <p className="text-xs text-gray-500 mt-1">최근 7일 합계</p>
            </div>
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
              <p className="text-xs text-gray-400 uppercase tracking-wide">Current Streak</p>
              <p className="text-2xl font-semibold text-violet-300 mt-1">{data.streak.current_days}d</p>
              <p className="text-xs text-gray-500 mt-1">Longest {data.streak.longest_days}d</p>
            </div>
          </div>

          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 md:p-5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-base font-semibold text-gray-100">Daily Heatmap</h3>
              <p className="text-xs text-gray-500">GitHub-style activity grid</p>
            </div>
            <div className="overflow-x-auto">
              <div className="min-w-max flex gap-3">
                <div className="grid grid-rows-7 gap-1 text-[10px] text-gray-600 pr-2">
                  <span>Sun</span>
                  <span />
                  <span>Tue</span>
                  <span />
                  <span>Thu</span>
                  <span />
                  <span>Sat</span>
                </div>
                <div className="grid grid-flow-col grid-rows-7 gap-1">
                  {heatCells.map((cell) => (
                    <div
                      key={cell.key}
                      className={`h-3 w-3 rounded-[3px] border ${cell.date ? 'border-gray-800/60' : 'border-transparent'}`}
                      style={{ backgroundColor: cell.date ? heatColor(cell.count, maxDailyCount) : 'transparent' }}
                      title={cell.date ? `${formatDateLong(cell.date)}: ${cell.count} generation(s)` : ''}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 md:p-5 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-base font-semibold text-gray-100">Daily Volume</h3>
              <p className="text-xs text-gray-500">Hover each bar for details</p>
            </div>
            <div className="overflow-x-auto">
              <svg
                viewBox={`0 0 ${dailyChart.width} ${dailyChart.chartHeight}`}
                className="h-56"
                style={{ width: `${dailyChart.width}px` }}
                role="img"
                aria-label="Daily generation bar chart"
              >
                <line
                  x1={dailyChart.left}
                  y1={dailyChart.chartHeight - dailyChart.bottom}
                  x2={dailyChart.width - 8}
                  y2={dailyChart.chartHeight - dailyChart.bottom}
                  stroke="rgba(75,85,99,0.8)"
                  strokeWidth={1}
                />
                {dailyChart.daily.map((item, idx) => {
                  const x = dailyChart.left + idx * (dailyChart.barWidth + dailyChart.gap)
                  const height = (item.count / dailyChart.max) * dailyChart.plotHeight
                  const y = dailyChart.top + (dailyChart.plotHeight - height)
                  const showLabel = idx % dailyChart.labelStep === 0 || idx === dailyChart.daily.length - 1
                  return (
                    <g key={item.date}>
                      <rect
                        x={x}
                        y={y}
                        width={dailyChart.barWidth}
                        height={Math.max(1, height)}
                        rx={2}
                        fill="rgba(139,92,246,0.9)"
                      >
                        <title>
                          {`${formatDateLong(item.date)} | total ${item.count}, completed ${item.completed}, failed ${item.failed}, cancelled ${item.cancelled}, avg ${formatAvgSeconds(item.avg_generation_time_sec)}`}
                        </title>
                      </rect>
                      {showLabel && (
                        <text
                          x={x + dailyChart.barWidth / 2}
                          y={dailyChart.chartHeight - 14}
                          textAnchor="middle"
                          fontSize="10"
                          fill="rgba(156,163,175,0.9)"
                        >
                          {formatDate(item.date)}
                        </text>
                      )}
                    </g>
                  )
                })}
              </svg>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-5 space-y-3">
              <h3 className="text-base font-semibold text-gray-100">Checkpoint Distribution</h3>
              {data.by_checkpoint.length === 0 ? (
                <p className="text-sm text-gray-500">Completed generation data가 없습니다.</p>
              ) : (
                <div className="space-y-3">
                  {data.by_checkpoint.map((item) => (
                    <div key={item.checkpoint}>
                      <div className="flex items-center justify-between text-xs mb-1.5 gap-2">
                        <span className="text-gray-300 truncate" title={item.checkpoint}>{item.checkpoint}</span>
                        <span className="text-gray-400 font-mono">{item.count} ({item.pct.toFixed(1)}%)</span>
                      </div>
                      <div className="h-2 rounded-full bg-gray-800 overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-violet-700 to-violet-400"
                          style={{ width: `${Math.min(100, Math.max(0, item.pct))}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 md:p-5 space-y-3">
              <h3 className="text-base font-semibold text-gray-100">By Hour (UTC)</h3>
              <div className="overflow-x-auto">
                <svg
                  viewBox={`0 0 ${hourChart.width} ${hourChart.chartHeight}`}
                  className="h-40"
                  style={{ width: `${hourChart.width}px` }}
                  role="img"
                  aria-label="Hourly generation distribution"
                >
                  <line
                    x1={hourChart.left}
                    y1={hourChart.chartHeight - hourChart.bottom}
                    x2={hourChart.width - hourChart.right}
                    y2={hourChart.chartHeight - hourChart.bottom}
                    stroke="rgba(75,85,99,0.8)"
                    strokeWidth={1}
                  />
                  {hourChart.hours.map((item) => {
                    const x = hourChart.left + item.hour * (hourChart.barWidth + hourChart.gap)
                    const h = (item.count / hourChart.max) * hourChart.plotHeight
                    const y = hourChart.top + (hourChart.plotHeight - h)
                    return (
                      <g key={`hour-${item.hour}`}>
                        <rect
                          x={x}
                          y={y}
                          width={hourChart.barWidth}
                          height={Math.max(1, h)}
                          rx={2}
                          fill="rgba(124,58,237,0.9)"
                        >
                          <title>{`${item.hour}:00 - ${item.count} generation(s)`}</title>
                        </rect>
                        {item.hour % 3 === 0 && (
                          <text
                            x={x + hourChart.barWidth / 2}
                            y={hourChart.chartHeight - 8}
                            textAnchor="middle"
                            fontSize="9"
                            fill="rgba(156,163,175,0.9)"
                          >
                            {item.hour}
                          </text>
                        )}
                      </g>
                    )
                  })}
                </svg>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
