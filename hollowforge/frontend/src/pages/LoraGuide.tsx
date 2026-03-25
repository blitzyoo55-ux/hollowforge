import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getLoraGuide, getPromptTemplates } from '../api/client'
import type {
  CheckpointPromptTemplates,
  LoraGuideCheckpointFit,
  LoraGuideEntry,
  PromptTemplate,
} from '../api/client'

type RankedLora = LoraGuideEntry & {
  activeFit?: LoraGuideCheckpointFit
}

type SortMode = 'fit' | 'usage' | 'name'

const CATEGORY_BADGE: Record<string, string> = {
  style: 'bg-blue-600/20 text-blue-300 border border-blue-500/40',
  eyes: 'bg-emerald-600/20 text-emerald-300 border border-emerald-500/40',
  material: 'bg-amber-600/20 text-amber-300 border border-amber-500/40',
  fetish: 'bg-pink-600/20 text-pink-300 border border-pink-500/40',
}

function formatSigned(value: number | null, digits = 2): string {
  if (value === null) return '-'
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}`
}

function formatDecimal(value: number | null, digits = 2): string {
  if (value === null) return '-'
  return value.toFixed(digits)
}

function findTemplateById(templates: PromptTemplate[], templateId: string): PromptTemplate | undefined {
  return templates.find((tpl) => tpl.id === templateId)
}

export default function LoraGuide() {
  const navigate = useNavigate()
  const [selectedCheckpoint, setSelectedCheckpoint] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [showAll, setShowAll] = useState(false)
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [sortMode, setSortMode] = useState<SortMode>('fit')
  const [historyOnly, setHistoryOnly] = useState(false)
  const [showReasons, setShowReasons] = useState(false)
  const [refreshTick, setRefreshTick] = useState(0)

  const debouncedSearch = useDebounce(searchInput, 220)
  const forceRefresh = refreshTick > 0

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: ['lora-guide', refreshTick],
    queryFn: () => getLoraGuide({ refresh: forceRefresh }),
    staleTime: 90_000,
  })

  const { data: promptTemplateData } = useQuery({
    queryKey: ['prompt-templates'],
    queryFn: getPromptTemplates,
    staleTime: 120_000,
  })

  const activeCheckpoint =
    data?.checkpoints.some((cp) => cp.name === selectedCheckpoint)
      ? selectedCheckpoint
      : (data?.active_checkpoint ?? data?.checkpoints[0]?.name ?? '')
  const activeCheckpointInfo = useMemo(
    () => data?.checkpoints.find((cp) => cp.name === activeCheckpoint),
    [data, activeCheckpoint],
  )
  const activePromptTemplates: CheckpointPromptTemplates | undefined =
    activeCheckpoint ? promptTemplateData?.templates?.[activeCheckpoint] : undefined

  const availableCategories = useMemo(() => {
    if (!data) return []
    const set = new Set(data.loras.map((lora) => lora.category))
    return Array.from(set).sort()
  }, [data])

  const rankedLoras = useMemo<RankedLora[]>(() => {
    if (!data || !activeCheckpoint) return []
    const query = debouncedSearch.trim().toLowerCase()

    const filtered = data.loras
      .filter((lora) => lora.compatible_checkpoints.includes(activeCheckpoint))
      .filter((lora) => (categoryFilter === 'all' ? true : lora.category === categoryFilter))
      .filter((lora) => {
        if (!historyOnly) return true
        return lora.usage.total_runs > 0
      })
      .filter((lora) => {
        if (!query) return true
        return (
          lora.display_name.toLowerCase().includes(query) ||
          lora.filename.toLowerCase().includes(query) ||
          lora.category.toLowerCase().includes(query)
        )
      })
      .map((lora) => ({
        ...lora,
        activeFit: lora.checkpoint_fits.find((fit) => fit.checkpoint === activeCheckpoint),
      }))

    filtered.sort((a, b) => {
      if (sortMode === 'usage') {
        const usageGap = b.usage.total_runs - a.usage.total_runs
        if (usageGap !== 0) return usageGap
      } else if (sortMode === 'name') {
        const nameGap = a.display_name.localeCompare(b.display_name)
        if (nameGap !== 0) return nameGap
      } else {
        const scoreGap = (b.activeFit?.score ?? 0) - (a.activeFit?.score ?? 0)
        if (Math.abs(scoreGap) > 0.01) return scoreGap
      }

      const fitRunsGap = (b.activeFit?.runs ?? 0) - (a.activeFit?.runs ?? 0)
      if (fitRunsGap !== 0) return fitRunsGap
      return a.display_name.localeCompare(b.display_name)
    })

    return filtered
  }, [data, activeCheckpoint, debouncedSearch, categoryFilter, sortMode, historyOnly])

  const visibleLoras = useMemo(
    () => (showAll ? rankedLoras : rankedLoras.slice(0, 20)),
    [rankedLoras, showAll],
  )

  const completedGenerationTotal = useMemo(
    () => data?.checkpoints.reduce((sum, cp) => sum + cp.completed_generations, 0) ?? 0,
    [data],
  )

  const negativeCandidates = useMemo(
    () =>
      rankedLoras
        .filter((lora) => lora.usage.negative_runs > 0 || lora.category === 'material' || lora.category === 'fetish')
        .slice(0, 8),
    [rankedLoras],
  )

  const generatedAtLabel = data?.generated_at
    ? new Date(data.generated_at).toLocaleString()
    : '-'

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">LoRA Guide</h2>
          <p className="text-sm text-gray-400 mt-1">Loading compatibility and strength research...</p>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, idx) => (
            <div key={idx} className="h-40 rounded-xl border border-gray-800 bg-gray-900 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold text-gray-100">LoRA Guide</h2>
        <div className="bg-gray-900 rounded-xl border border-red-700/50 p-6 text-sm text-red-300">
          Guide data load failed. Check backend status and try again.
          <div className="mt-4">
            <button
              type="button"
              onClick={() => setRefreshTick((v) => v + 1)}
              className="px-4 py-2 rounded-lg bg-red-600/20 border border-red-500/50 text-red-200 hover:bg-red-600/30 transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">LoRA Guide</h2>
          <p className="text-sm text-gray-400 mt-1">
            체크포인트-로라 상성, 강도 변화, 실출력 예시를 한 화면에서 튜닝할 수 있도록 최적화했습니다.
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Updated: <span className="text-gray-300">{generatedAtLabel}</span>
            {' · '}
            Cache: <span className="text-gray-300">{data.cache?.hit ? 'HIT' : 'MISS'}</span>
            {' · '}
            TTL: <span className="text-gray-300">{data.cache?.ttl_sec ?? 0}s</span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => setRefreshTick((v) => v + 1)}
          className="px-3 py-2 rounded-lg border border-gray-700 bg-gray-900 text-sm text-gray-200 hover:bg-gray-800 transition-colors"
          disabled={isFetching}
        >
          {isFetching ? 'Refreshing...' : 'Hard Refresh Guide'}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <p className="text-xs text-gray-500">Recommended Max |strength|</p>
          <p className="text-2xl font-semibold text-violet-300 mt-1">{data.max_total_strength.toFixed(1)}</p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <p className="text-xs text-gray-500">Checkpoints Indexed</p>
          <p className="text-2xl font-semibold text-gray-100 mt-1">{data.checkpoints.length}</p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <p className="text-xs text-gray-500">LoRAs Profiled</p>
          <p className="text-2xl font-semibold text-gray-100 mt-1">{data.loras.length}</p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-4">
          <p className="text-xs text-gray-500">Completed Generations (sampled)</p>
          <p className="text-2xl font-semibold text-gray-100 mt-1">{completedGenerationTotal}</p>
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-400 block mb-1">Checkpoint</label>
            <select
              value={activeCheckpoint}
              onChange={(e) => {
                setSelectedCheckpoint(e.target.value)
                setShowAll(false)
              }}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            >
              {data.checkpoints.map((cp) => (
                <option key={cp.name} value={cp.name}>
                  {cp.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Search LoRA</label>
            <input
              type="text"
              value={searchInput}
              onChange={(e) => {
                setSearchInput(e.target.value)
                setShowAll(false)
              }}
              placeholder="Name, file, category..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Category</label>
            <select
              value={categoryFilter}
              onChange={(e) => {
                setCategoryFilter(e.target.value)
                setShowAll(false)
              }}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            >
              <option value="all">all categories</option>
              {availableCategories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-400 block mb-1">Sort</label>
            <select
              value={sortMode}
              onChange={(e) => setSortMode(e.target.value as SortMode)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            >
              <option value="fit">fit score</option>
              <option value="usage">usage volume</option>
              <option value="name">name</option>
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button
              type="button"
              onClick={() => {
                setHistoryOnly((v) => !v)
                setShowAll(false)
              }}
              className={`px-3 py-2 rounded-lg border text-sm transition-colors ${
                historyOnly
                  ? 'bg-violet-600/20 border-violet-500/50 text-violet-200'
                  : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'
              }`}
            >
              history only
            </button>
            <button
              type="button"
              onClick={() => setShowReasons((v) => !v)}
              className={`px-3 py-2 rounded-lg border text-sm transition-colors ${
                showReasons
                  ? 'bg-violet-600/20 border-violet-500/50 text-violet-200'
                  : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700'
              }`}
            >
              reason detail
            </button>
          </div>
        </div>

        <div className="text-xs text-gray-400">
          {activeCheckpointInfo ? (
            <>
              Active architecture: <span className="text-gray-200">{activeCheckpointInfo.architecture}</span>
              {' · '}
              Local completed runs: <span className="text-gray-200">{activeCheckpointInfo.completed_generations}</span>
              {' · '}
              Filtered LoRAs: <span className="text-gray-200">{rankedLoras.length}</span>
            </>
          ) : (
            'Select a checkpoint to review compatible LoRAs.'
          )}
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-3">
        <h3 className="text-lg font-semibold text-gray-100">Model Prompt Strategy</h3>
        <p className="text-xs text-gray-400">
          체크포인트 아키텍처에 따라 프롬프트 해석 방식이 다릅니다. 같은 문장이라도 SDXL/SD1.5/FLUX에서 결과가 달라지므로,
          모델별 템플릿을 기준으로 시작한 뒤 필요한 부분만 편집하는 방식이 가장 안정적입니다.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
            <p className="text-gray-200 font-medium">Why It Matters</p>
            <p className="text-gray-400 mt-1">
              같은 LoRA 조합이라도 프롬프트 구조가 맞지 않으면 인물/재질/구도가 불안정해지고 재현성이 떨어집니다.
            </p>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
            <p className="text-gray-200 font-medium">Correct Flow</p>
            <p className="text-gray-400 mt-1">
              1) 체크포인트 선택 2) 모델 템플릿 적용 3) LoRA 강도 조절 4) 생성 결과 기준으로 프롬프트를 미세 수정합니다.
            </p>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
            <p className="text-gray-200 font-medium">Editing Rule</p>
            <p className="text-gray-400 mt-1">
              핵심 구도/피사체는 앞쪽, 스타일/재질은 뒤쪽에 두면 충돌이 줄어듭니다. 부정 프롬프트는 과도하게 길지 않게 유지합니다.
            </p>
          </div>
        </div>

        {activePromptTemplates && (
          <div className="rounded-lg border border-cyan-700/40 bg-cyan-900/10 p-4 space-y-3">
            <p className="text-sm text-cyan-200 font-medium">
              Active Checkpoint Template ({activePromptTemplates.architecture})
            </p>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
              <div className="rounded-md border border-cyan-800/50 bg-gray-950/70 p-3">
                <p className="text-xs text-cyan-300 mb-1">Recommended Positive</p>
                <p className="text-xs text-gray-300 font-medium">
                  {findTemplateById(
                    activePromptTemplates.positive_templates,
                    activePromptTemplates.default_positive_template_id,
                  )?.name ?? '-'}
                </p>
                <p className="text-[11px] text-gray-400 mt-1 font-mono break-all">
                  {findTemplateById(
                    activePromptTemplates.positive_templates,
                    activePromptTemplates.default_positive_template_id,
                  )?.text ?? '-'}
                </p>
              </div>
              <div className="rounded-md border border-cyan-800/50 bg-gray-950/70 p-3">
                <p className="text-xs text-cyan-300 mb-1">Recommended Negative</p>
                <p className="text-xs text-gray-300 font-medium">
                  {findTemplateById(
                    activePromptTemplates.negative_templates,
                    activePromptTemplates.default_negative_template_id,
                  )?.name ?? '-'}
                </p>
                <p className="text-[11px] text-gray-400 mt-1 font-mono break-all">
                  {findTemplateById(
                    activePromptTemplates.negative_templates,
                    activePromptTemplates.default_negative_template_id,
                  )?.text ?? '-'}
                </p>
              </div>
            </div>
            <div className="space-y-1">
              {activePromptTemplates.guidance.map((line) => (
                <p key={line} className="text-[11px] text-cyan-200/80">
                  - {line}
                </p>
              ))}
            </div>
            <p className="text-[11px] text-cyan-200/90">
              Tokens: {promptTemplateData?.variables.map((item) => `${item.token}=${item.example}`).join(' · ')}
            </p>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-3">
        <h3 className="text-lg font-semibold text-gray-100">Negative Strength Playbook (-)</h3>
        <p className="text-xs text-gray-400">
          과적용된 스타일/소재를 눌러야 할 때 음수 강도를 사용합니다. 보통
          <span className="text-gray-200 font-mono"> -0.15 ~ -0.30 </span>
          에서 시작해 단계적으로 내리는 방식이 안정적입니다.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {negativeCandidates.map((lora) => (
            <div key={`neg-${lora.filename}`} className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
              <p className="text-sm text-gray-100 truncate">{lora.display_name}</p>
              <p className="text-[11px] text-gray-500 font-mono mt-0.5">{lora.filename}</p>
              <div className="flex items-center justify-between mt-2 text-xs">
                <span className={`px-2 py-0.5 rounded ${CATEGORY_BADGE[lora.category] ?? 'bg-gray-700 text-gray-300 border border-gray-600'}`}>
                  {lora.category}
                </span>
                <span className="text-gray-400">{lora.usage.negative_runs} negative runs</span>
              </div>
              <div className="mt-2 text-xs text-gray-400">
                Start <span className="text-gray-200 font-mono">{formatSigned(lora.strength.reverse_start)}</span>
                {' · '}
                Limit <span className="text-gray-200 font-mono">{formatSigned(lora.strength.reverse_limit)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-100">Checkpoint-Compatible LoRAs</h3>
          {rankedLoras.length > 20 && (
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="text-xs px-3 py-1.5 rounded-lg border border-gray-700 text-gray-300 hover:bg-gray-800 transition-colors"
            >
              {showAll ? 'Show Top 20' : `Show All (${rankedLoras.length})`}
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
          {visibleLoras.map((lora) => (
            <div key={lora.filename} className="rounded-lg border border-gray-800 bg-gray-950/60 p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-gray-100">{lora.display_name}</p>
                  <p className="text-[11px] text-gray-500 font-mono mt-0.5">{lora.filename}</p>
                </div>
                <span className={`text-[11px] px-2 py-0.5 rounded ${CATEGORY_BADGE[lora.category] ?? 'bg-gray-700 text-gray-300 border border-gray-600'}`}>
                  {lora.category}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-md border border-gray-800 bg-gray-900 px-2 py-1.5">
                  <p className="text-gray-500">Architecture</p>
                  <p className="text-gray-200 mt-0.5">{lora.architecture}</p>
                </div>
                <div className="rounded-md border border-gray-800 bg-gray-900 px-2 py-1.5">
                  <p className="text-gray-500">Fit Score</p>
                  <p className="text-gray-200 mt-0.5">{formatDecimal(lora.activeFit?.score ?? null, 1)}</p>
                </div>
                <div className="rounded-md border border-gray-800 bg-gray-900 px-2 py-1.5">
                  <p className="text-gray-500">Runs ({activeCheckpoint})</p>
                  <p className="text-gray-200 mt-0.5">{lora.activeFit?.runs ?? 0}</p>
                </div>
                <div className="rounded-md border border-gray-800 bg-gray-900 px-2 py-1.5">
                  <p className="text-gray-500">Avg Strength</p>
                  <p className="text-gray-200 mt-0.5">{formatSigned(lora.activeFit?.avg_strength ?? null)}</p>
                </div>
              </div>

              <div className="rounded-md border border-violet-500/30 bg-violet-600/10 p-3 text-xs">
                <p className="text-violet-300 font-medium">Recommended Strength Window</p>
                <p className="text-gray-200 mt-1 font-mono">
                  +{lora.strength.low.toFixed(2)} ~ +{lora.strength.high.toFixed(2)}
                  {' · '}
                  base +{lora.strength.base.toFixed(2)}
                </p>
                <p className="text-gray-400 mt-1 font-mono">
                  reverse start {formatSigned(lora.strength.reverse_start)} / limit {formatSigned(lora.strength.reverse_limit)}
                </p>
              </div>

              <div className="text-xs text-gray-400 space-y-1">
                <p><span className="text-gray-500">Raise:</span> {lora.raise_effect}</p>
                <p><span className="text-gray-500">Lower:</span> {lora.lower_effect}</p>
              </div>

              {showReasons && (
                <div className="space-y-1">
                  {(lora.activeFit?.reasons ?? ['No checkpoint-specific rationale available']).map((reason, idx) => (
                    <p key={`${lora.filename}-reason-${idx}`} className="text-[11px] text-gray-400">
                      - {reason}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-4">
        <h3 className="text-lg font-semibold text-gray-100">Total |strength| by Real Outputs</h3>
        <p className="text-xs text-gray-400">
          실제 생성 이력을 구간별로 매칭한 카드입니다. 이미지를 클릭하면 Gallery 상세로 바로 이동합니다.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {data.strength_examples.map((example) => (
            <div key={example.bucket_id} className="rounded-lg border border-gray-800 bg-gray-950/60 overflow-hidden">
              <div className="px-3 py-2 border-b border-gray-800">
                <p className="text-sm text-gray-100">{example.label}</p>
                <p className="text-[11px] text-gray-500 mt-0.5">{example.guidance}</p>
              </div>

              {example.thumbnail_path ? (
                <button
                  type="button"
                  onClick={() => {
                    if (example.generation_id) {
                      navigate(`/gallery/${example.generation_id}`)
                    }
                  }}
                  className="block w-full text-left"
                >
                  <img
                    src={`/data/${example.thumbnail_path}`}
                    alt={example.prompt ?? example.label}
                    loading="lazy"
                    className="w-full aspect-[3/4] object-cover hover:opacity-90 transition-opacity"
                  />
                </button>
              ) : (
                <div className="w-full aspect-[3/4] flex items-center justify-center text-gray-600 text-xs">
                  No sampled image in this range yet
                </div>
              )}

              <div className="px-3 py-2 space-y-1 text-xs">
                <p className="text-gray-400">
                  Checkpoint: <span className="text-gray-200">{example.checkpoint ?? '-'}</span>
                </p>
                <p className="text-gray-400">
                  Total |strength|: <span className="text-gray-200 font-mono">{formatDecimal(example.total_abs_strength)}</span>
                </p>
                {example.loras.length > 0 && (
                  <p className="text-gray-500 truncate">
                    {example.loras.slice(0, 3).map((lora) => `${lora.filename} (${formatSigned(lora.strength)})`).join(', ')}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function useDebounce(value: string, delay: number): string {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const handler = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(handler)
  }, [value, delay])

  return debounced
}
