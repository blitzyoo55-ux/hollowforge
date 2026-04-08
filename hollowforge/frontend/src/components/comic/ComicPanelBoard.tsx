import EmptyState from '../EmptyState'
import type {
  ComicEpisodeDetailResponse,
  ComicPanelRenderAssetResponse,
  ComicRenderExecutionMode,
  ComicScenePanelResponse,
} from '../../api/client'

export interface ComicPanelRenderStatusSummary {
  executionMode: ComicRenderExecutionMode
  materializedAssetCount: number
  remoteJobCount: number
  pendingRemoteCount: number
  latestFailureMessage: string | null
  latestExternalJobUrl: string | null
}

interface ComicPanelBoardProps {
  episode: ComicEpisodeDetailResponse | null
  selectedPanelId: string | null
  panelAssets: Record<string, ComicPanelRenderAssetResponse[]>
  panelRenderStatuses: Record<string, ComicPanelRenderStatusSummary>
  characterName: string | null
  characterVersionName: string | null
  queueingPanelId: string | null
  queueingExecutionMode: ComicRenderExecutionMode | null
  selectingAssetId: string | null
  onSelectPanel: (panelId: string) => void
  onQueueRenders: (panelId: string, executionMode: ComicRenderExecutionMode) => void
  onSelectAsset: (panelId: string, assetId: string) => void
}

function describeSelectedAsset(assets: ComicPanelRenderAssetResponse[]): ComicPanelRenderAssetResponse | null {
  return assets.find((asset) => asset.is_selected) ?? null
}

function formatQualityScore(score: number | null): string {
  if (typeof score !== 'number') return 'n/a'
  return score.toFixed(2)
}

function panelLineage(
  panel: ComicScenePanelResponse,
  episodeTitle: string,
  sceneNo: number,
): string {
  return `${episodeTitle} / Scene ${sceneNo} / Panel ${panel.panel_no}`
}

function formatExecutionLaneLabel(executionMode: ComicRenderExecutionMode): string {
  return executionMode === 'remote_worker' ? 'Remote Production' : 'Local Preview'
}

export default function ComicPanelBoard({
  episode,
  selectedPanelId,
  panelAssets,
  panelRenderStatuses,
  characterName,
  characterVersionName,
  queueingPanelId,
  queueingExecutionMode,
  selectingAssetId,
  onSelectPanel,
  onQueueRenders,
  onSelectAsset,
}: ComicPanelBoardProps) {
  if (!episode) {
    return (
      <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
        <EmptyState
          title="No comic episode loaded"
          description="Import a Story Planner payload first. Once an episode exists, this board becomes the one-place view for scene, panel, and selected asset lineage."
        />
      </section>
    )
  }

  const selectedSceneDetail = episode.scenes.find((sceneDetail) =>
    sceneDetail.panels.some((panel) => panel.id === selectedPanelId),
  ) ?? episode.scenes[0]
  const selectedPanel = selectedSceneDetail?.panels.find((panel) => panel.id === selectedPanelId)
    ?? selectedSceneDetail?.panels[0]
    ?? null
  const selectedAssets = selectedPanel ? panelAssets[selectedPanel.id] ?? [] : []
  const selectedAsset = describeSelectedAsset(selectedAssets)
  const selectedPanelRenderStatus = selectedPanel
    ? panelRenderStatuses[selectedPanel.id] ?? {
        executionMode: 'local_preview',
        materializedAssetCount: selectedAssets.filter((asset) => Boolean(asset.storage_path)).length,
        remoteJobCount: 0,
        pendingRemoteCount: 0,
        latestFailureMessage: null,
        latestExternalJobUrl: null,
      }
    : null

  return (
    <section className="space-y-5 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-emerald-300">
            Panel Board
          </span>
          <span className="rounded-full border border-gray-700 bg-gray-950/70 px-3 py-1 text-xs text-gray-300">
            {characterName ?? episode.episode.character_id}
          </span>
          <span className="rounded-full border border-gray-700 bg-gray-950/70 px-3 py-1 text-xs text-gray-300">
            {characterVersionName ?? episode.episode.character_version_id}
          </span>
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-100">Episode lineage</h2>
          <p className="mt-1 text-sm text-gray-400">
            Character, version, scene, panel, and selected render asset stay visible together so page assembly decisions do not drift from the chosen shot.
          </p>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,360px)]">
        <div className="space-y-4">
          {episode.scenes.map((sceneDetail) => (
            <article key={sceneDetail.scene.id} className="rounded-2xl border border-gray-800 bg-gray-950/60 p-4">
              <div className="flex flex-col gap-2 border-b border-gray-800 pb-3">
                <p className="text-xs uppercase tracking-wide text-gray-500">Scene {sceneDetail.scene.scene_no}</p>
                <h3 className="text-base font-semibold text-gray-100">{sceneDetail.scene.premise}</h3>
                <p className="text-sm text-gray-400">
                  {sceneDetail.scene.location_label ?? 'Unknown location'} · {sceneDetail.panels.length} panels
                </p>
              </div>

              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {sceneDetail.panels.map((panel) => {
                  const assets = panelAssets[panel.id] ?? []
                  const asset = describeSelectedAsset(assets)
                  const isSelected = panel.id === selectedPanel?.id
                  const renderStatus = panelRenderStatuses[panel.id] ?? {
                    executionMode: 'local_preview' as const,
                    materializedAssetCount: assets.filter((entry) => Boolean(entry.storage_path)).length,
                    remoteJobCount: 0,
                    pendingRemoteCount: 0,
                    latestFailureMessage: null,
                    latestExternalJobUrl: null,
                  }
                  return (
                    <button
                      key={panel.id}
                      type="button"
                      onClick={() => onSelectPanel(panel.id)}
                      className={`rounded-2xl border p-4 text-left transition ${
                        isSelected
                          ? 'border-violet-500/40 bg-violet-500/10'
                          : 'border-gray-800 bg-gray-900/70 hover:border-gray-700'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-xs uppercase tracking-wide text-gray-500">
                            Panel {panel.panel_no} · {panel.panel_type}
                          </p>
                          <p className="mt-2 text-sm font-medium text-gray-100">
                            {panel.framing ?? panel.action_intent ?? 'No framing notes yet'}
                          </p>
                        </div>
                        {isSelected && (
                          <span className="rounded-full border border-violet-500/40 bg-violet-500/10 px-2 py-1 text-[11px] font-medium text-violet-200">
                            Selected Panel
                          </span>
                        )}
                      </div>
                      <p className="mt-3 text-xs text-gray-500">
                        {panelLineage(panel, episode.episode.title, sceneDetail.scene.scene_no)}
                      </p>
                      <div className="mt-4 rounded-xl border border-gray-800 bg-gray-950/80 px-3 py-2 text-xs text-gray-400">
                        <p className="font-medium uppercase tracking-wide text-gray-500">Selected Asset</p>
                        <p className="mt-1 truncate text-gray-200">
                          {asset?.storage_path ?? 'No selected render yet'}
                        </p>
                        <p className="mt-1 text-gray-500">
                          Candidates {assets.length} · Quality {formatQualityScore(asset?.quality_score ?? null)}
                        </p>
                        <p className="mt-2 text-gray-500">
                          Lane {formatExecutionLaneLabel(renderStatus.executionMode)}
                          {renderStatus.executionMode === 'remote_worker'
                            ? ` · ${renderStatus.pendingRemoteCount} pending`
                            : ''}
                        </p>
                      </div>
                    </button>
                  )
                })}
              </div>
            </article>
          ))}
        </div>

        <aside className="space-y-4 rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-gray-500">Current focus</p>
            <h3 className="mt-1 text-lg font-semibold text-gray-100">
              {selectedPanel ? `Panel ${selectedPanel.panel_no}` : 'No panel selected'}
            </h3>
            {selectedPanel && (
              <p className="mt-1 text-sm text-gray-400">
                {panelLineage(selectedPanel, episode.episode.title, selectedSceneDetail.scene.scene_no)}
              </p>
            )}
          </div>

          {selectedPanel ? (
            <>
              <div className="rounded-2xl border border-gray-800 bg-gray-900/70 p-4 text-sm text-gray-300">
                <p className="font-medium text-gray-100">Framing</p>
                <p className="mt-1 text-gray-400">{selectedPanel.framing ?? 'No framing notes yet.'}</p>
                <p className="mt-3 font-medium text-gray-100">Action Intent</p>
                <p className="mt-1 text-gray-400">{selectedPanel.action_intent ?? 'No action notes yet.'}</p>
              </div>

              {selectedPanelRenderStatus && (
                <div className="grid gap-3 rounded-2xl border border-gray-800 bg-gray-900/70 p-4 sm:grid-cols-2">
                  <div className="rounded-xl border border-gray-800 bg-gray-950/70 p-3">
                    <p className="text-xs uppercase tracking-wide text-gray-500">Execution Lane</p>
                    <p className="mt-1 text-sm font-medium text-gray-100">
                      {formatExecutionLaneLabel(selectedPanelRenderStatus.executionMode)}
                    </p>
                  </div>
                  <div className="rounded-xl border border-gray-800 bg-gray-950/70 p-3">
                    <p className="text-xs uppercase tracking-wide text-gray-500">Pending Remote Jobs</p>
                    <p className="mt-1 text-sm font-medium text-gray-100">
                      {selectedPanelRenderStatus.pendingRemoteCount}
                    </p>
                  </div>
                  <div className="rounded-xl border border-gray-800 bg-gray-950/70 p-3">
                    <p className="text-xs uppercase tracking-wide text-gray-500">Remote Jobs</p>
                    <p className="mt-1 text-sm font-medium text-gray-100">
                      {selectedPanelRenderStatus.remoteJobCount}
                    </p>
                  </div>
                  <div className="rounded-xl border border-gray-800 bg-gray-950/70 p-3">
                    <p className="text-xs uppercase tracking-wide text-gray-500">Materialized Assets</p>
                    <p className="mt-1 text-sm font-medium text-gray-100">
                      {selectedPanelRenderStatus.materializedAssetCount}
                    </p>
                  </div>
                  {selectedPanelRenderStatus.latestFailureMessage && (
                    <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 sm:col-span-2">
                      <p className="text-xs uppercase tracking-wide text-rose-200/80">Failure</p>
                      <p className="mt-1 text-sm text-rose-100">
                        {selectedPanelRenderStatus.latestFailureMessage}
                      </p>
                    </div>
                  )}
                  {selectedPanelRenderStatus.latestExternalJobUrl && (
                    <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-3 sm:col-span-2">
                      <p className="text-xs uppercase tracking-wide text-sky-200/80">External Job</p>
                      <a
                        href={selectedPanelRenderStatus.latestExternalJobUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-1 inline-flex text-sm font-medium text-sky-100 underline decoration-sky-300/60 underline-offset-4"
                      >
                        Open Remote Job
                      </a>
                    </div>
                  )}
                </div>
              )}

              <div className="grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => onQueueRenders(selectedPanel.id, 'local_preview')}
                  disabled={queueingPanelId === selectedPanel.id}
                  className="w-full rounded-xl border border-violet-500/40 bg-violet-500/10 px-4 py-2.5 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {queueingPanelId === selectedPanel.id && queueingExecutionMode === 'local_preview'
                    ? 'Queueing Local Preview...'
                    : 'Queue Local Preview'}
                </button>
                <button
                  type="button"
                  onClick={() => onQueueRenders(selectedPanel.id, 'remote_worker')}
                  disabled={queueingPanelId === selectedPanel.id}
                  className="w-full rounded-xl border border-cyan-500/40 bg-cyan-500/10 px-4 py-2.5 text-sm font-medium text-cyan-100 transition hover:bg-cyan-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {queueingPanelId === selectedPanel.id && queueingExecutionMode === 'remote_worker'
                    ? 'Queueing Remote Production...'
                    : 'Queue Remote Production'}
                </button>
              </div>
              <p className="text-xs text-gray-500">
                Local preview preserves the current one-panel verification flow. Remote production dispatches worker jobs and keeps status visible on the focused panel.
              </p>

              <div className="rounded-2xl border border-gray-800 bg-gray-900/70 p-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-gray-100">Selected Asset</h4>
                  <span className="text-xs text-gray-500">{selectedAssets.length} candidates</span>
                </div>
                {selectedAsset ? (
                  <div className="mt-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3">
                    <p className="text-xs uppercase tracking-wide text-emerald-200">Selected Asset</p>
                    <p className="mt-2 break-all text-sm font-medium text-gray-100">{selectedAsset.storage_path}</p>
                    <p className="mt-2 text-xs text-emerald-100">
                      Role {selectedAsset.asset_role} · Quality {formatQualityScore(selectedAsset.quality_score)}
                    </p>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-gray-400">No render has been selected yet.</p>
                )}

                <div className="mt-4 space-y-3">
                  {selectedAssets.map((asset) => (
                    <div key={asset.id} className="rounded-xl border border-gray-800 bg-gray-950/70 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-gray-100">{asset.storage_path ?? asset.id}</p>
                          <p className="mt-1 text-xs text-gray-500">
                            Role {asset.asset_role} · Quality {formatQualityScore(asset.quality_score)}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => onSelectAsset(selectedPanel.id, asset.id)}
                          disabled={!asset.storage_path || asset.is_selected || selectingAssetId === asset.id}
                          className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-200 transition hover:border-violet-500/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {asset.is_selected
                            ? 'Selected'
                            : !asset.storage_path
                              ? 'Render Pending'
                            : selectingAssetId === asset.id
                              ? 'Saving...'
                              : 'Mark Selected'}
                        </button>
                      </div>
                    </div>
                  ))}
                  {selectedAssets.length === 0 && (
                    <p className="text-sm text-gray-400">Queue renders to populate candidate assets for this panel.</p>
                  )}
                </div>
              </div>
            </>
          ) : (
            <EmptyState
              title="No panel selected"
              description="Pick a panel card to review its current asset stack and continue the render-selection workflow."
            />
          )}
        </aside>
      </div>
    </section>
  )
}
