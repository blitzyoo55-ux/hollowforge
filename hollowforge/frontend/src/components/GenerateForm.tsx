import { useCallback, useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  getModels,
  getPresets,
  getPromptTemplates,
  getQualityProfiles,
} from '../api/client'
import type {
  CheckpointPromptTemplates,
  GenerationCreate,
  GenerationResponse,
  LoraInput,
  PromptTemplate,
} from '../api/client'
import LoraSelector from './LoraSelector'
import { DEFAULT_NEGATIVE_PROMPT } from '../lib/defaultPrompts'

export interface GenerateSubmitPayload {
  generation: GenerationCreate
  batchCount: number
}

interface GenerateFormProps {
  initialValues?: Partial<GenerationCreate>
  initialData?: GenerationResponse | null
  onSubmit: (payload: GenerateSubmitPayload) => void
  submitLabel?: string
  isSubmitting?: boolean
  onSavePreset?: (data: GenerationCreate) => void
}

const MOODS = ['cyberpunk', 'dungeon', 'lab', 'latex', 'bondage'] as const
type TemplateApplyMode = 'replace' | 'append'

function resolveTemplateSelection(
  templates: PromptTemplate[],
  selectedId: string,
  fallbackId: string,
): string {
  if (templates.some((tpl) => tpl.id === selectedId)) {
    return selectedId
  }
  return fallbackId
}

export default function GenerateForm({
  initialValues,
  initialData,
  onSubmit,
  submitLabel = 'Generate',
  isSubmitting = false,
  onSavePreset,
}: GenerateFormProps) {
  const [prompt, setPrompt] = useState(initialData?.prompt ?? initialValues?.prompt ?? '')
  const [negativePrompt, setNegativePrompt] = useState(
    initialData?.negative_prompt ??
      initialValues?.negative_prompt ??
      DEFAULT_NEGATIVE_PROMPT,
  )
  const [checkpoint, setCheckpoint] = useState(initialData?.checkpoint ?? initialValues?.checkpoint ?? '')
  const [loras, setLoras] = useState<LoraInput[]>(initialData?.loras ?? initialValues?.loras ?? [])
  const [selectedMoods, setSelectedMoods] = useState<string[]>([])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [steps, setSteps] = useState(initialData?.steps ?? initialValues?.steps ?? 30)
  const [cfg, setCfg] = useState(initialData?.cfg ?? initialValues?.cfg ?? 5.5)
  const [width, setWidth] = useState(initialData?.width ?? initialValues?.width ?? 832)
  const [height, setHeight] = useState(initialData?.height ?? initialValues?.height ?? 1216)
  const [sampler, setSampler] = useState(initialData?.sampler ?? initialValues?.sampler ?? 'euler_ancestral')
  const [scheduler, setScheduler] = useState(initialData?.scheduler ?? initialValues?.scheduler ?? 'normal')
  const [seed, setSeed] = useState(initialData?.seed?.toString() ?? initialValues?.seed?.toString() ?? '')
  const [clipSkip, setClipSkip] = useState(
    initialData?.clip_skip != null
      ? initialData.clip_skip.toString()
      : initialValues?.clip_skip != null
        ? initialValues.clip_skip.toString()
        : '2'
  )
  const [tags, setTags] = useState(
    initialData?.tags?.join(', ') ?? initialValues?.tags?.join(', ') ?? ''
  )
  const [notes, setNotes] = useState(initialData?.notes ?? initialValues?.notes ?? '')
  const [selectedPresetId, setSelectedPresetId] = useState<string>('')
  const [sourceId, setSourceId] = useState<string | null>(initialData?.id ?? null)
  const [batchCount, setBatchCount] = useState(1)
  const [autoQualityProfile, setAutoQualityProfile] = useState(true)
  const [appliedQualityProfile, setAppliedQualityProfile] = useState<string>('')
  const [selectedPositiveTemplateId, setSelectedPositiveTemplateId] = useState('')
  const [selectedNegativeTemplateId, setSelectedNegativeTemplateId] = useState('')
  const [templateApplyMode, setTemplateApplyMode] = useState<TemplateApplyMode>('replace')

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: getModels,
  })

  const { data: qualityProfiles } = useQuery({
    queryKey: ['quality-profiles'],
    queryFn: getQualityProfiles,
  })

  const { data: presets } = useQuery({
    queryKey: ['presets'],
    queryFn: getPresets,
  })

  const { data: promptTemplates } = useQuery({
    queryKey: ['prompt-templates'],
    queryFn: getPromptTemplates,
    staleTime: 120_000,
  })

  const checkpointTemplates: CheckpointPromptTemplates | undefined =
    checkpoint ? promptTemplates?.templates?.[checkpoint] : undefined

  const applyQualityProfile = useCallback((checkpointName: string) => {
    const profile = qualityProfiles?.profiles?.[checkpointName]
    if (!profile || !profile.applicable || !profile.params) {
      setAppliedQualityProfile('')
      return
    }
    setSteps(profile.params.steps)
    setCfg(profile.params.cfg)
    setWidth(profile.params.width)
    setHeight(profile.params.height)
    setSampler(profile.params.sampler)
    setScheduler(profile.params.scheduler)
    setClipSkip(
      profile.params.clip_skip != null ? String(profile.params.clip_skip) : ''
    )
    setAppliedQualityProfile(profile.profile_name)
  }, [qualityProfiles])

  useEffect(() => {
    if (!autoQualityProfile || !checkpoint || !qualityProfiles?.profiles) return
    const timer = window.setTimeout(() => {
      applyQualityProfile(checkpoint)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [autoQualityProfile, checkpoint, qualityProfiles, applyQualityProfile])

  const activePositiveTemplateId = checkpointTemplates
    ? resolveTemplateSelection(
        checkpointTemplates.positive_templates,
        selectedPositiveTemplateId,
        checkpointTemplates.default_positive_template_id,
      )
    : ''

  const activeNegativeTemplateId = checkpointTemplates
    ? resolveTemplateSelection(
        checkpointTemplates.negative_templates,
        selectedNegativeTemplateId,
        checkpointTemplates.default_negative_template_id,
      )
    : ''

  const toggleMood = (mood: string) => {
    setSelectedMoods((prev) =>
      prev.includes(mood) ? prev.filter((m) => m !== mood) : [...prev, mood]
    )
  }

  const handlePresetSelect = (presetId: string) => {
    setSelectedPresetId(presetId)
    if (!presetId) return
    const preset = presets?.find((p) => p.id === presetId)
    if (!preset) return
    if (preset.prompt_template) setPrompt(preset.prompt_template)
    if (preset.negative_prompt) setNegativePrompt(preset.negative_prompt)
    setCheckpoint(preset.checkpoint)
    setLoras(preset.loras)
    if (preset.tags) setTags(preset.tags.join(', '))
    const params = preset.default_params
    if (params.steps != null) setSteps(params.steps as number)
    if (params.cfg != null) setCfg(params.cfg as number)
    if (params.width != null) setWidth(params.width as number)
    if (params.height != null) setHeight(params.height as number)
    if (params.sampler != null) setSampler(params.sampler as string)
    if (params.scheduler != null) setScheduler(params.scheduler as string)
    if (params.clip_skip != null) setClipSkip(String(params.clip_skip))
    else setClipSkip('')
  }

  const randomizeSeed = () => {
    const next = Math.floor(Math.random() * 2147483647)
    setSeed(String(next))
  }

  const appendTemplateText = (current: string, next: string): string => {
    const currentTrimmed = current.trim()
    const nextTrimmed = next.trim()
    if (!nextTrimmed) return currentTrimmed
    if (!currentTrimmed) return nextTrimmed
    if (currentTrimmed.includes(nextTrimmed)) return currentTrimmed
    return `${currentTrimmed}, ${nextTrimmed}`
  }

  const findPromptTemplate = (
    templates: PromptTemplate[],
    templateId: string,
  ): PromptTemplate | undefined => templates.find((tpl) => tpl.id === templateId)

  const applyPromptTemplate = (target: 'positive' | 'negative') => {
    if (!checkpointTemplates) return
    if (target === 'positive') {
      const template = findPromptTemplate(
        checkpointTemplates.positive_templates,
        activePositiveTemplateId,
      )
      if (!template) return
      setPrompt((prev) =>
        templateApplyMode === 'replace'
          ? template.text
          : appendTemplateText(prev, template.text),
      )
      return
    }
    const template = findPromptTemplate(
      checkpointTemplates.negative_templates,
      activeNegativeTemplateId,
    )
    if (!template) return
    setNegativePrompt((prev) =>
      templateApplyMode === 'replace'
        ? template.text
        : appendTemplateText(prev, template.text),
    )
  }

  const applyBothPromptTemplates = () => {
    applyPromptTemplate('positive')
    applyPromptTemplate('negative')
  }

  const buildData = (): GenerationCreate => ({
    prompt,
    negative_prompt: negativePrompt || null,
    checkpoint,
    loras,
    seed: seed ? parseInt(seed, 10) : null,
    steps,
    cfg,
    width,
    height,
    sampler,
    scheduler,
    clip_skip: clipSkip ? parseInt(clipSkip, 10) : null,
    tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : null,
    notes: notes || null,
    preset_id: selectedPresetId || null,
    source_id: sourceId,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const normalizedBatchCount = Number.isFinite(batchCount)
      ? Math.max(1, Math.min(24, Math.floor(batchCount)))
      : 1
    onSubmit({
      generation: buildData(),
      batchCount: normalizedBatchCount,
    })
  }

  const clearLoadedGeneration = () => {
    setPrompt('')
    setNegativePrompt('')
    setCheckpoint('')
    setLoras([])
    setSelectedMoods([])
    setSteps(28)
    setCfg(7.0)
    setWidth(832)
    setHeight(1216)
    setSampler('euler')
    setScheduler('normal')
    setSeed('')
    setClipSkip('')
    setTags('')
    setNotes('')
    setSelectedPresetId('')
    setSourceId(null)
    setBatchCount(1)
    setAppliedQualityProfile('')
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {sourceId && (
        <div className="bg-violet-900/20 border border-violet-700/40 rounded-xl p-3 flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-violet-300">
            Loaded from generation <span className="font-mono">{sourceId}</span>
          </p>
          <button
            type="button"
            onClick={clearLoadedGeneration}
            className="text-xs px-2.5 py-1.5 rounded-md bg-gray-800 hover:bg-gray-700 text-gray-200 transition-colors duration-200"
          >
            Clear
          </button>
        </div>
      )}

      {/* Preset selector */}
      {presets && presets.length > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">Load Preset</label>
          <select
            value={selectedPresetId}
            onChange={(e) => handlePresetSelect(e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          >
            <option value="">-- Select preset --</option>
            {presets.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      )}

      {/* Checkpoint */}
      <div>
        <div className="flex flex-col items-start gap-2 mb-1.5 sm:flex-row sm:items-center sm:justify-between">
          <label className="block text-sm font-medium text-gray-300">Checkpoint</label>
          <label className="inline-flex items-center gap-2 text-xs text-gray-400">
            <input
              type="checkbox"
              checked={autoQualityProfile}
              onChange={(e) => {
                const nextValue = e.target.checked
                setAutoQualityProfile(nextValue)
                if (nextValue && checkpoint) {
                  applyQualityProfile(checkpoint)
                }
              }}
              className="rounded border-gray-600 bg-gray-700 text-violet-500 focus:ring-violet-500 focus:ring-offset-0"
            />
            Auto quality profile
          </label>
        </div>
        <select
          value={checkpoint}
          onChange={(e) => {
            const nextCheckpoint = e.target.value
            setCheckpoint(nextCheckpoint)
            if (autoQualityProfile && nextCheckpoint) {
              applyQualityProfile(nextCheckpoint)
            } else if (!autoQualityProfile && nextCheckpoint) {
              setAppliedQualityProfile('')
            }
          }}
          required
          className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
        >
          <option value="">-- Select checkpoint --</option>
          {models?.checkpoints.map((cp) => (
            <option key={cp} value={cp}>{cp}</option>
          ))}
        </select>
        <div className="mt-2 flex flex-col items-start gap-1.5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-gray-500">
            {appliedQualityProfile
              ? `Applied profile: ${appliedQualityProfile}`
              : 'No profile applied'}
          </p>
          {!autoQualityProfile && checkpoint && (
            <button
              type="button"
              onClick={() => applyQualityProfile(checkpoint)}
              className="text-xs text-violet-400 hover:text-violet-300 transition-colors duration-200"
            >
              Apply profile now
            </button>
          )}
        </div>
      </div>

      {/* Batch generation */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1.5">Batch Count</label>
        <input
          type="number"
          min={1}
          max={24}
          step={1}
          value={batchCount}
          onChange={(e) => {
            const parsed = Number.parseInt(e.target.value || '1', 10)
            if (Number.isNaN(parsed)) {
              setBatchCount(1)
              return
            }
            setBatchCount(Math.max(1, Math.min(24, parsed)))
          }}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
        />
        <p className="mt-1 text-xs text-gray-500">
          2+ 입력 시 seed가 자동으로 1씩 증가하며 N장 큐잉됩니다.
        </p>
      </div>

      {/* Prompt */}
      {checkpointTemplates && (
        <div className="rounded-xl border border-cyan-700/40 bg-cyan-900/10 p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-medium text-cyan-200">Model Prompt Templates</p>
              <p className="text-xs text-cyan-300/80 mt-0.5">
                Architecture: {checkpointTemplates.architecture}
              </p>
            </div>
            <div className="flex w-full items-center gap-2 sm:w-auto">
              <label className="text-xs text-cyan-200">Apply mode</label>
              <select
                value={templateApplyMode}
                onChange={(e) => setTemplateApplyMode(e.target.value as TemplateApplyMode)}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-2.5 py-1.5 text-xs focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none sm:flex-none"
              >
                <option value="replace">Replace</option>
                <option value="append">Append</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-xs text-cyan-200 block">Positive Template</label>
              <select
                value={activePositiveTemplateId}
                onChange={(e) => setSelectedPositiveTemplateId(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none"
              >
                {checkpointTemplates.positive_templates.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.name}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-cyan-300/80 min-h-[2rem]">
                {findPromptTemplate(
                  checkpointTemplates.positive_templates,
                  activePositiveTemplateId,
                )?.description ?? 'Select a positive template'}
              </p>
              <button
                type="button"
                onClick={() => applyPromptTemplate('positive')}
                className="text-xs px-3 py-1.5 rounded-lg border border-cyan-500/50 text-cyan-200 hover:bg-cyan-600/20 transition-colors"
              >
                Apply Positive
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-xs text-cyan-200 block">Negative Template</label>
              <select
                value={activeNegativeTemplateId}
                onChange={(e) => setSelectedNegativeTemplateId(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 focus:outline-none"
              >
                {checkpointTemplates.negative_templates.map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.name}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-cyan-300/80 min-h-[2rem]">
                {findPromptTemplate(
                  checkpointTemplates.negative_templates,
                  activeNegativeTemplateId,
                )?.description ?? 'Select a negative template'}
              </p>
              <button
                type="button"
                onClick={() => applyPromptTemplate('negative')}
                className="text-xs px-3 py-1.5 rounded-lg border border-cyan-500/50 text-cyan-200 hover:bg-cyan-600/20 transition-colors"
              >
                Apply Negative
              </button>
            </div>
          </div>

          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
            <button
              type="button"
              onClick={applyBothPromptTemplates}
              className="text-xs px-3 py-1.5 rounded-lg bg-cyan-600/20 border border-cyan-500/60 text-cyan-100 hover:bg-cyan-600/30 transition-colors"
            >
              Apply Both Templates
            </button>
            <div className="text-[11px] text-cyan-200/90 break-words">
              {promptTemplates?.variables
                .map((item) => `${item.token}=${item.example}`)
                .join(' · ')}
            </div>
          </div>
          <div className="space-y-1">
            {checkpointTemplates.guidance.map((line) => (
              <p key={line} className="text-[11px] text-cyan-200/80">
                - {line}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Prompt */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1.5">Prompt</label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          required
          rows={6}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none resize-y"
          placeholder="Describe the image you want to generate..."
        />
      </div>

      {/* Negative prompt */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1.5">Negative Prompt</label>
        <textarea
          value={negativePrompt}
          onChange={(e) => setNegativePrompt(e.target.value)}
          rows={3}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none resize-y"
          placeholder="Things to exclude from the generation..."
        />
      </div>

      {/* Mood chips */}
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-1.5">Mood</label>
        <div className="flex flex-wrap gap-2">
          {MOODS.map((mood) => (
            <button
              key={mood}
              type="button"
              onClick={() => toggleMood(mood)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                selectedMoods.includes(mood)
                  ? 'bg-violet-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-gray-200 hover:bg-gray-700'
              }`}
            >
              {mood}
            </button>
          ))}
        </div>
      </div>

      {/* LoRA selector */}
      <LoraSelector
        selected={loras}
        onChange={setLoras}
        moods={selectedMoods}
        checkpoint={checkpoint}
      />

      {/* Tags */}
      <div>
        <div className="flex flex-wrap items-center gap-2 mb-1.5">
          <label className="text-sm font-medium text-gray-300">Tags</label>
          <span className="text-xs text-gray-500">(Gallery filtering &amp; classification)</span>
        </div>
        <input
          type="text"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          placeholder="series-a, cyberpunk, sns-post, favorite"
        />
        <p className="mt-1 text-xs text-gray-600">
          Series: series-a~e | Purpose: sns-post, test, portfolio | Quality: favorite, redo | Platform: twitter, pixiv
        </p>
      </div>

      {/* Notes */}
      <div>
        <div className="flex flex-wrap items-center gap-2 mb-1.5">
          <label className="text-sm font-medium text-gray-300">Notes</label>
          <span className="text-xs text-gray-500">(Free text memo for this generation)</span>
        </div>
        <input
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
          placeholder="e.g. Twitter reaction good (200+ likes), good pose at this seed"
        />
      </div>

      {/* Advanced settings toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-200 transition-colors duration-200"
      >
        <svg
          className={`w-4 h-4 transition-transform duration-200 ${showAdvanced ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        Advanced Settings
      </button>

      {showAdvanced && (
        <div className="space-y-4 pl-3 md:pl-4 border-l-2 border-gray-800">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Steps */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Steps</label>
              <input
                type="number"
                min={1}
                max={150}
                value={steps}
                onChange={(e) => setSteps(parseInt(e.target.value || '28', 10))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>

            {/* CFG Scale */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">CFG Scale</label>
              <input
                type="number"
                min={1.0}
                max={30.0}
                step={0.5}
                value={cfg}
                onChange={(e) => setCfg(parseFloat(e.target.value || '7.0'))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>

            {/* Width */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Width</label>
              <input
                type="number"
                value={width}
                onChange={(e) => setWidth(parseInt(e.target.value, 10))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>

            {/* Height */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Height</label>
              <input
                type="number"
                value={height}
                onChange={(e) => setHeight(parseInt(e.target.value, 10))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>

            {/* Sampler */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Sampler</label>
              <select
                value={sampler}
                onChange={(e) => setSampler(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              >
                {(models?.samplers ?? ['euler', 'euler_ancestral', 'dpmpp_2m', 'dpmpp_sde']).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            {/* Scheduler */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Scheduler</label>
              <select
                value={scheduler}
                onChange={(e) => setScheduler(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              >
                {(models?.schedulers ?? ['normal', 'karras', 'exponential', 'sgm_uniform']).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Seed */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Seed</label>
            <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center">
              <input
                type="number"
                value={seed}
                min={-1}
                step={1}
                onChange={(e) => setSeed(e.target.value)}
                className="flex-1 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                placeholder="Random (empty or -1)"
              />
              <button
                type="button"
                onClick={randomizeSeed}
                className="w-full bg-gray-800 border border-gray-700 hover:bg-gray-700 text-gray-200 rounded-lg p-2 transition-colors duration-200 sm:w-auto"
                title="Generate random seed"
                aria-label="Generate random seed"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <rect x="5" y="5" width="14" height="14" rx="2" />
                  <circle cx="9" cy="9" r="1" />
                  <circle cx="15" cy="9" r="1" />
                  <circle cx="9" cy="15" r="1" />
                  <circle cx="15" cy="15" r="1" />
                </svg>
              </button>
            </div>
          </div>

          {/* Clip Skip */}
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">Clip Skip</label>
            <input
              type="number"
              value={clipSkip}
              min={1}
              max={12}
              step={1}
              onChange={(e) => setClipSkip(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              placeholder="Disabled (empty)"
            />
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:items-center">
        {onSavePreset && (
          <button
            type="button"
            onClick={() => onSavePreset(buildData())}
            className="w-full bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2.5 text-sm font-medium transition-colors duration-200 sm:w-auto"
          >
            Save as Preset
          </button>
        )}
        <button
          type="submit"
          disabled={isSubmitting || !prompt || !checkpoint}
          className="w-full bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg px-6 py-2.5 text-sm font-medium transition-colors duration-200 sm:flex-1"
        >
          {isSubmitting ? 'Submitting...' : submitLabel}
        </button>
      </div>
    </form>
  )
}
