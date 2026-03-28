import type { FormEvent, ReactNode } from 'react'

import type {
  StoryPlannerCatalog,
  StoryPlannerLane,
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
  isPlanning: boolean
  onStoryPromptChange: (value: string) => void
  onLaneChange: (value: StoryPlannerLane) => void
  onUseRegistryCharactersChange: (value: boolean) => void
  onLeadCharacterIdChange: (value: string) => void
  onSupportCharacterIdChange: (value: string) => void
  onSubmit: () => void
}

export default function StoryPlannerInputPanel({
  catalog,
  storyPrompt,
  lane,
  useRegistryCharacters,
  leadCharacterId,
  supportCharacterId,
  isPlanning,
  onStoryPromptChange,
  onLaneChange,
  onUseRegistryCharactersChange,
  onLeadCharacterIdChange,
  onSupportCharacterIdChange,
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

            {useRegistryCharacters ? (
              <div className="grid gap-4">
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
                </label>

                {catalog?.characters.length ? (
                  <p className="text-xs leading-5 text-gray-500">
                    Registry options are loaded from the Story Planner catalog.
                  </p>
                ) : null}
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-gray-800 bg-gray-950/70 px-4 py-5 text-sm text-gray-400">
                Registry characters are optional. Keep this off if you want the planner to resolve the episode from the story prompt alone.
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
