import { useEffect, useMemo, useState } from 'react'
import type { SequenceBlueprintCreate, SequenceContentMode } from '../api/client'

interface SequenceBlueprintFormProps {
  onSubmit: (payload: SequenceBlueprintCreate) => void
  isSubmitting?: boolean
  initialValues?: Partial<SequenceBlueprintCreate>
  productionContextLabel?: string | null
}

interface ModeOption {
  value: string
  label: string
  description: string
}

const CONTENT_MODE_OPTIONS: Array<{ value: SequenceContentMode; label: string; description: string }> = [
  {
    value: 'all_ages',
    label: 'All Ages',
    description: 'Safe lane using the current Stage 1 grammar and remote-safe executor presets.',
  },
  {
    value: 'adult_nsfw',
    label: 'Adult NSFW',
    description: 'Lane-separated adult Stage 1 controls using the adult grammar and adult executor presets.',
  },
]

const POLICY_OPTIONS: Record<SequenceContentMode, ModeOption[]> = {
  all_ages: [
    {
      value: 'safe_stage1_v1',
      label: 'safe_stage1_v1',
      description: 'Default Stage 1 safe policy lane.',
    },
  ],
  adult_nsfw: [
    {
      value: 'adult_stage1_v1',
      label: 'adult_stage1_v1',
      description: 'Adult policy lane paired with the adult Stage 1 grammar.',
    },
  ],
}

const EXECUTOR_OPTIONS: Record<SequenceContentMode, ModeOption[]> = {
  all_ages: [
    {
      value: 'safe_remote_prod',
      label: 'safe_remote_prod',
      description: 'Remote worker execution for the safe lane.',
    },
    {
      value: 'safe_local_preview',
      label: 'safe_local_preview',
      description: 'Local preview executor for quick safe-lane iteration.',
    },
  ],
  adult_nsfw: [
    {
      value: 'adult_remote_prod',
      label: 'adult_remote_prod',
      description: 'Remote worker execution for the adult lane.',
    },
    {
      value: 'adult_local_preview',
      label: 'adult_local_preview',
      description: 'Local preview executor for adult-lane experiments.',
    },
  ],
}

const BEAT_GRAMMAR_OPTIONS: Record<SequenceContentMode, ModeOption[]> = {
  all_ages: [
    {
      value: 'stage1_single_location_v1',
      label: 'stage1_single_location_v1',
      description: 'Fixed six-beat grammar for the first single-location sequence slice.',
    },
  ],
  adult_nsfw: [
    {
      value: 'adult_stage1_v1',
      label: 'adult_stage1_v1',
      description: 'Fixed six-beat grammar for the adult single-location sequence slice.',
    },
  ],
}

function selectDefault(options: ModeOption[]): string {
  return options[0]?.value ?? ''
}

export default function SequenceBlueprintForm({
  onSubmit,
  isSubmitting = false,
  initialValues,
  productionContextLabel = null,
}: SequenceBlueprintFormProps) {
  const defaultContentMode = initialValues?.content_mode ?? 'all_ages'
  const [contentMode, setContentMode] = useState<SequenceContentMode>(defaultContentMode)
  const [policyProfileId, setPolicyProfileId] = useState(
    initialValues?.policy_profile_id?.trim() || selectDefault(POLICY_OPTIONS[defaultContentMode]),
  )
  const [executorPolicy, setExecutorPolicy] = useState(
    initialValues?.executor_policy?.trim() || selectDefault(EXECUTOR_OPTIONS[defaultContentMode]),
  )
  const [beatGrammarId, setBeatGrammarId] = useState(
    initialValues?.beat_grammar_id?.trim() || selectDefault(BEAT_GRAMMAR_OPTIONS[defaultContentMode]),
  )
  const [characterId, setCharacterId] = useState(initialValues?.character_id ?? 'char_stage1')
  const [locationId, setLocationId] = useState(initialValues?.location_id ?? 'location_stage1')
  const [targetDurationSec, setTargetDurationSec] = useState(String(initialValues?.target_duration_sec ?? 36))
  const [shotCount, setShotCount] = useState(String(initialValues?.shot_count ?? 6))
  const [tone, setTone] = useState(initialValues?.tone ?? 'tense')
  const [workId, setWorkId] = useState(initialValues?.work_id ?? null)
  const [seriesId, setSeriesId] = useState(initialValues?.series_id ?? null)
  const [productionEpisodeId, setProductionEpisodeId] = useState(initialValues?.production_episode_id ?? null)

  const policyOptions = useMemo(() => POLICY_OPTIONS[contentMode], [contentMode])
  const executorOptions = useMemo(() => EXECUTOR_OPTIONS[contentMode], [contentMode])
  const beatGrammarOptions = useMemo(() => BEAT_GRAMMAR_OPTIONS[contentMode], [contentMode])

  const activeMode = CONTENT_MODE_OPTIONS.find((option) => option.value === contentMode)
  const activeExecutor = executorOptions.find((option) => option.value === executorPolicy)
  const activeBeatGrammar = beatGrammarOptions.find((option) => option.value === beatGrammarId)
  const canSubmit = Boolean(policyProfileId && executorPolicy && beatGrammarId && characterId.trim() && locationId.trim())
  const hasProductionContext = Boolean(productionContextLabel || productionEpisodeId || workId || seriesId)

  useEffect(() => {
    if (!initialValues) return

    const nextMode = initialValues.content_mode ?? 'all_ages'
    setContentMode(nextMode)
    setPolicyProfileId(initialValues.policy_profile_id?.trim() || selectDefault(POLICY_OPTIONS[nextMode]))
    setExecutorPolicy(initialValues.executor_policy?.trim() || selectDefault(EXECUTOR_OPTIONS[nextMode]))
    setBeatGrammarId(initialValues.beat_grammar_id?.trim() || selectDefault(BEAT_GRAMMAR_OPTIONS[nextMode]))
    setCharacterId(initialValues.character_id ?? 'char_stage1')
    setLocationId(initialValues.location_id ?? 'location_stage1')
    setTargetDurationSec(String(initialValues.target_duration_sec ?? 36))
    setShotCount(String(initialValues.shot_count ?? 6))
    setTone(initialValues.tone ?? 'tense')
    setWorkId(initialValues.work_id ?? null)
    setSeriesId(initialValues.series_id ?? null)
    setProductionEpisodeId(initialValues.production_episode_id ?? null)
  }, [initialValues])

  const handleContentModeChange = (nextMode: SequenceContentMode) => {
    setContentMode(nextMode)
    setPolicyProfileId(selectDefault(POLICY_OPTIONS[nextMode]))
    setExecutorPolicy(selectDefault(EXECUTOR_OPTIONS[nextMode]))
    setBeatGrammarId(selectDefault(BEAT_GRAMMAR_OPTIONS[nextMode]))
  }

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!canSubmit) return

    onSubmit({
      work_id: workId?.trim() ? workId.trim() : null,
      series_id: seriesId?.trim() ? seriesId.trim() : null,
      production_episode_id: productionEpisodeId?.trim() ? productionEpisodeId.trim() : null,
      content_mode: contentMode,
      policy_profile_id: policyProfileId.trim(),
      character_id: characterId.trim(),
      location_id: locationId.trim(),
      beat_grammar_id: beatGrammarId,
      target_duration_sec: Math.max(1, Number.parseInt(targetDurationSec, 10) || 36),
      shot_count: Math.max(1, Number.parseInt(shotCount, 10) || 6),
      tone: tone.trim() || null,
      executor_policy: executorPolicy,
    })
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-5 rounded-2xl border border-gray-800 bg-gray-900/70 p-5"
    >
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-gray-100">Blueprint Builder</h2>
        <p className="text-sm text-gray-400">
          Define a reusable sequence template for the first orchestration slice.
        </p>
      </div>

      <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 px-4 py-3 text-sm text-gray-300">
        <p className="font-medium text-violet-300">{activeMode?.label}</p>
        <p className="mt-1 text-gray-400">{activeMode?.description}</p>
      </div>

      {hasProductionContext ? (
        <div className="space-y-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-gray-300">
          <p className="font-medium text-emerald-300">Production Episode Context</p>
          {productionContextLabel ? <p className="text-xs text-emerald-100">{productionContextLabel}</p> : null}
          <div className="grid gap-1 text-xs text-gray-400">
            <p>Production Episode: {productionEpisodeId ?? 'unlinked'}</p>
            <p>Work: {workId ?? 'unlinked'}</p>
            <p>Series: {seriesId ?? 'standalone'}</p>
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-gray-300">
          <span>Content Mode</span>
          <select
            aria-label="Content Mode"
            value={contentMode}
            onChange={(event) => handleContentModeChange(event.target.value as SequenceContentMode)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            {CONTENT_MODE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Executor Profile</span>
          <select
            aria-label="Executor Profile"
            value={executorPolicy}
            onChange={(event) => setExecutorPolicy(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            {executorOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {activeExecutor && <p className="text-xs text-gray-500">{activeExecutor.description}</p>}
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Policy Profile</span>
          <select
            value={policyProfileId}
            onChange={(event) => setPolicyProfileId(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            {policyOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Beat Grammar</span>
          <select
            value={beatGrammarId}
            onChange={(event) => setBeatGrammarId(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          >
            {beatGrammarOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {activeBeatGrammar && <p className="text-xs text-gray-500">{activeBeatGrammar.description}</p>}
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Character ID</span>
          <input
            value={characterId}
            onChange={(event) => setCharacterId(event.target.value)}
            placeholder="char_stage1"
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
          />
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Location ID</span>
          <input
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
            placeholder="location_stage1"
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
          />
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Target Duration (sec)</span>
          <input
            type="number"
            min={1}
            max={3600}
            value={targetDurationSec}
            onChange={(event) => setTargetDurationSec(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span>Shot Count</span>
          <input
            type="number"
            min={1}
            max={64}
            value={shotCount}
            onChange={(event) => setShotCount(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>
      </div>

      <label className="space-y-2 text-sm text-gray-300">
        <span>Tone</span>
        <input
          value={tone}
          onChange={(event) => setTone(event.target.value)}
          placeholder="tense"
          className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
        />
      </label>

      <div className="flex items-center justify-between gap-3 border-t border-gray-800 pt-4">
        <p className="text-xs text-gray-500">
          Blueprint creation stays lane-aware and does not cross safe and adult sequence domains.
        </p>
        <button
          type="submit"
          disabled={isSubmitting || !canSubmit}
          className="rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? 'Creating...' : 'Create Blueprint'}
        </button>
      </div>
    </form>
  )
}
