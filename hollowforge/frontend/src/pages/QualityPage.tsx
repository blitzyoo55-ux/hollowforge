import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  addToCollection,
  batchAnalyzeQuality,
  createCollection,
  getCollections,
  getGallery,
  getQualityReport,
  getSystemHealth,
  type BatchAnalyzeResult,
  type CollectionResponse,
  type GenerationResponse,
} from '../api/client'

const HISTOGRAM_BUCKETS = [
  '0-9',
  '10-19',
  '20-29',
  '30-39',
  '40-49',
  '50-59',
  '60-69',
  '70-79',
  '80-89',
  '90-100',
] as const

function formatAnomalyRate(rate: number): string {
  const pct = rate <= 1 ? rate * 100 : rate
  return `${pct.toFixed(1)}%`
}

function histogramTone(index: number): string {
  if (index <= 2) return 'bg-red-500/80'
  if (index <= 5) return 'bg-amber-500/80'
  return 'bg-violet-500/80'
}

export default function QualityPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [lastBatchResult, setLastBatchResult] = useState<BatchAnalyzeResult | null>(null)
  const [sortBy, setSortBy] = useState<'quality_ai_score' | 'quality_score' | 'checkpoint' | 'created_at'>(
    'quality_ai_score',
  )
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc')
  const [filterCheckpoint, setFilterCheckpoint] = useState<string>('')
  const [minScore, setMinScore] = useState<number | ''>('')
  const [maxScore, setMaxScore] = useState<number | ''>('')
  const [showAnomalyOnly, setShowAnomalyOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [collectionDropdownId, setCollectionDropdownId] = useState<string | null>(null)
  const [newCollectionName, setNewCollectionName] = useState('')
  const [showNewCollectionInput, setShowNewCollectionInput] = useState(false)
  const PER_PAGE = 24

  const {
    data: report,
    isLoading: reportLoading,
    isError: reportError,
    refetch: refetchReport,
  } = useQuery({
    queryKey: ['quality-report'],
    queryFn: getQualityReport,
    refetchInterval: 15_000,
  })

  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: getSystemHealth,
    refetchInterval: 20_000,
  })

  const { data: galleryData, isLoading: galleryLoading } = useQuery({
    queryKey: [
      'quality-gallery',
      sortBy,
      sortOrder,
      filterCheckpoint,
      minScore,
      maxScore,
      showAnomalyOnly,
      page,
    ],
    queryFn: () =>
      getGallery({
        page,
        per_page: PER_PAGE,
        sort_by: sortBy,
        sort_order: sortOrder,
        checkpoint: filterCheckpoint || undefined,
        min_quality: minScore !== '' ? Number(minScore) : undefined,
        max_quality: maxScore !== '' ? Number(maxScore) : undefined,
      }),
    placeholderData: keepPreviousData,
  })

  const { data: collections } = useQuery({
    queryKey: ['collections'],
    queryFn: () => getCollections(),
  })

  const addToCollectionMutation = useMutation({
    mutationFn: async ({
      collectionId,
      generationId,
    }: {
      collectionId: string
      generationId: string
    }) => {
      await addToCollection(collectionId, generationId)
    },
    onSuccess: async () => {
      toast.success('콜렉션에 추가됨')
      setCollectionDropdownId(null)
      await queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
    onError: () => toast.error('콜렉션 추가 실패'),
  })

  const createAndAddMutation = useMutation({
    mutationFn: async ({ name, generationId }: { name: string; generationId: string }) => {
      const col = await createCollection({ name })
      await addToCollection(col.id, generationId)
    },
    onSuccess: async () => {
      toast.success('새 콜렉션에 추가됨')
      setCollectionDropdownId(null)
      setNewCollectionName('')
      setShowNewCollectionInput(false)
      await queryClient.invalidateQueries({ queryKey: ['collections'] })
    },
    onError: () => toast.error('콜렉션 생성 실패'),
  })

  const batchMutation = useMutation({
    mutationFn: ({ skipAnalyzed }: { skipAnalyzed: boolean }) =>
      // Re-Analyze All processes the full library (up to 2000); Analyze All targets unscored only
      batchAnalyzeQuality(skipAnalyzed ? 200 : 2000, skipAnalyzed),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['quality-report'] })
      await queryClient.invalidateQueries({ queryKey: ['system-health'] })
      // Refresh the image list so updated scores appear immediately
      await queryClient.invalidateQueries({ queryKey: ['quality-gallery'] })
    },
  })

  const histogramRows = useMemo(() => {
    if (!report) return []
    return HISTOGRAM_BUCKETS.map((bucket) => ({
      bucket,
      count: report.score_histogram[bucket] ?? 0,
    }))
  }, [report])

  const maxHistogramCount = Math.max(1, ...histogramRows.map((item) => item.count))

  const topBadTags = useMemo(() => {
    if (!report) return []
    return Object.entries(report.bad_tag_distribution)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
  }, [report])

  const estimatedPending =
    report && typeof health?.total_generations === 'number'
      ? Math.max(health.total_generations - report.total_analyzed, 0)
      : null

  const galleryItems = useMemo(() => {
    const items = galleryData?.items ?? []
    if (!showAnomalyOnly) return items
    return items.filter((item) => item.finger_anomaly === 1)
  }, [galleryData?.items, showAnomalyOnly])

  useEffect(() => {
    const handleDocumentClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null
      if (!target) return
      if (target.closest('[data-collection-dropdown="true"]')) return
      if (target.closest('[data-collection-toggle="true"]')) return
      setCollectionDropdownId(null)
      setShowNewCollectionInput(false)
    }

    document.addEventListener('click', handleDocumentClick)
    return () => document.removeEventListener('click', handleDocumentClick)
  }, [])

  const runBatchAnalyze = async (skipAnalyzed: boolean) => {
    const loadingId = toast.loading(
      skipAnalyzed ? '미분석 이미지를 분석 중입니다...' : '전체 이미지를 재분석 중입니다...',
    )

    try {
      const result = await batchMutation.mutateAsync({ skipAnalyzed })
      setLastBatchResult(result)
      toast.success(`처리됨: ${result.processed}, 스킵: ${result.skipped}, 오류: ${result.errors}`, {
        id: loadingId,
      })
    } catch {
      toast.error('배치 분석 실행 중 오류가 발생했습니다.', { id: loadingId })
    }
  }

  if (reportLoading) {
    return (
      <div className="p-4 md:p-6">
        <div className="flex items-center justify-center py-20">
          <span className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-400" />
        </div>
      </div>
    )
  }

  if (reportError || !report) {
    return (
      <div className="p-4 md:p-6 space-y-6">
        <h1 className="text-2xl font-bold text-gray-100">Quality AI</h1>
        <div className="bg-gray-900 border border-red-800/50 rounded-xl p-4 md:p-6 text-center space-y-4">
          <p className="text-red-300">품질 리포트를 불러오지 못했습니다.</p>
          <button
            type="button"
            onClick={() => refetchReport()}
            className="w-full px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium sm:w-auto"
          >
            다시 시도
          </button>
        </div>
      </div>
    )
  }

  const totalAnalyzed = report.total_analyzed
  const anomalyRateText = formatAnomalyRate(report.anomaly_rate)
  const isAnalyzing = batchMutation.isPending

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Quality AI</h1>
          <p className="text-sm text-gray-400 mt-1">이미지 품질/손가락 이상 감지 리포트</p>
        </div>
        <div className="text-xs text-gray-500">
          {health ? `Total images: ${health.total_generations.toLocaleString()}` : 'System total unavailable'}
        </div>
      </div>

      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">총 분석 수</p>
          <p className="text-2xl font-bold text-gray-100 mt-1">{totalAnalyzed.toLocaleString()}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">이상 감지 수</p>
          <p className="text-2xl font-bold text-red-300 mt-1">{report.anomaly_count.toLocaleString()}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">이상률</p>
          <p className="text-2xl font-bold text-violet-300 mt-1">{anomalyRateText}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider">미분석 수(추정)</p>
          <p className="text-2xl font-bold text-gray-100 mt-1">
            {estimatedPending === null ? '-' : estimatedPending.toLocaleString()}
          </p>
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4">
        <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-lg font-semibold text-gray-100">배치 분석</h2>
          <div className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:items-center">
            <button
              type="button"
              disabled={isAnalyzing}
              onClick={() => runBatchAnalyze(true)}
              className="w-full px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed sm:w-auto"
            >
              {isAnalyzing ? 'Analyzing...' : 'Analyze All'}
            </button>
            <button
              type="button"
              disabled={isAnalyzing}
              onClick={() => {
                const confirmed = window.confirm(
                  '전체 이미지 재분석을 실행할까요? 오래 걸릴 수 있습니다.',
                )
                if (!confirmed) return
                runBatchAnalyze(false)
              }}
              className="w-full px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-700/50 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed sm:w-auto"
            >
              Re-Analyze All
            </button>
          </div>
        </div>

        {isAnalyzing && (
          <div className="flex items-center gap-2 text-sm text-violet-300">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet-500/30 border-t-violet-400" />
            배치 분석 실행 중...
          </div>
        )}

        <div className="text-sm text-gray-300">
          {lastBatchResult ? (
            <span>
              처리됨: <span className="text-gray-100 font-medium">{lastBatchResult.processed}</span>, 스킵:{' '}
              <span className="text-gray-100 font-medium">{lastBatchResult.skipped}</span>, 오류:{' '}
              <span className="text-gray-100 font-medium">{lastBatchResult.errors}</span>
            </span>
          ) : (
            <span className="text-gray-500">최근 배치 실행 결과가 없습니다.</span>
          )}
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">점수 히스토그램</h2>
        <div className="space-y-2.5">
          {histogramRows.map((row, index) => {
            const widthPct = row.count > 0
              ? Math.max(2, (row.count / maxHistogramCount) * 100)
              : 0
            return (
              <div key={row.bucket} className="grid grid-cols-[52px_1fr_40px] gap-2 sm:grid-cols-[64px_1fr_48px] sm:gap-3 items-center">
                <span className="text-xs text-gray-400 font-mono">{row.bucket}</span>
                <div className="h-3 rounded-full bg-gray-800 overflow-hidden">
                  <div
                    className={`h-full ${histogramTone(index)} transition-all duration-500`}
                    style={{ width: `${widthPct}%` }}
                  />
                </div>
                <span className="text-xs text-gray-300 text-right font-mono">{row.count}</span>
              </div>
            )
          })}
        </div>
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-lg font-semibold text-gray-100 mb-4">불량 태그 분포 Top 10</h2>
        {topBadTags.length === 0 ? (
          <p className="text-sm text-gray-500">집계된 불량 태그가 없습니다.</p>
        ) : (
          <>
            <div className="space-y-2 md:hidden">
              {topBadTags.map(([tag, count]) => {
                const ratio = totalAnalyzed > 0 ? (count / totalAnalyzed) * 100 : 0
                return (
                  <div key={tag} className="rounded-lg border border-gray-800 bg-gray-950/50 p-3 space-y-1">
                    <p className="font-mono text-xs text-gray-300 break-all">{tag}</p>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-400">발생 횟수</span>
                      <span className="text-gray-200">{count.toLocaleString()}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-400">비율</span>
                      <span className="text-gray-200">{ratio.toFixed(1)}%</span>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="hidden md:block overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-800">
                    <th className="py-2 pr-4 font-medium">태그</th>
                    <th className="py-2 pr-4 font-medium">발생 횟수</th>
                    <th className="py-2 font-medium">비율</th>
                  </tr>
                </thead>
                <tbody>
                  {topBadTags.map(([tag, count]) => {
                    const ratio = totalAnalyzed > 0 ? (count / totalAnalyzed) * 100 : 0
                    return (
                      <tr key={tag} className="border-b border-gray-800/60 text-gray-200">
                        <td className="py-2 pr-4 font-mono text-xs">{tag}</td>
                        <td className="py-2 pr-4">{count.toLocaleString()}</td>
                        <td className="py-2">{ratio.toFixed(1)}%</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h2 className="text-lg font-semibold text-gray-100">이미지 목록</h2>

          <div className="flex flex-wrap gap-2 items-center w-full lg:w-auto">
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value as typeof sortBy)
                setPage(1)
              }}
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-1.5 sm:w-auto"
            >
              <option value="quality_ai_score">AI 점수순</option>
              <option value="quality_score">혼합 점수순</option>
              <option value="checkpoint">모델순</option>
              <option value="created_at">생성일순</option>
            </select>

            <button
              type="button"
              onClick={() => {
                setSortOrder((order) => (order === 'asc' ? 'desc' : 'asc'))
                setPage(1)
              }}
              className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg hover:bg-gray-700 sm:w-auto"
            >
              {sortOrder === 'asc' ? '↑ 오름차순' : '↓ 내림차순'}
            </button>

            <input
              type="number"
              min={0}
              max={100}
              placeholder="최소점수"
              value={minScore}
              onChange={(e) => {
                setMinScore(e.target.value === '' ? '' : Number(e.target.value))
                setPage(1)
              }}
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-1.5 sm:w-24"
            />
            <span className="hidden text-gray-500 text-sm sm:inline">~</span>
            <input
              type="number"
              min={0}
              max={100}
              placeholder="최대점수"
              value={maxScore}
              onChange={(e) => {
                setMaxScore(e.target.value === '' ? '' : Number(e.target.value))
                setPage(1)
              }}
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-1.5 sm:w-24"
            />

            <input
              type="text"
              placeholder="모델 필터..."
              value={filterCheckpoint}
              onChange={(e) => {
                setFilterCheckpoint(e.target.value)
                setPage(1)
              }}
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 text-sm rounded-lg px-3 py-1.5 sm:w-40"
            />

            <button
              type="button"
              onClick={() => setShowAnomalyOnly((prev) => !prev)}
              className={`w-full px-3 py-1.5 border text-sm rounded-lg sm:w-auto ${
                showAnomalyOnly
                  ? 'bg-red-900/30 border-red-700 text-red-300'
                  : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'
              }`}
            >
              손 이상만
            </button>
          </div>
        </div>

        {galleryLoading ? (
          <div className="text-center text-gray-500 py-12">로딩 중...</div>
        ) : !galleryItems.length ? (
          <div className="text-center text-gray-500 py-12">
            {showAnomalyOnly ? '조건에 맞는 이상 감지 이미지 없음' : '이미지 없음'}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {galleryItems.map((gen: GenerationResponse) => (
                <div
                  key={gen.id}
                  className="relative group rounded-lg overflow-hidden border border-gray-800 bg-gray-800 cursor-pointer"
                >
                  <div onClick={() => navigate(`/gallery/${gen.id}`)} className="aspect-square">
                    {gen.thumbnail_path ? (
                      <img
                        src={`/data/${gen.thumbnail_path}`}
                        alt={gen.id}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full bg-gray-700 flex items-center justify-center text-gray-500 text-xs">
                        No image
                      </div>
                    )}
                  </div>

                  <div
                    className={`absolute top-1 left-1 px-1.5 py-0.5 rounded text-xs font-bold ${
                      gen.quality_ai_score == null
                        ? 'bg-gray-700 text-gray-400'
                        : gen.quality_ai_score >= 90
                          ? 'bg-emerald-900/80 text-emerald-300'
                          : gen.quality_ai_score >= 70
                            ? 'bg-green-900/80 text-green-300'
                            : gen.quality_ai_score >= 50
                              ? 'bg-amber-900/80 text-amber-300'
                              : 'bg-red-900/80 text-red-300'
                    }`}
                  >
                    {gen.quality_ai_score ?? '?'}
                  </div>

                  {gen.finger_anomaly === 1 && (
                    <div
                      className="absolute top-1 right-1 px-1.5 py-0.5 rounded text-xs bg-red-900/80 text-red-300"
                      title="손/손가락 이상 감지"
                    >
                      HAND
                    </div>
                  )}

                  <div className="absolute bottom-0 left-0 right-0 bg-gray-900/90 px-2 py-1 flex items-center justify-between gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                    <span className="text-gray-400 text-xs truncate max-w-[80%]" title={gen.checkpoint}>
                      {gen.checkpoint?.split('/').pop()?.replace(/\.[^.]+$/, '') ?? '-'}
                    </span>

                    <div className="relative">
                      <button
                        type="button"
                        data-collection-toggle="true"
                        onClick={(event) => {
                          event.stopPropagation()
                          setCollectionDropdownId((prev) => (prev === gen.id ? null : gen.id))
                          setShowNewCollectionInput(false)
                        }}
                        className="p-1 rounded bg-violet-700/60 hover:bg-violet-600 text-white text-xs"
                        title="콜렉션에 추가"
                      >
                        +
                      </button>

                      {collectionDropdownId === gen.id && (
                        <div
                          data-collection-dropdown="true"
                          className="absolute bottom-8 right-0 z-50 w-48 max-w-[80vw] bg-gray-900 border border-gray-700 rounded-lg shadow-xl p-2 space-y-1"
                          onClick={(event) => event.stopPropagation()}
                        >
                          <p className="text-xs text-gray-500 px-1 mb-1">콜렉션 선택</p>
                          {collections?.map((col: CollectionResponse) => (
                            <button
                              key={col.id}
                              type="button"
                              onClick={() =>
                                addToCollectionMutation.mutate({
                                  collectionId: col.id,
                                  generationId: gen.id,
                                })
                              }
                              className="w-full text-left px-2 py-1.5 text-sm text-gray-200 hover:bg-gray-800 rounded"
                            >
                              {col.name}
                              <span className="text-gray-500 text-xs ml-1">({col.image_count ?? 0})</span>
                            </button>
                          ))}
                          <hr className="border-gray-700 my-1" />
                          {showNewCollectionInput ? (
                            <div className="flex gap-1">
                              <input
                                autoFocus
                                value={newCollectionName}
                                onChange={(event) => setNewCollectionName(event.target.value)}
                                onKeyDown={(event) => {
                                  if (event.key === 'Enter' && newCollectionName.trim()) {
                                    createAndAddMutation.mutate({
                                      name: newCollectionName.trim(),
                                      generationId: gen.id,
                                    })
                                  }
                                }}
                                placeholder="이름 입력..."
                                className="flex-1 bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-2 py-1"
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  if (newCollectionName.trim()) {
                                    createAndAddMutation.mutate({
                                      name: newCollectionName.trim(),
                                      generationId: gen.id,
                                    })
                                  }
                                }}
                                className="px-2 py-1 bg-violet-600 text-white text-xs rounded hover:bg-violet-500"
                              >
                                OK
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setShowNewCollectionInput(true)}
                              className="w-full text-left px-2 py-1.5 text-sm text-violet-400 hover:bg-gray-800 rounded"
                            >
                              + 새 콜렉션 만들기
                            </button>
                          )}
                          <hr className="border-gray-700 my-1" />
                          <Link
                            to="/collections"
                            onClick={() => setCollectionDropdownId(null)}
                            className="block px-2 py-1.5 text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800 rounded"
                          >
                            콜렉션 페이지 {'->'}
                          </Link>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {galleryData && galleryData.total_pages > 1 && (
              <div className="flex flex-wrap items-center justify-center gap-2 mt-4">
                <button
                  type="button"
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                  disabled={page <= 1}
                  className="px-3 py-1.5 bg-gray-800 text-gray-300 rounded-lg text-sm disabled:opacity-40"
                >
                  이전
                </button>
                <span className="text-gray-400 text-sm">
                  {page} / {galleryData.total_pages} (총 {galleryData.total}장)
                </span>
                <button
                  type="button"
                  onClick={() => setPage((value) => Math.min(galleryData.total_pages, value + 1))}
                  disabled={page >= galleryData.total_pages}
                  className="px-3 py-1.5 bg-gray-800 text-gray-300 rounded-lg text-sm disabled:opacity-40"
                >
                  다음
                </button>
              </div>
            )}
          </>
        )}
      </section>

      <section className="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h2 className="text-lg font-semibold text-gray-100 mb-3">갤러리 링크</h2>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/gallery?min_quality=0&max_quality=40"
            className="w-full px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm font-medium sm:w-auto"
          >
            갤러리에서 낮은 점수 이미지 보기
          </Link>
          <Link
            to="/gallery?search=finger_anomaly"
            className="w-full px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-200 rounded-lg text-sm font-medium sm:w-auto"
          >
            손 이상 감지 이미지 필터
          </Link>
        </div>
      </section>
    </div>
  )
}
