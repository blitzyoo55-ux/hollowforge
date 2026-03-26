import { useMemo, useState } from 'react'
import type { SequenceBlueprintCreate, SequenceContentMode } from '../api/client'

interface SequenceBlueprintFormProps {
  onSubmit: (payload: SequenceBlueprintCreate) => void
  isSubmitting?: boolean
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
    description: 'Lane-separated adult orchestration controls. Stage 1 grammar is not registered yet.',
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
      description: 'Reserved adult policy lane for future Stage 1 parity.',
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
  adult_nsfw: [],
}

function selectDefault(options: ModeOption[]): string {
  return options[0]?.value ?? ''
}

export default function SequenceBlueprintForm({
  onSubmit,
  isSubmitting = false,
}: SequenceBlueprintFormProps) {
  const [contentMode, setContentMode] = useState<SequenceContentMode>('all_ages')
  const [policyProfileId, setPolicyProfileId] = useState(selectDefault(POLICY_OPTIONS.all_ages))
  const [executorPolicy, setExecutorPolicy] = useState(selectDefault(EXECUTOR_OPTIONS.all_ages))
  const [beatGrammarId, setBeatGrammarId] = useState(selectDefault(BEAT_GRAMMAR_OPTIONS.all_ages))
  const [characterId, setCharacterId] = useState('char_stage1')
  const [locationId, setLocationId] = useState('location_stage1')
  const [targetDurationSec, setTargetDurationSec] = useState('36')
  const [shotCount, setShotCount] = useState('6')
  const [tone, setTone] = useState('tense')

  const policyOptions = useMemo(() => POLICY_OPTIONS[contentMode], [contentMode])
  const executorOptions = useMemo(() => EXECUTOR_OPTIONS[contentMode], [contentMode])
  const beatGrammarOptions = useMemo(() => BEAT_GRAMMAR_OPTIONS[contentMode], [contentMode])

  const activeMode = CONTENT_MODE_OPTIONS.find((option) => option.value === contentMode)
  const activeExecutor = executorOptions.find((option) => option.value === executorPolicy)
  const activeBeatGrammar = beatGrammarOptions.find((option) => option.value === beatGrammarId)
  const canSubmit = Boolean(policyProfileId && executorPolicy && beatGrammarId && characterId.trim() && locationId.trim())

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
            disabled={beatGrammarOptions.length === 0}
            className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2.5 text-gray-100 outline-none transition focus:border-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {beatGrammarOptions.length > 0 ? (
              beatGrammarOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))
            ) : (
              <option value="">No Stage 1 grammar registered</option>
            )}
          </select>
          {activeBeatGrammar ? (
            <p className="text-xs text-gray-500">{activeBeatGrammar.description}</p>
          ) : (
            <p className="text-xs text-amber-300">
              Stage 1 currently exposes only the safe single-location grammar.
            </p>
          )}
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
