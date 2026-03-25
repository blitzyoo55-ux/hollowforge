import { useEffect, useRef, useState } from 'react'
import { isAxiosError } from 'axios'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  adetailGeneration,
  applyWatermark,
  addToCollection,
  getGeneration,
  getCollections,
  deleteGalleryItem,
  hiresfixGeneration,
  reproduceGeneration,
  createPreset,
  getUpscaleModels,
  toggleFavorite,
  toggleReadyToGo,
  upscaleGeneration,
} from '../api/client'
import type { GenerationResponse, UpscaleMode } from '../api/client'
import { notify } from '../lib/toast'
import CompareView from '../components/CompareView'
import DreamActorPanel from '../components/DreamActorPanel'
import LocalAnimationPanel from '../components/LocalAnimationPanel'

type CompareTargetType = 'upscale' | 'faceFix' | 'hiresfix'
type PostprocessKind = 'upscale' | 'adetail' | 'hiresfix'

interface CompareTargetOption {
  type: CompareTargetType
  dropdownLabel: string
  resultLabel: string
  path: string
}

const POSTPROCESS_LABELS: Record<PostprocessKind, string> = {
  upscale: '업스케일',
  adetail: 'Face Fix',
  hiresfix: 'Hires.fix',
}

function isPostprocessActive(status?: string | null): boolean {
  return status === 'queued' || status === 'running'
}

function didPostprocessSucceed(gen: GenerationResponse, kind: PostprocessKind): boolean {
  if (kind === 'upscale') return Boolean(gen.upscaled_image_path)
  if (kind === 'adetail') return Boolean(gen.adetailed_path)
  return Boolean(gen.hiresfix_path)
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  return fallback
}

export default function ImageDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedUpscaleModel, setSelectedUpscaleModel] = useState('remacri_original.safetensors')
  const [selectedCollectionId, setSelectedCollectionId] = useState('')
  const [hiresfixScaleFactor, setHiresfixScaleFactor] = useState(1.5)
  const [hiresfixDenoise, setHiresfixDenoise] = useState(0.5)
  const [showHiresfixAdvanced, setShowHiresfixAdvanced] = useState(false)
  const [selectedCompareTarget, setSelectedCompareTarget] = useState<CompareTargetType>('upscale')
  const [isCompareOpen, setIsCompareOpen] = useState(false)
  const queuedPostprocessKindRef = useRef<PostprocessKind | null>(null)

  const { data: gen, isLoading, isError } = useQuery({
    queryKey: ['generation', id],
    queryFn: () => getGeneration(id!),
    enabled: !!id,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      const data = query.state.data as GenerationResponse | undefined
      if (!data) return false
      if (data.status === 'queued' || data.status === 'running') return 2000
      return isPostprocessActive(data.postprocess_status) ? 2000 : false
    },
  })

  const { data: upscaleModelsData } = useQuery({
    queryKey: ['upscale-models', gen?.checkpoint ?? null],
    queryFn: () => getUpscaleModels(gen?.checkpoint ?? null),
  })

  const { data: collections } = useQuery({
    queryKey: ['collections', id],
    queryFn: () => getCollections(id),
    enabled: !!id,
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteGalleryItem(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      sessionStorage.setItem('hf_gallery_delete_toast', 'success')
      navigate('/gallery', { state: { deleteToast: 'success' } })
    },
    onError: () => {
      sessionStorage.setItem('hf_gallery_delete_toast', 'error')
      notify.error('이미지 삭제에 실패했습니다')
    },
  })

  const reproduceMutation = useMutation({
    mutationFn: (mode: 'exact' | 'variation') =>
      reproduceGeneration(id!, { mode }),
    onSuccess: (data) => {
      navigate(`/gallery/${data.id}`)
    },
  })

  const savePresetMutation = useMutation({
    mutationFn: () => {
      if (!gen) throw new Error('No generation data')
      return createPreset({
        name: `From ${gen.id.slice(0, 8)} - ${new Date().toISOString().slice(0, 10)}`,
        checkpoint: gen.checkpoint,
        loras: gen.loras,
        prompt_template: gen.prompt,
        negative_prompt: gen.negative_prompt ?? undefined,
        default_params: {
          steps: gen.steps,
          cfg: gen.cfg,
          width: gen.width,
          height: gen.height,
          sampler: gen.sampler,
          scheduler: gen.scheduler,
        },
        tags: gen.tags ?? undefined,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['presets'] })
    },
  })

  const upscaleMutation = useMutation({
    mutationFn: ({ model, mode }: { model: string; mode: UpscaleMode }) =>
      upscaleGeneration(id!, model, mode),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(['generation', id], data)
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      queuedPostprocessKindRef.current = 'upscale'
      notify.info(
        variables.mode === 'quality'
          ? '퀄리티 업스케일 작업을 큐에 추가했습니다'
          : '안전 업스케일 작업을 큐에 추가했습니다',
      )
    },
    onError: (error) => {
      notify.error(getApiErrorMessage(error, '업스케일 작업을 시작하지 못했습니다'))
    },
  })

  const adetailMutation = useMutation({
    mutationFn: () => adetailGeneration(id!, { denoise: 0.4, steps: 20 }),
    onSuccess: (data) => {
      queryClient.setQueryData(['generation', id], data)
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      queuedPostprocessKindRef.current = 'adetail'
      notify.info('Face Fix 작업을 큐에 추가했습니다')
    },
    onError: (error) => {
      notify.error(getApiErrorMessage(error, 'Face Fix 작업을 시작하지 못했습니다'))
    },
  })

  const hiresfixMutation = useMutation({
    mutationFn: () =>
      hiresfixGeneration(id!, {
        upscale_factor: hiresfixScaleFactor,
        denoise: hiresfixDenoise,
        steps: 20,
        cfg: 7.0,
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(['generation', id], data)
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      queuedPostprocessKindRef.current = 'hiresfix'
      notify.info('Hires.fix 작업을 큐에 추가했습니다')
    },
    onError: (error) => {
      notify.error(getApiErrorMessage(error, 'Hires.fix 작업을 시작하지 못했습니다'))
    },
  })

  const favoriteMutation = useMutation({
    mutationFn: () => toggleFavorite(id!),
    onSuccess: (data) => {
      queryClient.setQueryData(['generation', id], (prev: unknown) => {
        if (!prev || typeof prev !== 'object') return prev
        return { ...(prev as Record<string, unknown>), is_favorite: data.is_favorite }
      })
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
      queryClient.invalidateQueries({ queryKey: ['ready-gallery'] })
      queryClient.invalidateQueries({ queryKey: ['collections', id] })
    },
  })

  const readyMutation = useMutation({
    mutationFn: () => toggleReadyToGo(id!),
    onSuccess: (data) => {
      queryClient.setQueryData(['generation', id], (prev: unknown) => {
        if (!prev || typeof prev !== 'object') return prev
        return {
          ...(prev as Record<string, unknown>),
          publish_approved: data.publish_approved,
        }
      })
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
      queryClient.invalidateQueries({ queryKey: ['ready-gallery'] })
    },
  })

  const addToCollectionMutation = useMutation({
    mutationFn: (collectionId: string) => addToCollection(collectionId, id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['collections', id] })
      queryClient.invalidateQueries({ queryKey: ['collections'] })
      queryClient.invalidateQueries({ queryKey: ['collection'] })
    },
  })

  const watermarkMutation = useMutation({
    mutationFn: () => applyWatermark(id!),
    onSuccess: (data) => {
      queryClient.setQueryData(['generation', id], data)
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
    },
  })

  const activePostprocess = isPostprocessActive(gen?.postprocess_status)
  const activePostprocessKind = (gen?.postprocess_kind ?? null) as PostprocessKind | null
  const qualityUpscaleEnabled = Boolean(upscaleModelsData?.quality_upscale_enabled)
  const qualityUpscaleReason =
    upscaleModelsData?.quality_upscale_reason ||
    'Quality upscale is disabled until the redraw workflow is revalidated.'

  useEffect(() => {
    const queuedPostprocessKind = queuedPostprocessKindRef.current
    if (!gen || !queuedPostprocessKind || activePostprocess) {
      return
    }

    const label = POSTPROCESS_LABELS[queuedPostprocessKind]
    if (didPostprocessSucceed(gen, queuedPostprocessKind)) {
      notify.success(`${label} 작업이 완료되었습니다`)
    } else if (gen.postprocess_status === 'failed' || gen.postprocess_message || gen.error_message) {
      notify.error(gen.postprocess_message || gen.error_message || `${label} 작업에 실패했습니다`)
    }

    queuedPostprocessKindRef.current = null
  }, [
    activePostprocess,
    gen,
    gen?.adetailed_path,
    gen?.error_message,
    gen?.hiresfix_path,
    gen?.postprocess_message,
    gen?.postprocess_status,
    gen?.upscaled_image_path,
  ])

  const includedCollections = (collections ?? []).filter((collection) => collection.contains_generation)
  const availableCollections = (collections ?? []).filter((collection) => !collection.contains_generation)
  const activeCollectionId = availableCollections.some((collection) => collection.id === selectedCollectionId)
    ? selectedCollectionId
    : (availableCollections[0]?.id ?? '')

  const availableUpscaleModels = upscaleModelsData?.upscale_models?.length
    ? upscaleModelsData.upscale_models
    : ['remacri_original.safetensors']
  const activeUpscaleModel = availableUpscaleModels.includes(selectedUpscaleModel)
    ? selectedUpscaleModel
    : (gen?.upscale_model || upscaleModelsData?.recommended_model || availableUpscaleModels[0])

  const compareBaseImagePath = gen?.image_path || gen?.thumbnail_path || null
  const compareOptions: CompareTargetOption[] = []

  const upscaledPath = gen?.upscaled_image_path || gen?.upscaled_preview_path
  if (upscaledPath) {
    compareOptions.push({
      type: 'upscale',
      dropdownLabel: '원본 vs 업스케일',
      resultLabel: '업스케일',
      path: upscaledPath,
    })
  }
  if (gen?.adetailed_path) {
    compareOptions.push({
      type: 'faceFix',
      dropdownLabel: '원본 vs Face Fix',
      resultLabel: 'Face Fix',
      path: gen.adetailed_path,
    })
  }
  if (gen?.hiresfix_path) {
    compareOptions.push({
      type: 'hiresfix',
      dropdownLabel: '원본 vs Hires.fix',
      resultLabel: 'Hires.fix',
      path: gen.hiresfix_path,
    })
  }

  const selectedCompareOption =
    compareOptions.find((option) => option.type === selectedCompareTarget) ||
    compareOptions[0] ||
    null
  const activeCompareTarget = selectedCompareOption?.type ?? 'upscale'

  const handleDelete = () => {
    if (window.confirm('Are you sure you want to delete this image? This cannot be undone.')) {
      deleteMutation.mutate()
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-[55vh] md:h-[70vh] bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
        <div className="h-40 bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
      </div>
    )
  }

  if (isError || !gen) {
    return (
      <div className="bg-gray-900 rounded-xl border border-red-800/50 p-8 text-center">
        <p className="text-red-400">Failed to load image details</p>
        <Link to="/gallery" className="text-sm text-violet-400 hover:text-violet-300 mt-2 inline-block">
          Back to Gallery
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        to="/gallery"
        className="inline-flex items-center gap-1 text-sm text-gray-400 hover:text-gray-200 transition-colors duration-200"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
        </svg>
        Back to Gallery
      </Link>

      {/* Images */}
      {gen.upscaled_image_path || gen.adetailed_path || gen.hiresfix_path ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-4 gap-4">
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-400 uppercase tracking-wide">
              Original
            </div>
            <div className="flex items-center justify-center">
              {gen.image_path ? (
                <img
                  src={`/data/${gen.image_path}`}
                  alt={gen.prompt.slice(0, 80)}
                  className="max-h-[80vh] md:max-h-[70vh] object-contain"
                />
              ) : (
                <div className="h-[50vh] md:h-[40vh] flex items-center justify-center text-gray-600">
                  <p>No original image available</p>
                </div>
              )}
            </div>
          </div>
          {gen.upscaled_image_path && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-400 uppercase tracking-wide">
                Upscaled
              </div>
              <div className="flex items-center justify-center">
                <img
                  src={`/data/${gen.upscaled_preview_path || gen.upscaled_image_path}`}
                  alt={`Upscaled ${gen.prompt.slice(0, 80)}`}
                  className="max-h-[80vh] md:max-h-[70vh] object-contain"
                />
              </div>
            </div>
          )}
          {gen.adetailed_path && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-400 uppercase tracking-wide">
                Face Fixed (ADetailer)
              </div>
              <div className="flex items-center justify-center">
                <img
                  src={`/data/${gen.adetailed_path}`}
                  alt={`Face fixed ${gen.prompt.slice(0, 80)}`}
                  className="max-h-[80vh] md:max-h-[70vh] object-contain"
                />
              </div>
            </div>
          )}
          {gen.hiresfix_path && (
            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
              <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-400 uppercase tracking-wide">
                Hires.fix
              </div>
              <div className="flex items-center justify-center">
                <img
                  src={`/data/${gen.hiresfix_path}`}
                  alt={`Hires.fix ${gen.prompt.slice(0, 80)}`}
                  className="max-h-[80vh] md:max-h-[70vh] object-contain"
                />
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden flex items-center justify-center">
          {gen.image_path ? (
            <img
              src={`/data/${gen.image_path}`}
              alt={gen.prompt.slice(0, 80)}
              className="max-h-[80vh] md:max-h-[70vh] object-contain"
            />
          ) : gen.thumbnail_path ? (
            <img
              src={`/data/${gen.thumbnail_path}`}
              alt={gen.prompt.slice(0, 80)}
              className="max-h-[80vh] md:max-h-[70vh] object-contain"
            />
          ) : (
            <div className="h-[50vh] md:h-[40vh] flex items-center justify-center text-gray-600">
              <p>No image available</p>
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-2 md:gap-3">
        <button
          onClick={() => favoriteMutation.mutate()}
          disabled={favoriteMutation.isPending}
          className={`w-full sm:w-auto rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 ${
            gen.is_favorite
              ? 'bg-amber-500 hover:bg-amber-400 text-white'
              : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
          }`}
        >
          {gen.is_favorite ? '★ Favorited' : '☆ Favorite'}
        </button>

        <button
          onClick={() => readyMutation.mutate()}
          disabled={readyMutation.isPending}
          className={`w-full sm:w-auto rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 ${
            gen.publish_approved === 1
              ? 'bg-emerald-600 hover:bg-emerald-500 text-white'
              : 'bg-gray-800 hover:bg-gray-700 text-gray-300'
          }`}
        >
          {gen.publish_approved === 1 ? '✓ Ready to Go' : '○ Ready to Go'}
        </button>

        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <select
            value={activeCollectionId}
            onChange={(e) => setSelectedCollectionId(e.target.value)}
            disabled={availableCollections.length === 0 || addToCollectionMutation.isPending}
            className="w-full bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm sm:w-auto"
          >
            {availableCollections.length === 0 ? (
              <option value="">No available collection</option>
            ) : (
              availableCollections.map((collection) => (
                <option key={collection.id} value={collection.id}>
                  {collection.name}
                </option>
              ))
            )}
          </select>
          <button
            onClick={() => {
              if (!activeCollectionId) return
              addToCollectionMutation.mutate(activeCollectionId)
            }}
            disabled={!activeCollectionId || addToCollectionMutation.isPending}
            className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 sm:w-auto"
          >
            Add to Collection
          </button>
        </div>

        <button
          onClick={() => reproduceMutation.mutate('exact')}
          disabled={reproduceMutation.isPending}
          className="w-full sm:w-auto bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Exact Regenerate
        </button>
        <button
          onClick={() => navigate(`/generate?from=${gen.id}`)}
          className="w-full sm:w-auto bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Edit &amp; Regenerate
        </button>
        <button
          onClick={() => reproduceMutation.mutate('variation')}
          disabled={reproduceMutation.isPending}
          className="w-full sm:w-auto bg-violet-600/80 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Variation
        </button>
        <button
          onClick={() => savePresetMutation.mutate()}
          disabled={savePresetMutation.isPending}
          className="w-full sm:w-auto bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          {savePresetMutation.isSuccess ? 'Saved!' : 'Save as Preset'}
        </button>
        {compareOptions.length > 0 && (
          <div className="flex w-full flex-col gap-2 rounded-lg border border-gray-800 bg-gray-900/80 p-2 sm:w-auto sm:flex-row sm:items-center sm:p-1">
            {compareOptions.length > 1 && (
              <select
                value={activeCompareTarget}
                onChange={(e) => setSelectedCompareTarget(e.target.value as CompareTargetType)}
                className="w-full bg-gray-900 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm sm:w-auto"
              >
                {compareOptions.map((option) => (
                  <option key={option.type} value={option.type}>
                    {option.dropdownLabel}
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={() => setIsCompareOpen(true)}
              disabled={!compareBaseImagePath || !selectedCompareOption}
              className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 sm:w-auto"
            >
              비교 보기
            </button>
          </div>
        )}
        {gen.workflow_path && (
          <a
            href={`/data/${gen.workflow_path}`}
            download
            className="w-full sm:w-auto bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 inline-flex items-center justify-center"
          >
            Download Workflow
          </a>
        )}
        {!gen.upscaled_image_path && (
          <>
            <select
              value={activeUpscaleModel}
              onChange={(e) => setSelectedUpscaleModel(e.target.value)}
              disabled={upscaleMutation.isPending || activePostprocess}
              className="w-full sm:w-auto bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm"
            >
              {availableUpscaleModels.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            <div className="flex w-full flex-col gap-2 sm:w-auto">
              <div className="flex w-full flex-col gap-2 sm:flex-row">
                <button
                  onClick={() => upscaleMutation.mutate({ model: activeUpscaleModel, mode: 'safe' })}
                  disabled={upscaleMutation.isPending || activePostprocess || !activeUpscaleModel}
                  className="w-full sm:w-auto bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
                >
                  {activePostprocessKind === 'upscale' && activePostprocess ? 'Upscale Queued...' : 'Safe Upscale'}
                </button>
                <button
                  onClick={() => upscaleMutation.mutate({ model: activeUpscaleModel, mode: 'quality' })}
                  disabled={
                    upscaleMutation.isPending || activePostprocess || !activeUpscaleModel || !qualityUpscaleEnabled
                  }
                  className="w-full sm:w-auto bg-fuchsia-700/80 hover:bg-fuchsia-600 disabled:opacity-40 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
                >
                  Quality Upscale
                </button>
              </div>
              <div className="rounded-lg border border-gray-800 bg-gray-950/70 px-3 py-2 text-xs leading-5">
                <p className="text-gray-300">
                  `Safe Upscale` uses the current non-redraw path and is the recommended default.
                </p>
                {upscaleModelsData?.recommended_model && (
                  <p className="text-cyan-300">
                    Recommended for this checkpoint: {upscaleModelsData.recommended_model}
                    {upscaleModelsData.recommended_profile
                      ? ` (${upscaleModelsData.recommended_profile})`
                      : ''}
                  </p>
                )}
                {upscaleModelsData?.recommended_mode && (
                  <p className="text-emerald-300">
                    Recommended path: {upscaleModelsData.recommended_mode === 'quality' ? 'Quality Upscale' : 'Safe Upscale'}
                  </p>
                )}
                {upscaleModelsData?.recommended_mode_reason && (
                  <p className="text-gray-400">
                    {upscaleModelsData.recommended_mode_reason}
                  </p>
                )}
                <p className={qualityUpscaleEnabled ? 'text-fuchsia-300' : 'text-amber-300'}>
                  {qualityUpscaleEnabled
                    ? 'Quality Upscale experimental path is enabled.'
                    : qualityUpscaleReason}
                </p>
              </div>
            </div>
          </>
        )}
        {gen.upscaled_image_path && (
          <a
            href={`/data/${gen.upscaled_image_path}`}
            download
            className="w-full sm:w-auto bg-blue-600/20 hover:bg-blue-600/30 border border-blue-700/40 text-blue-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 inline-flex items-center justify-center"
          >
            Download Upscaled
          </a>
        )}
        {!gen.adetailed_path && (
          <button
            onClick={() => adetailMutation.mutate()}
            disabled={adetailMutation.isPending || activePostprocess || !gen.image_path}
            className="w-full sm:w-auto bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
          >
            {activePostprocessKind === 'adetail' && activePostprocess ? 'Face Fix Queued...' : 'Fix Faces (ADetailer)'}
          </button>
        )}
        {gen.adetailed_path && (
          <a
            href={`/data/${gen.adetailed_path}`}
            download
            className="w-full sm:w-auto bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-700/40 text-indigo-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 inline-flex items-center justify-center"
          >
            Download Face-Fixed
          </a>
        )}
        {!gen.hiresfix_path && (
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:items-center">
            <button
              onClick={() => hiresfixMutation.mutate()}
              disabled={hiresfixMutation.isPending || activePostprocess || (!gen.image_path && !gen.upscaled_image_path)}
              className="w-full sm:w-auto bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
            >
              {activePostprocessKind === 'hiresfix' && activePostprocess ? 'Hires.fix Queued...' : 'Hires.fix'}
            </button>
            <button
              onClick={() => setShowHiresfixAdvanced((prev) => !prev)}
              className="w-full sm:w-auto bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-3 py-2 text-xs font-medium transition-colors duration-200"
            >
              {showHiresfixAdvanced ? 'Hide Hires.fix Options' : 'Hires.fix Options'}
            </button>
            {showHiresfixAdvanced && (
              <div className="flex w-full flex-col items-stretch gap-2 rounded-lg border border-gray-700 bg-gray-900/80 px-3 py-2 sm:w-auto sm:flex-row sm:items-center">
                <label className="text-xs text-gray-400">
                  Scale
                  <input
                    type="number"
                    min={1.1}
                    max={2.0}
                    step={0.05}
                    value={hiresfixScaleFactor}
                    onChange={(e) => {
                      const value = Number(e.target.value)
                      if (!Number.isNaN(value)) {
                        setHiresfixScaleFactor(value)
                      }
                    }}
                    className="ml-2 w-20 rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-100"
                  />
                </label>
                <label className="text-xs text-gray-400">
                  Denoise
                  <input
                    type="number"
                    min={0.2}
                    max={0.85}
                    step={0.05}
                    value={hiresfixDenoise}
                    onChange={(e) => {
                      const value = Number(e.target.value)
                      if (!Number.isNaN(value)) {
                        setHiresfixDenoise(value)
                      }
                    }}
                    className="ml-2 w-20 rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-100"
                  />
                </label>
              </div>
            )}
          </div>
        )}
        {gen.hiresfix_path && (
          <a
            href={`/data/${gen.hiresfix_path}`}
            download
            className="w-full sm:w-auto bg-cyan-600/20 hover:bg-cyan-600/30 border border-cyan-700/40 text-cyan-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 inline-flex items-center justify-center"
          >
            Download Hires.fix
          </a>
        )}
        {!gen.watermarked_path && (
          <button
            onClick={() => watermarkMutation.mutate()}
            disabled={watermarkMutation.isPending || activePostprocess || !gen.image_path}
            className="w-full sm:w-auto bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
          >
            {watermarkMutation.isPending ? 'Applying...' : 'Apply Watermark'}
          </button>
        )}
        {gen.watermarked_path && (
          <a
            href={`/data/${gen.watermarked_path}`}
            download
            className="w-full sm:w-auto bg-amber-600/20 hover:bg-amber-600/30 border border-amber-700/40 text-amber-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 inline-flex items-center justify-center"
          >
            Download Watermarked
          </a>
        )}
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="w-full sm:w-auto bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 sm:ml-auto"
        >
          Delete
        </button>
      </div>

      {gen.postprocess_kind && gen.postprocess_status && (
        <div
          className={`rounded-xl border p-4 ${
            activePostprocess
              ? 'border-sky-700/50 bg-sky-900/20'
              : 'border-red-800/50 bg-red-900/20'
          }`}
        >
          <div className="flex items-center gap-3">
            {activePostprocess && (
              <div className="h-4 w-4 rounded-full border-2 border-sky-400 border-t-transparent animate-spin" />
            )}
            <div>
              <p className={`text-sm font-medium ${activePostprocess ? 'text-sky-300' : 'text-red-300'}`}>
                {POSTPROCESS_LABELS[gen.postprocess_kind as PostprocessKind] ?? gen.postprocess_kind}
                {' '}
                {activePostprocess ? '작업 진행 중' : '작업 실패'}
              </p>
              <p className={`mt-1 text-xs ${activePostprocess ? 'text-sky-200/80' : 'text-red-200/80'}`}>
                {gen.postprocess_message || gen.error_message || '백그라운드 작업 상태를 확인하는 중입니다.'}
              </p>
            </div>
          </div>
        </div>
      )}

      <DreamActorPanel generation={gen} />
      <LocalAnimationPanel generation={gen} />

      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
        <p className="text-xs text-gray-500 uppercase tracking-wide mb-2">Included Collections</p>
        {includedCollections.length === 0 ? (
          <p className="text-sm text-gray-500">This image is not in any collection.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {includedCollections.map((collection) => (
              <Link
                key={collection.id}
                to={`/collections/${collection.id}`}
                className="text-xs bg-violet-600/20 border border-violet-500/30 text-violet-300 rounded-full px-3 py-1 hover:bg-violet-600/30"
              >
                {collection.name}
              </Link>
            ))}
          </div>
        )}
      </div>

      {reproduceMutation.isError && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
          <p className="text-sm text-red-400">Failed to reproduce. Is ComfyUI connected?</p>
        </div>
      )}

      {upscaleMutation.isError && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
          <p className="text-sm text-red-400">
            Upscale failed. Safe mode stays on the model-only path, and quality mode remains blocked until the redraw workflow is revalidated.
          </p>
        </div>
      )}

      {adetailMutation.isError && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
          <p className="text-sm text-red-400">Face fix failed. No face detected or ComfyUI inpaint node unavailable.</p>
        </div>
      )}

      {hiresfixMutation.isError && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
          <p className="text-sm text-red-400">Hires.fix failed. Check ComfyUI latent upscale nodes and source image.</p>
        </div>
      )}

      {watermarkMutation.isError && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
          <p className="text-sm text-red-400">Watermark application failed.</p>
        </div>
      )}

      {(favoriteMutation.isError || addToCollectionMutation.isError) && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
          <p className="text-sm text-red-400">Collection/Favorite update failed.</p>
        </div>
      )}

      {/* Metadata panel */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 md:p-6 space-y-6">
        {/* Parameters grid */}
        <div>
          <h3 className="text-sm font-medium text-gray-300 mb-3">Parameters</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            <MetaItem label="Checkpoint" value={gen.checkpoint} />
            <MetaItem label="Seed" value={String(gen.seed)} mono />
            <MetaItem label="Steps" value={String(gen.steps)} mono />
            <MetaItem label="CFG" value={String(gen.cfg)} mono />
            <MetaItem label="Size" value={`${gen.width} x ${gen.height}`} mono />
            <MetaItem label="Sampler" value={gen.sampler} />
            <MetaItem label="Scheduler" value={gen.scheduler} />
            {gen.upscale_model && <MetaItem label="Upscale Model" value={gen.upscale_model} />}
            {gen.generation_time_sec != null && (
              <MetaItem label="Gen Time" value={`${gen.generation_time_sec.toFixed(1)}s`} mono />
            )}
          </div>
        </div>

        {/* Prompt */}
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <h3 className="text-sm font-medium text-gray-300">Prompt</h3>
            <button
              onClick={() => copyToClipboard(gen.prompt)}
              className="text-xs text-gray-500 hover:text-gray-300 transition-colors duration-200"
            >
              Copy
            </button>
          </div>
          <p className="text-sm text-gray-400 font-mono bg-gray-800 rounded-lg p-3 whitespace-pre-wrap">
            {gen.prompt}
          </p>
        </div>

        {/* Negative prompt */}
        {gen.negative_prompt && (
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
              <h3 className="text-sm font-medium text-gray-300">Negative Prompt</h3>
              <button
                onClick={() => copyToClipboard(gen.negative_prompt!)}
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors duration-200"
              >
                Copy
              </button>
            </div>
            <p className="text-sm text-gray-400 font-mono bg-gray-800 rounded-lg p-3 whitespace-pre-wrap">
              {gen.negative_prompt}
            </p>
          </div>
        )}

        {/* LoRAs */}
        {gen.loras.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-3">LoRAs</h3>
            <div className="space-y-2 md:hidden">
              {gen.loras.map((lora, i) => (
                <div key={i} className="rounded-lg border border-gray-800 bg-gray-950/50 p-3">
                  <p className="text-sm text-gray-300 break-all">{lora.filename}</p>
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-gray-500">Strength</span>
                    <span className="text-gray-400 font-mono">{lora.strength.toFixed(2)}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-xs">
                    <span className="text-gray-500">Category</span>
                    <span className="text-gray-400">{lora.category ?? '-'}</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b border-gray-800">
                    <th className="pb-2 pr-4">Name</th>
                    <th className="pb-2 pr-4">Strength</th>
                    <th className="pb-2">Category</th>
                  </tr>
                </thead>
                <tbody>
                  {gen.loras.map((lora, i) => (
                    <tr key={i} className="border-b border-gray-800/50">
                      <td className="py-2 pr-4 text-gray-300">{lora.filename}</td>
                      <td className="py-2 pr-4 text-gray-400 font-mono">{lora.strength.toFixed(2)}</td>
                      <td className="py-2 text-gray-400">{lora.category ?? '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tags */}
        {gen.tags && gen.tags.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-2">Tags</h3>
            <div className="flex flex-wrap gap-2">
              {gen.tags.map((tag) => (
                <span key={tag} className="text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Notes */}
        {gen.notes && (
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-2">Notes</h3>
            <p className="text-sm text-gray-400">{gen.notes}</p>
          </div>
        )}

        {/* Source */}
        {gen.source_id && (
          <div>
            <h3 className="text-sm font-medium text-gray-300 mb-2">Reproduced From</h3>
            <Link
              to={`/gallery/${gen.source_id}`}
              className="text-sm text-violet-400 hover:text-violet-300 transition-colors duration-200"
            >
              {gen.source_id}
            </Link>
          </div>
        )}

        {/* Timestamps */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-gray-500 pt-2 border-t border-gray-800">
          <span>Created: {new Date(gen.created_at).toLocaleString()}</span>
          {gen.completed_at && (
            <span>Completed: {new Date(gen.completed_at).toLocaleString()}</span>
          )}
          {gen.preset_id && <span>Preset: {gen.preset_id}</span>}
          <span>Status: {gen.status}</span>
        </div>
      </div>

      {isCompareOpen && compareBaseImagePath && selectedCompareOption && (
        <CompareView
          leftImage={{ url: `/data/${compareBaseImagePath}`, label: '원본' }}
          rightImage={{
            url: `/data/${selectedCompareOption.path}`,
            label: selectedCompareOption.resultLabel,
          }}
          onClose={() => setIsCompareOpen(false)}
        />
      )}
    </div>
  )
}

function MetaItem({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className={`text-sm text-gray-200 mt-0.5 ${mono ? 'font-mono' : ''}`}>{value}</p>
    </div>
  )
}
