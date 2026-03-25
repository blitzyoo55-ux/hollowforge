import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getGeneration,
  deleteGalleryItem,
  reproduceGeneration,
  createPreset,
  getUpscaleModels,
  upscaleGeneration,
} from '../api/client'

export default function ImageDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedUpscaleModel, setSelectedUpscaleModel] = useState('remacri_original.safetensors')

  const { data: gen, isLoading, isError } = useQuery({
    queryKey: ['generation', id],
    queryFn: () => getGeneration(id!),
    enabled: !!id,
  })

  const { data: upscaleModelsData } = useQuery({
    queryKey: ['upscale-models'],
    queryFn: getUpscaleModels,
  })

  const deleteMutation = useMutation({
    mutationFn: () => deleteGalleryItem(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
      navigate('/gallery')
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
    mutationFn: (model: string) => upscaleGeneration(id!, model),
    onSuccess: (data) => {
      queryClient.setQueryData(['generation', id], data)
      queryClient.invalidateQueries({ queryKey: ['gallery'] })
    },
  })

  useEffect(() => {
    if (gen?.upscale_model) {
      setSelectedUpscaleModel(gen.upscale_model)
      return
    }
    const firstModel = upscaleModelsData?.upscale_models?.[0]
    if (firstModel) {
      setSelectedUpscaleModel(firstModel)
    }
  }, [gen?.upscale_model, upscaleModelsData?.upscale_models])

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
        <div className="h-[70vh] bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
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
      {gen.upscaled_image_path ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-400 uppercase tracking-wide">
              Original
            </div>
            <div className="flex items-center justify-center">
              {gen.image_path ? (
                <img
                  src={`/data/${gen.image_path}`}
                  alt={gen.prompt.slice(0, 80)}
                  className="max-h-[70vh] object-contain"
                />
              ) : (
                <div className="h-[40vh] flex items-center justify-center text-gray-600">
                  <p>No original image available</p>
                </div>
              )}
            </div>
          </div>
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-400 uppercase tracking-wide">
              Upscaled
            </div>
            <div className="flex items-center justify-center">
              <img
                src={`/data/${gen.upscaled_preview_path || gen.upscaled_image_path}`}
                alt={`Upscaled ${gen.prompt.slice(0, 80)}`}
                className="max-h-[70vh] object-contain"
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden flex items-center justify-center">
          {gen.image_path ? (
            <img
              src={`/data/${gen.image_path}`}
              alt={gen.prompt.slice(0, 80)}
              className="max-h-[70vh] object-contain"
            />
          ) : gen.thumbnail_path ? (
            <img
              src={`/data/${gen.thumbnail_path}`}
              alt={gen.prompt.slice(0, 80)}
              className="max-h-[70vh] object-contain"
            />
          ) : (
            <div className="h-[40vh] flex items-center justify-center text-gray-600">
              <p>No image available</p>
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => reproduceMutation.mutate('exact')}
          disabled={reproduceMutation.isPending}
          className="bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Exact Regenerate
        </button>
        <button
          onClick={() => navigate(`/generate?from=${gen.id}`)}
          className="bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Edit &amp; Regenerate
        </button>
        <button
          onClick={() => reproduceMutation.mutate('variation')}
          disabled={reproduceMutation.isPending}
          className="bg-violet-600/80 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Variation
        </button>
        <button
          onClick={() => savePresetMutation.mutate()}
          disabled={savePresetMutation.isPending}
          className="bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          {savePresetMutation.isSuccess ? 'Saved!' : 'Save as Preset'}
        </button>
        {gen.workflow_path && (
          <a
            href={`/data/${gen.workflow_path}`}
            download
            className="bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 inline-flex items-center"
          >
            Download Workflow
          </a>
        )}
        {!gen.upscaled_image_path && (
          <>
            <select
              value={selectedUpscaleModel}
              onChange={(e) => setSelectedUpscaleModel(e.target.value)}
              disabled={upscaleMutation.isPending}
              className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm"
            >
              {(upscaleModelsData?.upscale_models?.length
                ? upscaleModelsData.upscale_models
                : ['remacri_original.safetensors']
              ).map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            <button
              onClick={() => upscaleMutation.mutate(selectedUpscaleModel)}
              disabled={upscaleMutation.isPending || !selectedUpscaleModel}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
            >
              {upscaleMutation.isPending ? 'Upscaling...' : 'Upscale'}
            </button>
          </>
        )}
        {gen.upscaled_image_path && (
          <a
            href={`/data/${gen.upscaled_image_path}`}
            download
            className="bg-blue-600/20 hover:bg-blue-600/30 border border-blue-700/40 text-blue-300 rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 inline-flex items-center"
          >
            Download Upscaled
          </a>
        )}
        <button
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
          className="bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200 ml-auto"
        >
          Delete
        </button>
      </div>

      {reproduceMutation.isError && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
          <p className="text-sm text-red-400">Failed to reproduce. Is ComfyUI connected?</p>
        </div>
      )}

      {upscaleMutation.isError && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4">
          <p className="text-sm text-red-400">Upscale failed. Is ComfyUI connected and model available?</p>
        </div>
      )}

      {/* Metadata panel */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-6">
        {/* Parameters grid */}
        <div>
          <h3 className="text-sm font-medium text-gray-300 mb-3">Parameters</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
          <div className="flex items-center justify-between mb-2">
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
            <div className="flex items-center justify-between mb-2">
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
            <div className="overflow-x-auto">
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
        <div className="flex items-center gap-6 text-xs text-gray-500 pt-2 border-t border-gray-800">
          <span>Created: {new Date(gen.created_at).toLocaleString()}</span>
          {gen.completed_at && (
            <span>Completed: {new Date(gen.completed_at).toLocaleString()}</span>
          )}
          {gen.preset_id && <span>Preset: {gen.preset_id}</span>}
          <span>Status: {gen.status}</span>
        </div>
      </div>
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
