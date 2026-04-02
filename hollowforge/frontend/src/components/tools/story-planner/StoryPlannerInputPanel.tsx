import type { FormEvent, ReactNode } from 'react'

import type {
  StoryPlannerCatalog,
  StoryPlannerLane,
  StoryPlannerPreferredAnchorBeat,
} from '../../../api/client'

const LANE_OPTIONS: Array<{
  value: StoryPlannerLane
  label: string
  description: string
}> = [
  {
    value: 'unrestricted',
    label: 'Unrestricted',
    description: 'Keep the episode broad and surface lane-sensitive beats explicitly.',
  },
  {
    value: 'all_ages',
    label: 'All Ages',
    description: 'Keep the episode suitable for a general audience.',
  },
  {
    value: 'adult_nsfw',
    label: 'Adult NSFW',
    description: 'Preserve adult-only continuity and keep consent logic explicit.',
  },
]

const PREFERRED_ANCHOR_BEAT_OPTIONS: Array<{
  value: StoryPlannerPreferredAnchorBeat
  label: string
  description: string
}> = [
  {
    value: 'auto',
    label: 'Auto',
    description: 'Let the planner choose the strongest anchor beat.',
  },
  {
    value: 'exchange',
    label: 'Exchange',
    description: 'Prefer the beat where the lead and support exchange.',
  },
  {
    value: 'reveal',
    label: 'Reveal',
    description: 'Prefer the beat where the key detail is revealed.',
  },
  {
    value: 'decision',
    label: 'Decision',
    description: 'Prefer the beat where the scene closes on a choice.',
  },
]

const SUPPORT_LOCK_MODE_OPTIONS: Array<{
  value: 'unlocked' | 'registry' | 'freeform'
  label: string
  description: string
}> = [
  {
    value: 'unlocked',
    label: 'Unlocked',
    description: 'Leave support unspecified and let the planner infer it from the prompt.',
  },
  {
    value: 'registry',
    label: 'Registry',
    description: 'Bind support to a catalog character.',
  },
  {
    value: 'freeform',
    label: 'Freeform',
    description: 'Describe support directly with a short freeform note.',
  },
]

function StoryPlannerSection({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="rounded-3xl border border-white/10 bg-gray-950/90 p-6 shadow-2xl shadow-black/20">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        <span className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-violet-100">
          Story Planner
        </span>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  )
}

export interface StoryPlannerInputPanelProps {
  catalog: StoryPlannerCatalog | null
  storyPrompt: string
  lane: StoryPlannerLane
  useRegistryCharacters: boolean
  leadCharacterId: string
  supportCharacterId: string
  locationId: string
  preferredAnchorBeat: StoryPlannerPreferredAnchorBeat
  supportLockMode: 'unlocked' | 'registry' | 'freeform'
  supportFreeformDescription: string
  isPlanning: boolean
  onStoryPromptChange: (value: string) => void
  onLaneChange: (value: StoryPlannerLane) => void
  onUseRegistryCharactersChange: (value: boolean) => void
  onLeadCharacterIdChange: (value: string) => void
  onSupportCharacterIdChange: (value: string) => void
  onLocationIdChange: (value: string) => void
  onPreferredAnchorBeatChange: (value: StoryPlannerPreferredAnchorBeat) => void
  onSupportLockModeChange: (value: 'unlocked' | 'registry' | 'freeform') => void
  onSupportFreeformDescriptionChange: (value: string) => void
  onSubmit: () => void
}

export default function StoryPlannerInputPanel({
  catalog,
  storyPrompt,
  lane,
  useRegistryCharacters,
  leadCharacterId,
  supportCharacterId,
  locationId,
  preferredAnchorBeat,
  supportLockMode,
  supportFreeformDescription,
  isPlanning,
  onStoryPromptChange,
  onLaneChange,
  onUseRegistryCharactersChange,
  onLeadCharacterIdChange,
  onSupportCharacterIdChange,
  onLocationIdChange,
  onPreferredAnchorBeatChange,
  onSupportLockModeChange,
  onSupportFreeformDescriptionChange,
  onSubmit,
}: StoryPlannerInputPanelProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onSubmit()
  }

  return (
    <StoryPlannerSection title="Story Prompt">
      <form className="space-y-6" onSubmit={handleSubmit}>
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,0.95fr)]">
          <label className="block space-y-2">
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm font-medium text-gray-100">Story Prompt</span>
              <span className="text-xs text-gray-500">{storyPrompt.length}/2000</span>
            </div>
            <textarea
              aria-label="Story Prompt"
              value={storyPrompt}
              onChange={(event) => onStoryPromptChange(event.target.value)}
              rows={9}
              className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm leading-6 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
              placeholder="Describe the episode, the tone, and the main tension you want the planner to resolve."
            />
            <p className="text-xs leading-5 text-gray-500">
              Freeform story prompt first. The planner will resolve the location, cast, and shot deck from this text.
            </p>
          </label>

          <div className="space-y-4">
            <label className="block space-y-2">
              <span className="text-sm font-medium text-gray-100">Lane</span>
              <select
                aria-label="Lane"
                value={lane}
                onChange={(event) => onLaneChange(event.target.value as StoryPlannerLane)}
                className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
              >
                {LANE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="text-xs leading-5 text-gray-500">
                {LANE_OPTIONS.find((option) => option.value === lane)?.description}
              </p>
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-medium text-gray-100">Location Lock</span>
              <select
                aria-label="Location Lock"
                value={locationId}
                onChange={(event) => onLocationIdChange(event.target.value)}
                className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
              >
                <option value="">Auto resolve from prompt</option>
                {catalog?.locations.map((location) => (
                  <option key={location.id} value={location.id}>
                    {location.name}
                  </option>
                ))}
              </select>
              <p className="text-xs leading-5 text-gray-500">
                Optional hard lock. Leave this blank to let the planner resolve the location from the story prompt.
              </p>
            </label>

            <label className="block space-y-2">
              <span className="text-sm font-medium text-gray-100">Preferred Anchor Beat</span>
              <select
                aria-label="Preferred Anchor Beat"
                value={preferredAnchorBeat}
                onChange={(event) =>
                  onPreferredAnchorBeatChange(event.target.value as StoryPlannerPreferredAnchorBeat)
                }
                className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
              >
                {PREFERRED_ANCHOR_BEAT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="text-xs leading-5 text-gray-500">
                {PREFERRED_ANCHOR_BEAT_OPTIONS.find((option) => option.value === preferredAnchorBeat)?.description}
              </p>
            </label>

            <button
              type="button"
              onClick={() => onUseRegistryCharactersChange(!useRegistryCharacters)}
              className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${
                useRegistryCharacters
                  ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
                  : 'border-gray-800 bg-gray-950 text-gray-300 hover:border-gray-600 hover:text-white'
              }`}
            >
              <div>
                <div className="text-sm font-semibold">Use Registry Characters</div>
                <div className="mt-1 text-xs leading-5 text-gray-400">
                  {useRegistryCharacters
                    ? 'On. Lead and support will resolve from the registry catalog.'
                    : 'Off. The planner will work from the freeform story prompt only.'}
                </div>
              </div>
              <div className={`h-6 w-11 rounded-full p-1 transition ${useRegistryCharacters ? 'bg-violet-500/30' : 'bg-gray-800'}`}>
                <div className={`h-4 w-4 rounded-full bg-white transition ${useRegistryCharacters ? 'translate-x-5' : 'translate-x-0'}`} />
              </div>
            </button>

            <label className="block space-y-2">
              <span className="text-sm font-medium text-gray-100">Support Lock Mode</span>
              <select
                aria-label="Support Lock Mode"
                value={supportLockMode}
                onChange={(event) =>
                  onSupportLockModeChange(event.target.value as 'unlocked' | 'registry' | 'freeform')
                }
                className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
              >
                {SUPPORT_LOCK_MODE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <p className="text-xs leading-5 text-gray-500">
                {SUPPORT_LOCK_MODE_OPTIONS.find((option) => option.value === supportLockMode)?.description}
              </p>
            </label>

            {useRegistryCharacters || supportLockMode !== 'unlocked' ? (
              <div className="grid gap-4">
                {useRegistryCharacters ? (
                  <label className="block space-y-2">
                    <span className="text-sm font-medium text-gray-100">Lead Character</span>
                    <select
                      aria-label="Lead Character"
                      value={leadCharacterId}
                      onChange={(event) => onLeadCharacterIdChange(event.target.value)}
                      className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                    >
                      <option value="">Select lead character</option>
                      {catalog?.characters.map((character) => (
                        <option key={character.id} value={character.id}>
                          {character.name}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : (
                  <div className="rounded-2xl border border-dashed border-gray-800 bg-gray-950/70 px-4 py-4 text-xs leading-5 text-gray-500">
                    Lead stays unlocked, but support can still be locked or described directly.
                  </div>
                )}

                {supportLockMode === 'registry' ? (
                  <label className="block space-y-2">
                    <span className="text-sm font-medium text-gray-100">Support Character</span>
                    <select
                      aria-label="Support Character"
                      value={supportCharacterId}
                      onChange={(event) => onSupportCharacterIdChange(event.target.value)}
                      className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                    >
                      <option value="">Select support character</option>
                      {catalog?.characters.map((character) => (
                        <option key={character.id} value={character.id}>
                          {character.name}
                        </option>
                      ))}
                    </select>
                    {catalog?.characters.length ? (
                      <p className="text-xs leading-5 text-gray-500">
                        Registry support options are loaded from the Story Planner catalog.
                      </p>
                    ) : null}
                  </label>
                ) : supportLockMode === 'freeform' ? (
                  <label className="block space-y-2">
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-sm font-medium text-gray-100">Support Freeform Description</span>
                      <span className="text-xs text-gray-500">{supportFreeformDescription.length}/200</span>
                    </div>
                    <textarea
                      aria-label="Support Freeform Description"
                      value={supportFreeformDescription}
                      onChange={(event) => onSupportFreeformDescriptionChange(event.target.value)}
                      rows={4}
                      className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm leading-6 text-gray-100 outline-none transition placeholder:text-gray-600 focus:border-violet-500"
                      placeholder="Describe the support role in one short phrase."
                    />
                    <p className="text-xs leading-5 text-gray-500">
                      Freeform support text is trimmed before serialization.
                    </p>
                  </label>
                ) : null}

                {useRegistryCharacters ? (
                  <p className="text-xs leading-5 text-gray-500">
                    Registry options are loaded from the Story Planner catalog.
                  </p>
                ) : null}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-gray-800 bg-gray-950/70 px-4 py-5 text-sm text-gray-400">
                Lead and support stay unlocked. The planner will work from the story prompt and optional guidance only.
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="submit"
            disabled={isPlanning || storyPrompt.trim().length === 0}
            className="rounded-2xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPlanning ? 'Planning...' : 'Plan Episode'}
          </button>
          <p className="text-xs leading-5 text-gray-500">
            The planner will return the episode brief, cast resolution, location, and four-shot plan.
          </p>
        </div>
      </form>
    </StoryPlannerSection>
  )
}
