import { useState, useCallback, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  createGeneration,
  createGenerationBatch,
  createPreset,
  getGeneration,
  getPresets,
} from '../api/client'
import type { GenerationCreate, GenerationResponse, PresetResponse } from '../api/client'
import GenerateForm from '../components/GenerateForm'
import type { GenerateSubmitPayload } from '../components/GenerateForm'
import ProgressCard from '../components/ProgressCard'

export default function Generate() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [generatingId, setGeneratingId] = useState<string | null>(null)
  const [pendingBatchIds, setPendingBatchIds] = useState<string[]>([])
  const [batchTotal, setBatchTotal] = useState(0)
  const [batchCompleted, setBatchCompleted] = useState(0)
  const [batchFailed, setBatchFailed] = useState(0)
  const [batchSeedRange, setBatchSeedRange] = useState<{ start: number; end: number } | null>(null)
  const [lastResult, setLastResult] = useState<GenerationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [presetInitial, setPresetInitial] = useState<Partial<GenerationCreate> | undefined>(undefined)
  const fromGenerationId = searchParams.get('from')

  const { data: presets } = useQuery({
    queryKey: ['presets'],
    queryFn: getPresets,
  })

  const { data: sourceGeneration, isError: sourceGenerationError } = useQuery({
    queryKey: ['generation-source', fromGenerationId],
    queryFn: () => getGeneration(fromGenerationId!),
    enabled: !!fromGenerationId,
  })

  // Auto-load preset from query param
  useEffect(() => {
    if (fromGenerationId) return
    const presetId = searchParams.get('preset')
    if (!presetId) {
      setPresetInitial(undefined)
      return
    }
    if (presetId && presets) {
      const preset = presets.find((p: PresetResponse) => p.id === presetId)
      if (preset) {
        const params = preset.default_params ?? {}
        setPresetInitial({
          prompt: preset.prompt_template ?? '',
          negative_prompt: preset.negative_prompt,
          checkpoint: preset.checkpoint,
          loras: preset.loras,
          steps: (params.steps as number) ?? 28,
          cfg: (params.cfg as number) ?? 7.0,
          width: (params.width as number) ?? 832,
          height: (params.height as number) ?? 1216,
          sampler: (params.sampler as string) ?? 'euler',
          scheduler: (params.scheduler as string) ?? 'normal',
          clip_skip: (params.clip_skip as number) ?? null,
          tags: preset.tags ?? undefined,
          preset_id: preset.id,
        })
      } else {
        setPresetInitial(undefined)
      }
    }
  }, [searchParams, presets, fromGenerationId])

  const generateMutation = useMutation({
    mutationFn: async (payload: GenerateSubmitPayload) => {
      if (payload.batchCount > 1) {
        return {
          type: 'batch' as const,
          data: await createGenerationBatch({
            generation: payload.generation,
            count: payload.batchCount,
            seed_increment: 1,
          }),
        }
      }
      return {
        type: 'single' as const,
        data: await createGeneration(payload.generation),
      }
    },
    onSuccess: (data) => {
      setError(null)
      if (data.type === 'single') {
        setGeneratingId(data.data.id)
        setPendingBatchIds([])
        setBatchTotal(1)
        setBatchCompleted(0)
        setBatchFailed(0)
        setBatchSeedRange({ start: data.data.seed, end: data.data.seed })
        return
      }

      const ids = data.data.generations.map((g) => g.id)
      setGeneratingId(ids[0] ?? null)
      setPendingBatchIds(ids.slice(1))
      setBatchTotal(data.data.count)
      setBatchCompleted(0)
      setBatchFailed(0)
      setBatchSeedRange({
        start: data.data.base_seed,
        end: data.data.base_seed + ((data.data.count - 1) * data.data.seed_increment),
      })
    },
    onError: (err) => {
      setGeneratingId(null)
      setPendingBatchIds([])
      setBatchTotal(0)
      setBatchCompleted(0)
      setBatchFailed(0)
      setBatchSeedRange(null)
      if (axios.isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
        setError(err.response.data.detail)
        return
      }
      setError('Failed to start generation. Is the backend running?')
    },
  })

  const advanceBatchQueue = useCallback(() => {
    setPendingBatchIds((prev) => {
      if (prev.length === 0) {
        setGeneratingId(null)
        return prev
      }
      const [next, ...rest] = prev
      setGeneratingId(next)
      return rest
    })
  }, [])

  const presetMutation = useMutation({
    mutationFn: (data: GenerationCreate) =>
      createPreset({
        name: `Preset ${new Date().toISOString().slice(0, 16)}`,
        checkpoint: data.checkpoint,
        loras: data.loras ?? [],
        prompt_template: data.prompt,
        negative_prompt: data.negative_prompt ?? undefined,
        default_params: {
          steps: data.steps,
          cfg: data.cfg,
          width: data.width,
          height: data.height,
          sampler: data.sampler,
          scheduler: data.scheduler,
          clip_skip: data.clip_skip,
        },
        tags: data.tags ?? undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['presets'] })
    },
  })

  const handleComplete = useCallback((gen: GenerationResponse) => {
    setLastResult(gen)
    setBatchCompleted((prev) => prev + 1)
    queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
    queryClient.invalidateQueries({ queryKey: ['system-health'] })
    advanceBatchQueue()
  }, [advanceBatchQueue, queryClient])

  const handleError = useCallback((msg: string, gen?: GenerationResponse) => {
    setError(msg)
    if (gen) {
      setLastResult(gen)
      setBatchFailed((prev) => prev + 1)
      queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
      queryClient.invalidateQueries({ queryKey: ['system-health'] })
      advanceBatchQueue()
      return
    }

    setGeneratingId(null)
    setPendingBatchIds([])
    setBatchTotal(0)
    setBatchCompleted(0)
    setBatchFailed(0)
    setBatchSeedRange(null)
  }, [advanceBatchQueue, queryClient])

  const batchProcessed = batchCompleted + batchFailed

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Generate</h2>
        <p className="text-sm text-gray-400 mt-1">Create a new image with ComfyUI</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Form - left 2/3 */}
        <div className="lg:col-span-2">
          {sourceGenerationError && (
            <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4 mb-4">
              <p className="text-sm text-red-400">Failed to load source generation from URL parameter.</p>
            </div>
          )}
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <GenerateForm
              key={sourceGeneration?.id ?? (presetInitial ? JSON.stringify(presetInitial) : 'default')}
              initialValues={presetInitial}
              initialData={sourceGeneration ?? null}
              onSubmit={(payload) => generateMutation.mutate(payload)}
              isSubmitting={generateMutation.isPending}
              onSavePreset={(data) => presetMutation.mutate(data)}
            />
          </div>
        </div>

        {/* Right panel - 1/3 */}
        <div className="space-y-4">
          {batchTotal > 1 && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 space-y-1.5">
              <p className="text-sm text-gray-200 font-medium">Batch Queue</p>
              <p className="text-xs text-gray-400">
                Processed: <span className="font-mono">{batchProcessed}/{batchTotal}</span>{' '}
                | Failed: <span className="font-mono">{batchFailed}</span>
              </p>
              <p className="text-xs text-gray-500">
                Remaining queue: <span className="font-mono">{pendingBatchIds.length}</span>
              </p>
              {batchSeedRange && (
                <p className="text-xs text-gray-500">
                  Seed range: <span className="font-mono">{batchSeedRange.start} ~ {batchSeedRange.end}</span>
                </p>
              )}
            </div>
          )}

          {error && (
            <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
              <p className="text-sm font-medium text-red-400">Generation failed</p>
              <p className="text-xs text-red-400/80 mt-1 whitespace-pre-wrap break-words max-h-32 overflow-y-auto">{error}</p>
              <button
                onClick={() => setError(null)}
                className="text-xs text-red-500 hover:text-red-400 mt-2 transition-colors duration-200"
              >
                Dismiss
              </button>
            </div>
          )}

          {presetMutation.isSuccess && (
            <div className="bg-green-900/20 border border-green-800/50 rounded-xl p-4">
              <p className="text-sm text-green-400">Preset saved successfully!</p>
            </div>
          )}

          {generatingId ? (
            <ProgressCard
              generationId={generatingId}
              onComplete={handleComplete}
              onError={handleError}
            />
          ) : lastResult ? (
            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
              {lastResult.thumbnail_path && (
                <img
                  src={`/data/${lastResult.thumbnail_path}`}
                  alt="Last generated"
                  className="w-full aspect-[3/4] object-cover"
                />
              )}
              <div className="p-4 space-y-2">
                <p className="text-sm text-gray-300 line-clamp-2">{lastResult.prompt}</p>
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <span className="font-mono">seed: {lastResult.seed}</span>
                  {lastResult.generation_time_sec != null && (
                    <span className="font-mono">{lastResult.generation_time_sec.toFixed(1)}s</span>
                  )}
                </div>
                <button
                  onClick={() => navigate(`/gallery/${lastResult.id}`)}
                  className="w-full bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-3 py-2 text-sm transition-colors duration-200"
                >
                  View Details
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 text-center">
              <svg className="w-12 h-12 mx-auto text-gray-700 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
              </svg>
              <p className="text-sm text-gray-500">Preview will appear here</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
