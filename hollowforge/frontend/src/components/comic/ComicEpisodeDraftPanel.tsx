import type {
  ComicCharacterResponse,
  ComicCharacterVersionResponse,
} from '../../api/client'

interface ComicEpisodeDraftPanelProps {
  characters: ComicCharacterResponse[]
  characterVersions: ComicCharacterVersionResponse[]
  selectedCharacterId: string | null
  selectedCharacterVersionId: string | null
  title: string
  panelMultiplier: number
  approvedPlanJson: string
  productionContext?: {
    productionEpisodeId: string
    workId: string
    seriesId: string | null
    contentMode: string
  } | null
  canImport: boolean
  importValidationMessage: string | null
  isLoadingCatalog: boolean
  isImporting: boolean
  onCharacterChange: (characterId: string) => void
  onCharacterVersionChange: (characterVersionId: string) => void
  onTitleChange: (title: string) => void
  onPanelMultiplierChange: (panelMultiplier: number) => void
  onApprovedPlanJsonChange: (approvedPlanJson: string) => void
  onImport: () => void
}

export default function ComicEpisodeDraftPanel({
  characters,
  characterVersions,
  selectedCharacterId,
  selectedCharacterVersionId,
  title,
  panelMultiplier,
  approvedPlanJson,
  productionContext = null,
  canImport,
  importValidationMessage,
  isLoadingCatalog,
  isImporting,
  onCharacterChange,
  onCharacterVersionChange,
  onTitleChange,
  onPanelMultiplierChange,
  onApprovedPlanJsonChange,
  onImport,
}: ComicEpisodeDraftPanelProps) {
  return (
    <section className="space-y-5 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="space-y-2">
        <span className="inline-flex rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-violet-300">
          Episode Intake
        </span>
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Story Plan Import</h2>
          <p className="mt-1 text-sm text-gray-400">
            Bring one approved Story Planner payload into Comic Studio, bind it to a character version, and keep the rest of the workflow scoped to that episode.
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2 text-sm text-gray-300">
          <span className="font-medium text-gray-200">Character</span>
          <select
            value={selectedCharacterId ?? ''}
            onChange={(event) => onCharacterChange(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950/70 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500/50"
          >
            <option value="">Select a character</option>
            {characters.map((character) => (
              <option key={character.id} value={character.id}>
                {character.name}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span className="font-medium text-gray-200">Character Version</span>
          <select
            value={selectedCharacterVersionId ?? ''}
            onChange={(event) => onCharacterVersionChange(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950/70 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500/50"
          >
            <option value="">Select a version</option>
            {characterVersions.map((version) => (
              <option key={version.id} value={version.id}>
                {version.version_name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_160px]">
        <label className="space-y-2 text-sm text-gray-300">
          <span className="font-medium text-gray-200">Episode Title</span>
          <input
            type="text"
            value={title}
            onChange={(event) => onTitleChange(event.target.value)}
            className="w-full rounded-xl border border-gray-700 bg-gray-950/70 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500/50"
            placeholder="After Hours Intake"
          />
        </label>

        <label className="space-y-2 text-sm text-gray-300">
          <span className="font-medium text-gray-200">Panel Multiplier</span>
          <input
            type="number"
            min={1}
            max={8}
            value={panelMultiplier}
            onChange={(event) => onPanelMultiplierChange(Number(event.target.value))}
            className="w-full rounded-xl border border-gray-700 bg-gray-950/70 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500/50"
          />
        </label>
      </div>

      <label className="block space-y-2 text-sm text-gray-300">
        <span className="font-medium text-gray-200">Approved Story Plan JSON</span>
        <textarea
          value={approvedPlanJson}
          onChange={(event) => onApprovedPlanJsonChange(event.target.value)}
          rows={12}
          spellCheck={false}
          className="min-h-[240px] w-full rounded-2xl border border-gray-700 bg-gray-950/80 px-4 py-3 font-mono text-xs leading-6 text-gray-100 outline-none transition focus:border-violet-500/50"
        />
      </label>

      {productionContext && (
        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-3 text-xs text-cyan-100">
          <p className="font-semibold uppercase tracking-wide text-cyan-200">Production Episode Context</p>
          <div className="mt-1 space-y-1 text-cyan-50/90">
            <p>Production Episode: {productionContext.productionEpisodeId}</p>
            <p>Work: {productionContext.workId}</p>
            <p>Series: {productionContext.seriesId ?? 'none'}</p>
            <p>Content Mode: {productionContext.contentMode}</p>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="rounded-xl border border-gray-800 bg-gray-950/60 px-4 py-3 text-xs text-gray-400">
          <p className="font-medium uppercase tracking-wide text-gray-500">Import Contract</p>
          <p className="mt-1">Character, version, episode title, and approved plan all stay visible in the lineage chain.</p>
        </div>
        <button
          type="button"
          onClick={onImport}
          disabled={!canImport || isImporting}
          className="rounded-xl border border-violet-500/40 bg-violet-500/10 px-4 py-2.5 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isImporting ? 'Importing...' : 'Import Story Plan'}
        </button>
      </div>

      {importValidationMessage && (
        <p className="text-xs text-amber-200/80">{importValidationMessage}</p>
      )}

      {isLoadingCatalog && (
        <p className="text-xs text-gray-500">Loading character catalog...</p>
      )}
    </section>
  )
}
