import EmptyState from '../EmptyState'
import type {
  ComicPanelDialogueResponse,
  ComicScenePanelResponse,
} from '../../api/client'

interface ComicDialogueEditorProps {
  episodeTitle: string | null
  sceneNo: number | null
  selectedPanel: ComicScenePanelResponse | null
  characterName: string | null
  characterVersionName: string | null
  dialogues: ComicPanelDialogueResponse[]
  canGenerate: boolean
  readinessMessage: string | null
  isGenerating: boolean
  onGenerate: (panelId: string) => void
}

const DIALOGUE_TYPE_LABELS: Record<string, string> = {
  speech: 'Speech',
  thought: 'Thought',
  caption: 'Caption',
  sfx: 'SFX',
}

export default function ComicDialogueEditor({
  episodeTitle,
  sceneNo,
  selectedPanel,
  characterName,
  characterVersionName,
  dialogues,
  canGenerate,
  readinessMessage,
  isGenerating,
  onGenerate,
}: ComicDialogueEditorProps) {
  return (
    <section className="space-y-5 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="space-y-2">
        <span className="inline-flex rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-amber-300">
          Dialogue Drafting
        </span>
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Panel Dialogue Editor</h2>
          <p className="mt-1 text-sm text-gray-400">
            Draft speech, caption, and SFX lines against the currently selected panel without losing the episode lineage context.
          </p>
        </div>
      </div>

      {selectedPanel ? (
        <>
          <div className="grid gap-3 rounded-2xl border border-gray-800 bg-gray-950/60 p-4 text-sm text-gray-300 md:grid-cols-2 xl:grid-cols-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Character</p>
              <p className="mt-1 font-medium text-gray-100">{characterName ?? 'Unresolved character'}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Character Version</p>
              <p className="mt-1 font-medium text-gray-100">{characterVersionName ?? 'Unresolved version'}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Episode</p>
              <p className="mt-1 font-medium text-gray-100">{episodeTitle ?? 'No episode loaded'}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500">Scene / Panel</p>
              <p className="mt-1 font-medium text-gray-100">
                Scene {sceneNo ?? 'n/a'} / Panel {selectedPanel.panel_no}
              </p>
            </div>
          </div>

          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-medium text-gray-100">Dialogue Intent</p>
              <p className="mt-1 text-sm text-gray-400">
                {selectedPanel.dialogue_intent ?? 'No explicit dialogue intent was supplied for this panel.'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onGenerate(selectedPanel.id)}
              disabled={!canGenerate || isGenerating}
              className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-2.5 text-sm font-medium text-amber-200 transition hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isGenerating ? 'Generating...' : 'Generate Dialogues'}
            </button>
          </div>

          {readinessMessage && (
            <p className="text-xs text-amber-200/80">{readinessMessage}</p>
          )}

          {dialogues.length > 0 ? (
            <div className="space-y-3">
              {dialogues.map((dialogue) => (
                <article key={dialogue.id} className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-gray-300">
                      {DIALOGUE_TYPE_LABELS[dialogue.type] ?? dialogue.type}
                    </span>
                    <span className="text-xs text-gray-500">
                      Priority {dialogue.priority}
                    </span>
                    {dialogue.speaker_character_id && (
                      <span className="text-xs text-gray-500">
                        Speaker {dialogue.speaker_character_id}
                      </span>
                    )}
                  </div>
                  <p className="mt-3 text-sm leading-6 text-gray-100">{dialogue.text}</p>
                  {(dialogue.balloon_style_hint || dialogue.placement_hint || dialogue.tone) && (
                    <p className="mt-3 text-xs text-gray-500">
                      {dialogue.tone ? `Tone ${dialogue.tone}` : null}
                      {dialogue.tone && (dialogue.balloon_style_hint || dialogue.placement_hint) ? ' · ' : null}
                      {dialogue.balloon_style_hint ? `Balloon ${dialogue.balloon_style_hint}` : null}
                      {dialogue.balloon_style_hint && dialogue.placement_hint ? ' · ' : null}
                      {dialogue.placement_hint ? `Placement ${dialogue.placement_hint}` : null}
                    </p>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No dialogue rows yet"
              description="Generate panel dialogue to materialize speech, caption, and SFX rows for the currently selected panel."
            />
          )}
        </>
      ) : (
        <EmptyState
          title="Select a panel first"
          description="Dialogue drafting stays pinned to one panel at a time so character, scene, and panel lineage remain explicit."
        />
      )}
    </section>
  )
}
