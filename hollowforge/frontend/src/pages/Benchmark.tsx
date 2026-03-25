import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { toast } from 'sonner'
import {
  createBenchmark,
  deleteBenchmark,
  getBenchmark,
  getModels,
  listBenchmarks,
} from '../api/client'
import type {
  BenchmarkCreate,
  BenchmarkResponse,
  GenerationResponse,
  LoraInput,
} from '../api/client'
import LoraSelector from '../components/LoraSelector'
import { DEFAULT_NEGATIVE_PROMPT } from '../lib/defaultPrompts'

type BenchmarkGenerationLike = Partial<GenerationResponse> & {
  id: string
  status: string
}

const STATUS_CLASS: Record<string, string> = {
  pending: 'bg-gray-700/70 text-gray-200 border-gray-600',
  running: 'bg-blue-900/40 text-blue-300 border-blue-700/50',
  completed: 'bg-green-900/40 text-green-300 border-green-700/50',
  failed: 'bg-red-900/40 text-red-300 border-red-700/50',
  queued: 'bg-gray-700/70 text-gray-200 border-gray-600',
  cancelled: 'bg-amber-900/40 text-amber-300 border-amber-700/50',
}

function toneForStatus(status: string): string {
  return STATUS_CLASS[status] ?? 'bg-gray-700/70 text-gray-200 border-gray-600'
}

function formatDateTime(value: string | null): string {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }
  return fallback
}

function normalizeSeed(seedInput: string): number | null {
  const trimmed = seedInput.trim()
  if (!trimmed) return null
  const parsed = Number.parseInt(trimmed, 10)
  if (!Number.isFinite(parsed)) return null
  return parsed
}

export default function Benchmark() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [name, setName] = useState('')
  const [prompt, setPrompt] = useState('')
  const [negativePrompt, setNegativePrompt] = useState(DEFAULT_NEGATIVE_PROMPT)
  const [selectedCheckpoints, setSelectedCheckpoints] = useState<string[]>([])
  const [loras, setLoras] = useState<LoraInput[]>([])
  const [steps, setSteps] = useState(28)
  const [cfg, setCfg] = useState(7)
  const [width, setWidth] = useState(832)
  const [height, setHeight] = useState(1216)
  const [sampler, setSampler] = useState('euler')
  const [scheduler, setScheduler] = useState('normal')
  const [seedInput, setSeedInput] = useState('')
  const [activeJobId, setActiveJobId] = useState<string | null>(null)

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: getModels,
    staleTime: 60_000,
  })

  const { data: benchmarks = [], isLoading: listLoading, isError: listError } = useQuery({
    queryKey: ['benchmarks'],
    queryFn: listBenchmarks,
    refetchInterval: (query) => {
      const items = query.state.data as BenchmarkResponse[] | undefined
      if (!items || items.length === 0) return false
      return items.some((item) => item.status === 'pending' || item.status === 'running')
        ? 5000
        : false
    },
  })

  const detailQuery = useQuery({
    queryKey: ['benchmark', activeJobId],
    queryFn: () => getBenchmark(activeJobId as string),
    enabled: !!activeJobId,
    refetchInterval: (query) => {
      const item = query.state.data as BenchmarkResponse | undefined
      if (!item) return 5000
      return item.status === 'pending' || item.status === 'running' ? 4000 : false
    },
  })

  const createMutation = useMutation({
    mutationFn: (payload: BenchmarkCreate) => createBenchmark(payload),
    onSuccess: async (job) => {
      toast.success('Benchmark queued')
      setActiveJobId(job.id)
      await queryClient.invalidateQueries({ queryKey: ['benchmarks'] })
      await queryClient.invalidateQueries({ queryKey: ['benchmark', job.id] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to start benchmark'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => deleteBenchmark(jobId),
    onSuccess: async (_, jobId) => {
      toast.success('Benchmark deleted')
      if (activeJobId === jobId) {
        setActiveJobId(null)
      }
      await queryClient.invalidateQueries({ queryKey: ['benchmarks'] })
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to delete benchmark'))
    },
  })

  const checkpointOptions = models?.checkpoints ?? []
  const samplerOptions = models?.samplers ?? ['euler']
  const schedulerOptions = models?.schedulers ?? ['normal']

  const primaryCheckpoint = selectedCheckpoints[0] ?? ''

  const detailRows = useMemo(() => {
    const detail = detailQuery.data
    if (!detail) return []

    const generations = (detail.generations ?? []) as BenchmarkGenerationLike[]
    const byId = new Map(generations.map((item) => [item.id, item]))

    return detail.checkpoints.map((checkpoint, idx) => {
      const generationId = detail.generation_ids[idx]
      return {
        checkpoint,
        generationId,
        generation: generationId ? byId.get(generationId) : undefined,
      }
    })
  }, [detailQuery.data])

  const toggleCheckpoint = (checkpoint: string) => {
    setSelectedCheckpoints((prev) => {
      if (prev.includes(checkpoint)) {
        return prev.filter((item) => item !== checkpoint)
      }
      if (prev.length >= 10) {
        toast.error('최대 10개의 체크포인트만 선택할 수 있습니다')
        return prev
      }
      return [...prev, checkpoint]
    })
  }

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()

    if (!name.trim()) {
      toast.error('Benchmark name을 입력하세요')
      return
    }
    if (!prompt.trim()) {
      toast.error('Prompt를 입력하세요')
      return
    }
    if (selectedCheckpoints.length < 2) {
      toast.error('체크포인트를 최소 2개 선택하세요')
      return
    }
    if (selectedCheckpoints.length > 10) {
      toast.error('체크포인트는 최대 10개까지 허용됩니다')
      return
    }
    if (width % 8 !== 0 || height % 8 !== 0) {
      toast.error('Width/Height는 8의 배수여야 합니다')
      return
    }

    const normalizedSeed = normalizeSeed(seedInput)

    createMutation.mutate({
      name: name.trim(),
      prompt: prompt.trim(),
      negative_prompt: negativePrompt.trim() ? negativePrompt.trim() : null,
      loras,
      steps,
      cfg,
      width,
      height,
      sampler,
      scheduler,
      seed: normalizedSeed,
      checkpoints: selectedCheckpoints,
    })
  }

  const activeDetail = detailQuery.data

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Benchmark</h2>
        <p className="text-sm text-gray-400 mt-1">Run one prompt across multiple checkpoints for side-by-side comparison</p>
      </div>

      <section className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-800 flex items-center justify-between gap-3">
          <h3 className="text-base font-semibold text-gray-100">Benchmark Jobs</h3>
          <span className="text-xs text-gray-500">Latest first</span>
        </div>

        {listLoading ? (
          <div className="p-5 text-sm text-gray-400">Loading benchmark jobs...</div>
        ) : listError ? (
          <div className="p-5 text-sm text-red-300">Failed to load benchmark jobs</div>
        ) : benchmarks.length === 0 ? (
          <div className="p-5 text-sm text-gray-500">아직 실행된 benchmark가 없습니다.</div>
        ) : (
          <div className="divide-y divide-gray-800">
            {benchmarks.map((job) => (
              <div
                key={job.id}
                className={`p-4 transition-colors ${
                  activeJobId === job.id ? 'bg-violet-600/10' : 'hover:bg-gray-800/40'
                }`}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <button
                    type="button"
                    onClick={() => setActiveJobId((prev) => (prev === job.id ? null : job.id))}
                    className="text-left flex-1 min-w-0"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-medium text-gray-100 truncate">{job.name}</p>
                      <span className={`text-[11px] px-2 py-0.5 rounded border ${toneForStatus(job.status)}`}>
                        {job.status}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-gray-500 flex flex-wrap gap-x-3 gap-y-1">
                      <span>{job.checkpoints.length} checkpoints</span>
                      <span>{formatDateTime(job.created_at)}</span>
                      <span className="font-mono">seed {job.seed ?? '-'}</span>
                    </div>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (!window.confirm(`Delete benchmark "${job.name}"?`)) return
                      deleteMutation.mutate(job.id)
                    }}
                    disabled={deleteMutation.isPending}
                    className="self-start sm:self-auto text-xs px-3 py-1.5 rounded-lg border border-red-800/70 bg-red-900/20 text-red-300 hover:bg-red-900/40 disabled:opacity-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <h3 className="text-lg font-semibold text-gray-100 mb-4">New Benchmark</h3>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Name</label>
              <input
                type="text"
                maxLength={120}
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Seed (optional)</label>
              <input
                type="number"
                min={-1}
                max={2147483647}
                value={seedInput}
                onChange={(e) => setSeedInput(e.target.value)}
                placeholder="leave empty for shared auto seed"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Prompt</label>
            <textarea
              rows={4}
              required
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Negative Prompt</label>
            <textarea
              rows={3}
              value={negativePrompt}
              onChange={(e) => setNegativePrompt(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
          </div>

          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <label className="text-sm font-medium text-gray-300">Checkpoints</label>
              <span className="text-xs text-gray-500">{selectedCheckpoints.length}/10 selected</span>
            </div>
            <div className="max-h-56 overflow-y-auto rounded-lg border border-gray-800 bg-gray-950/70 p-3 space-y-2">
              {checkpointOptions.length === 0 ? (
                <p className="text-sm text-gray-500">No checkpoints loaded</p>
              ) : (
                checkpointOptions.map((checkpoint) => {
                  const checked = selectedCheckpoints.includes(checkpoint)
                  return (
                    <label
                      key={checkpoint}
                      className={`flex items-center gap-2 p-2 rounded-md border text-sm transition-colors ${
                        checked
                          ? 'border-violet-600/60 bg-violet-600/10 text-violet-200'
                          : 'border-gray-800 bg-gray-900 text-gray-300 hover:bg-gray-800/70'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleCheckpoint(checkpoint)}
                        className="rounded border-gray-600 bg-gray-700 text-violet-500 focus:ring-violet-500 focus:ring-offset-0"
                      />
                      <span className="truncate" title={checkpoint}>{checkpoint}</span>
                    </label>
                  )
                })
              )}
            </div>
            <p className="mt-1 text-xs text-gray-500">최소 2개, 최대 10개 선택</p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Steps</label>
              <input
                type="number"
                min={1}
                max={150}
                value={steps}
                onChange={(e) => setSteps(Math.max(1, Math.min(150, Number(e.target.value) || 1)))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-2 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">CFG</label>
              <input
                type="number"
                min={1}
                max={30}
                step={0.1}
                value={cfg}
                onChange={(e) => setCfg(Math.max(1, Math.min(30, Number(e.target.value) || 1)))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-2 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Width</label>
              <input
                type="number"
                min={256}
                max={1536}
                step={8}
                value={width}
                onChange={(e) => setWidth(Math.max(256, Math.min(1536, Number(e.target.value) || 256)))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-2 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Height</label>
              <input
                type="number"
                min={256}
                max={1536}
                step={8}
                value={height}
                onChange={(e) => setHeight(Math.max(256, Math.min(1536, Number(e.target.value) || 256)))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-2 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Sampler</label>
              <select
                value={sampler}
                onChange={(e) => setSampler(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-2 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              >
                {samplerOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Scheduler</label>
              <select
                value={scheduler}
                onChange={(e) => setScheduler(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-2 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              >
                {schedulerOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="rounded-xl border border-gray-800 bg-gray-950/50 p-4">
            <LoraSelector
              selected={loras}
              onChange={setLoras}
              moods={[]}
              checkpoint={primaryCheckpoint}
            />
            {!primaryCheckpoint && (
              <p className="mt-2 text-xs text-gray-500">체크포인트를 선택하면 LoRA 호환 필터가 적용됩니다.</p>
            )}
          </div>

          <div className="flex items-center justify-end">
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-5 py-2 text-sm font-medium transition-colors duration-200"
            >
              {createMutation.isPending ? 'Running...' : 'Run Benchmark'}
            </button>
          </div>
        </form>
      </section>

      <section className="bg-gray-900 rounded-xl border border-gray-800 p-6">
        <div className="flex items-center justify-between gap-3 mb-4">
          <h3 className="text-lg font-semibold text-gray-100">Result Comparison</h3>
          {activeDetail && (
            <span className={`text-xs px-2 py-1 rounded border ${toneForStatus(activeDetail.status)}`}>
              {activeDetail.status}
            </span>
          )}
        </div>

        {!activeJobId ? (
          <p className="text-sm text-gray-500">상단 목록에서 benchmark를 선택하세요.</p>
        ) : detailQuery.isLoading ? (
          <p className="text-sm text-gray-400">Loading benchmark detail...</p>
        ) : detailQuery.isError || !activeDetail ? (
          <p className="text-sm text-red-300">Failed to load benchmark detail</p>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border border-gray-800 bg-gray-950/70 p-3">
              <p className="text-sm text-gray-200 font-medium">{activeDetail.name}</p>
              <p className="text-xs text-gray-500 mt-1">{activeDetail.prompt}</p>
              <p className="text-xs text-gray-500 mt-1">Created: {formatDateTime(activeDetail.created_at)}</p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {detailRows.map((row) => {
                const generation = row.generation
                const status = generation?.status ?? 'pending'
                const imagePath = generation?.image_path ?? generation?.thumbnail_path
                const generationTime = generation?.generation_time_sec
                const clickable = Boolean(generation?.id)

                return (
                  <div key={`${row.checkpoint}-${row.generationId ?? 'none'}`} className="rounded-xl border border-gray-800 bg-gray-950/70 overflow-hidden">
                    <div className="px-3 py-2 border-b border-gray-800 flex items-center justify-between gap-2">
                      <p className="text-xs text-gray-300 truncate" title={row.checkpoint}>{row.checkpoint}</p>
                      <span className={`text-[10px] px-2 py-0.5 rounded border ${toneForStatus(status)}`}>{status}</span>
                    </div>

                    {imagePath ? (
                      <button
                        type="button"
                        onClick={() => {
                          if (generation?.id) navigate(`/gallery/${generation.id}`)
                        }}
                        className="block w-full bg-black"
                        disabled={!clickable}
                      >
                        <img
                          src={`/data/${imagePath}`}
                          alt={row.checkpoint}
                          className="w-full aspect-[3/4] object-cover"
                        />
                      </button>
                    ) : (
                      <div className="w-full aspect-[3/4] grid place-items-center text-xs text-gray-500">
                        {status === 'failed' ? 'Generation failed' : 'Waiting for output...'}
                      </div>
                    )}

                    <div className="px-3 py-2 text-xs text-gray-500 space-y-1">
                      <p className="font-mono">gen_id: {row.generationId ?? '-'}</p>
                      <p>time: {generationTime != null ? `${generationTime.toFixed(1)}s` : '-'}</p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
