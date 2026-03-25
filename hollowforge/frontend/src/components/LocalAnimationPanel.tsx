import { useMemo, useState } from 'react'
import { isAxiosError } from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  getAnimationExecutorConfig,
  getAnimationPresets,
  launchAnimationPreset,
  listAnimationJobs,
} from '../api/client'
import type {
  AnimationJobResponse,
  AnimationPresetResponse,
  GenerationResponse,
} from '../api/client'
import { notify } from '../lib/toast'
import VideoPlayer from './VideoPlayer'

interface LocalAnimationPanelProps {
  generation: GenerationResponse
}

interface AnimationFormState {
  prompt: string
  negativePrompt: string
  width: string
  height: string
  frames: string
  fps: string
  steps: string
  cfg: string
  seed: string
  motionStrength: string
}

const ACTIVE_JOB_STATUSES = new Set(['queued', 'submitted', 'processing'])
const DEFAULT_ANIMATION_FORM: AnimationFormState = {
  prompt: '',
  negativePrompt: '',
  width: '768',
  height: '512',
  frames: '49',
  fps: '12',
  steps: '24',
  cfg: '3.5',
  seed: '42',
  motionStrength: '0.55',
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-green-900/40 text-green-300 border-green-700/50'
    case 'failed':
      return 'bg-red-900/40 text-red-300 border-red-700/50'
    case 'submitted':
    case 'processing':
      return 'bg-blue-900/40 text-blue-300 border-blue-700/50'
    case 'queued':
      return 'bg-amber-900/40 text-amber-300 border-amber-700/50'
    default:
      return 'bg-gray-700/70 text-gray-200 border-gray-600'
  }
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

function readString(source: Record<string, unknown>, key: string, fallback = ''): string {
  const value = source[key]
  return typeof value === 'string' ? value : fallback
}

function readNumberString(source: Record<string, unknown>, key: string, fallback: string): string {
  const value = source[key]
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value)
  }
  if (typeof value === 'string' && value.trim()) {
    return value
  }
  return fallback
}

function formFromPreset(preset: AnimationPresetResponse): AnimationFormState {
  const request = preset.request_json ?? {}
  return {
    prompt: readString(request, 'prompt'),
    negativePrompt: readString(request, 'negative_prompt'),
    width: readNumberString(request, 'width', '768'),
    height: readNumberString(request, 'height', '512'),
    frames: readNumberString(request, 'frames', '49'),
    fps: readNumberString(request, 'fps', '12'),
    steps: readNumberString(request, 'steps', '24'),
    cfg: readNumberString(request, 'cfg', '3.5'),
    seed: readNumberString(request, 'seed', '42'),
    motionStrength: readNumberString(request, 'motion_strength', '0.55'),
  }
}

function buildRequestOverrides(form: AnimationFormState): Record<string, unknown> {
  const overrides: Record<string, unknown> = {
    prompt: form.prompt,
    negative_prompt: form.negativePrompt,
  }

  const numberFields: Array<[key: string, value: string, kind: 'int' | 'float']> = [
    ['width', form.width, 'int'],
    ['height', form.height, 'int'],
    ['frames', form.frames, 'int'],
    ['fps', form.fps, 'float'],
    ['steps', form.steps, 'int'],
    ['cfg', form.cfg, 'float'],
    ['motion_strength', form.motionStrength, 'float'],
  ]

  for (const [key, value, kind] of numberFields) {
    const trimmed = value.trim()
    if (!trimmed) continue
    const parsed = kind === 'int' ? Number.parseInt(trimmed, 10) : Number.parseFloat(trimmed)
    if (Number.isFinite(parsed)) {
      overrides[key] = parsed
    }
  }

  const seedValue = form.seed.trim()
  if (seedValue) {
    const parsedSeed = Number.parseInt(seedValue, 10)
    if (Number.isFinite(parsedSeed)) {
      overrides.seed = parsedSeed
    }
  }

  return overrides
}

export default function LocalAnimationPanel({ generation }: LocalAnimationPanelProps) {
  const queryClient = useQueryClient()
  const [selectedPresetId, setSelectedPresetId] = useState('')
  const [formPresetId, setFormPresetId] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [form, setForm] = useState<AnimationFormState>(DEFAULT_ANIMATION_FORM)

  const { data: executorConfig } = useQuery({
    queryKey: ['animation-executor-config'],
    queryFn: getAnimationExecutorConfig,
  })

  const { data: presets = [] } = useQuery({
    queryKey: ['animation-presets'],
    queryFn: getAnimationPresets,
  })

  const effectiveSelectedPresetId = selectedPresetId || presets[0]?.id || ''
  const selectedPreset = useMemo(
    () => presets.find((preset) => preset.id === effectiveSelectedPresetId) ?? null,
    [effectiveSelectedPresetId, presets],
  )
  const activeForm = useMemo(() => {
    if (!selectedPreset) return form
    return formPresetId === selectedPreset.id ? form : formFromPreset(selectedPreset)
  }, [form, formPresetId, selectedPreset])

  const handlePresetChange = (nextPresetId: string) => {
    setSelectedPresetId(nextPresetId)
    const nextPreset = presets.find((preset) => preset.id === nextPresetId) ?? null
    setForm(nextPreset ? formFromPreset(nextPreset) : DEFAULT_ANIMATION_FORM)
    setFormPresetId(nextPresetId)
  }

  const updateForm = (field: keyof AnimationFormState, value: string) => {
    setForm({
      ...activeForm,
      [field]: value,
    })
    setFormPresetId(selectedPreset?.id ?? effectiveSelectedPresetId)
  }

  const jobsQuery = useQuery({
    queryKey: ['animation-jobs', generation.id],
    queryFn: () => listAnimationJobs({ generation_id: generation.id, limit: 10 }),
    enabled: Boolean(generation.id),
    refetchInterval: (query) => {
      const jobs = query.state.data ?? []
      const latestJob = jobs[0]
      return latestJob && ACTIVE_JOB_STATUSES.has(latestJob.status) ? 4000 : false
    },
  })

  const latestJob: AnimationJobResponse | null = jobsQuery.data?.[0] ?? null
  const latestJobModelProfile = useMemo(() => {
    const request = latestJob?.request_json
    if (!request || typeof request !== 'object') return null
    const modelProfile = request.model_profile
    return typeof modelProfile === 'string' ? modelProfile : null
  }, [latestJob])

  const launchMutation = useMutation({
    mutationFn: () => {
      if (!selectedPreset) {
        throw new Error('Animation preset is not available')
      }
      return launchAnimationPreset(selectedPreset.id, {
        generation_id: generation.id,
        dispatch_immediately: true,
        request_overrides: buildRequestOverrides(activeForm),
      })
    },
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ['animation-jobs', generation.id] })
      if (data.dispatch_error) {
        notify.error(`Animation job created, but dispatch failed: ${data.dispatch_error}`)
        return
      }
      notify.success('Local animation job queued')
    },
    onError: (error) => {
      notify.error(getApiErrorMessage(error, 'Failed to launch local animation job'))
    },
  })

  return (
    <section className="rounded-xl border border-gray-800 bg-gray-900 p-5 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-gray-100">Local I2V</h3>
          <p className="mt-1 text-xs text-gray-500">
            ComfyUI animation worker • LTX-Video fast preset routing
          </p>
        </div>
        {executorConfig && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded border border-sky-700/40 bg-sky-900/20 px-2 py-1 text-sky-200">
              mode: {executorConfig.mode}
            </span>
            <span className="rounded border border-gray-700 bg-gray-800 px-2 py-1 text-gray-300">
              key: {executorConfig.executor_key}
            </span>
          </div>
        )}
      </div>

      {selectedPreset ? (
        <>
          <div className="grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
            <label className="space-y-1">
              <span className="text-xs text-gray-400">Preset</span>
              <select
                value={effectiveSelectedPresetId}
                onChange={(event) => handlePresetChange(event.target.value)}
                className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 focus:border-sky-500 focus:outline-none"
              >
                {presets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="rounded-lg border border-gray-800 bg-gray-950/60 px-4 py-3">
              <p className="text-sm font-medium text-gray-100">{selectedPreset.name}</p>
              {selectedPreset.description && (
                <p className="mt-1 text-xs text-gray-400">{selectedPreset.description}</p>
              )}
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-300">
                <span className="rounded border border-gray-700 bg-gray-900 px-2 py-1">
                  target: {selectedPreset.target_tool}
                </span>
                <span className="rounded border border-gray-700 bg-gray-900 px-2 py-1">
                  backend: {selectedPreset.backend_family}
                </span>
                <span className="rounded border border-gray-700 bg-gray-900 px-2 py-1">
                  profile: {selectedPreset.model_profile}
                </span>
              </div>
            </div>
          </div>

          <label className="block space-y-1">
            <span className="text-xs text-gray-400">Prompt</span>
            <textarea
              value={activeForm.prompt}
              onChange={(event) => updateForm('prompt', event.target.value)}
              rows={3}
              className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 focus:border-sky-500 focus:outline-none"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-xs text-gray-400">Negative Prompt</span>
            <textarea
              value={activeForm.negativePrompt}
              onChange={(event) => updateForm('negativePrompt', event.target.value)}
              rows={2}
              className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 focus:border-sky-500 focus:outline-none"
            />
          </label>

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => setShowAdvanced((prev) => !prev)}
              className="text-xs text-sky-300 hover:text-sky-200"
            >
              {showAdvanced ? 'Hide advanced settings' : 'Show advanced settings'}
            </button>
            <button
              type="button"
              onClick={() => launchMutation.mutate()}
              disabled={launchMutation.isPending || !generation.image_path || !selectedPreset}
              className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
            >
              {launchMutation.isPending ? 'Launching...' : 'Launch Local I2V'}
            </button>
          </div>

          {showAdvanced && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ['Width', 'width'],
                ['Height', 'height'],
                ['Frames', 'frames'],
                ['FPS', 'fps'],
                ['Steps', 'steps'],
                ['CFG', 'cfg'],
                ['Seed', 'seed'],
                ['Motion', 'motionStrength'],
              ].map(([label, key]) => (
                <label key={key} className="space-y-1">
                  <span className="text-xs text-gray-400">{label}</span>
                  <input
                    type="text"
                    value={activeForm[key as keyof AnimationFormState]}
                    onChange={(event) => updateForm(key as keyof AnimationFormState, event.target.value)}
                    className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 focus:border-sky-500 focus:outline-none"
                  />
                </label>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="rounded-lg border border-amber-700/40 bg-amber-900/20 px-4 py-3 text-sm text-amber-200">
          No local animation presets are available yet.
        </div>
      )}

      {latestJob && (
        <div className="space-y-3 rounded-lg border border-gray-800 bg-gray-950/60 px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-gray-400">Latest job</span>
              <span className={`rounded border px-2 py-1 ${statusBadgeClass(latestJob.status)}`}>
                {latestJob.status}
              </span>
            </div>
            <div className="flex flex-wrap gap-2 text-xs text-gray-400">
              <span>{latestJob.target_tool}</span>
              {latestJobModelProfile && <span>{latestJobModelProfile}</span>}
            </div>
          </div>

          {latestJob.error_message && (
            <p className="text-sm text-red-300">{latestJob.error_message}</p>
          )}

          {latestJob.external_job_url && (
            <a
              href={latestJob.external_job_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex text-xs text-sky-300 hover:text-sky-200"
            >
              Open remote worker job
            </a>
          )}

          {latestJob.output_path && <VideoPlayer src={latestJob.output_path} />}
        </div>
      )}
    </section>
  )
}
