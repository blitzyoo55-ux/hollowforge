import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getComfyUIStatus, getModels, getSystemHealth, syncModels, updateComfyUIUrl } from '../api/client'

export default function Settings() {
  const queryClient = useQueryClient()
  const [comfyUrl, setComfyUrl] = useState('http://127.0.0.1:8188')
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const [testing, setTesting] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [syncResult, setSyncResult] = useState<{ ok: boolean; message: string } | null>(null)

  const { data: comfyStatus } = useQuery({
    queryKey: ['comfyui-status'],
    queryFn: getComfyUIStatus,
    refetchInterval: 10_000,
  })

  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: getSystemHealth,
  })

  const { data: models, isLoading: modelsLoading } = useQuery({
    queryKey: ['models'],
    queryFn: getModels,
  })
  const imageCheckpoints = models?.checkpoints ?? []
  const allCheckpoints = models?.checkpoints_all ?? imageCheckpoints
  const excludedCheckpoints = models?.non_image_checkpoints ?? []

  useEffect(() => {
    if (!syncResult) return
    const timer = window.setTimeout(() => setSyncResult(null), 3500)
    return () => window.clearTimeout(timer)
  }, [syncResult])

  useEffect(() => {
    if (comfyStatus?.url) {
      setComfyUrl(comfyStatus.url)
    }
  }, [comfyStatus?.url])

  const handleTestConnection = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const status = await updateComfyUIUrl(comfyUrl)
      setTestResult({
        ok: status.connected,
        message: status.connected ? 'Connected successfully!' : 'ComfyUI is not responding',
      })
      await queryClient.invalidateQueries({ queryKey: ['comfyui-status'] })
      await queryClient.invalidateQueries({ queryKey: ['system-health'] })
    } catch {
      setTestResult({ ok: false, message: 'Failed to update ComfyUI URL' })
    } finally {
      setTesting(false)
    }
  }

  const handleSyncModels = async () => {
    setSyncing(true)
    setSyncResult(null)
    try {
      const result = await syncModels()
      await queryClient.invalidateQueries({ queryKey: ['models'] })
      await queryClient.invalidateQueries({ queryKey: ['loras'] })
      setSyncResult({
        ok: true,
        message:
          `Synced! ${result.new_loras} new LoRAs, ` +
          `${result.compatibility_updated} compatibility profiles refreshed` +
          (result.incompatible_loras > 0
            ? ` (${result.incompatible_loras} currently have no compatible checkpoint)`
            : ''),
      })
    } catch {
      setSyncResult({ ok: false, message: 'Sync failed' })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Settings</h2>
        <p className="text-sm text-gray-400 mt-1">Configure your HollowForge instance</p>
      </div>

      {/* ComfyUI connection */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4">
        <h3 className="text-lg font-semibold text-gray-100">ComfyUI Connection</h3>

        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${comfyStatus?.connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-300">
            {comfyStatus?.connected ? 'Connected' : 'Disconnected'}
          </span>
          {comfyStatus?.url && (
            <span className="text-xs text-gray-500 font-mono">{comfyStatus.url}</span>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1.5">ComfyUI URL</label>
          <div className="flex gap-3">
            <input
              type="text"
              value={comfyUrl}
              onChange={(e) => setComfyUrl(e.target.value)}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
            />
            <button
              onClick={handleTestConnection}
              disabled={testing}
              className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
            >
              {testing ? 'Applying...' : 'Apply & Test'}
            </button>
          </div>
        </div>

        {testResult && (
          <div className={`rounded-lg p-3 text-sm ${
            testResult.ok
              ? 'bg-green-900/20 border border-green-800/50 text-green-400'
              : 'bg-red-900/20 border border-red-800/50 text-red-400'
          }`}>
            {testResult.message}
          </div>
        )}
      </div>

      {/* Models & LoRAs */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-gray-100">Models &amp; LoRAs</h3>
          <button
            onClick={handleSyncModels}
            disabled={syncing}
            className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
          >
            {syncing ? 'Syncing...' : 'Sync from ComfyUI'}
          </button>
        </div>

        {syncResult && (
          <div className={`rounded-lg p-2.5 text-sm ${
            syncResult.ok
              ? 'bg-green-900/20 border border-green-800/50 text-green-400'
              : 'bg-red-900/20 border border-red-800/50 text-red-400'
          }`}>
            {syncResult.message}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-100">
              Image Checkpoints ({imageCheckpoints.length})
            </h4>
            <div className="max-h-40 overflow-y-auto rounded-lg border border-gray-800 bg-gray-950 p-3">
              {modelsLoading ? (
                <p className="text-xs text-gray-500">Loading checkpoints...</p>
              ) : imageCheckpoints.length > 0 ? (
                <ul className="space-y-1">
                  {imageCheckpoints.map((name) => (
                    <li key={name} className="text-xs text-gray-300 font-mono break-all">{name}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-gray-500">No checkpoints found</p>
              )}
            </div>
            <p className="text-[11px] text-gray-500">
              Total discovered: {allCheckpoints.length}
              {excludedCheckpoints.length > 0 ? ` · Excluded (video/non-image): ${excludedCheckpoints.length}` : ''}
            </p>
            {excludedCheckpoints.length > 0 && (
              <div className="max-h-24 overflow-y-auto rounded-lg border border-amber-900/40 bg-amber-950/20 p-2.5">
                <p className="text-[11px] text-amber-300 mb-1">Excluded from Generate/Presets</p>
                <ul className="space-y-1">
                  {excludedCheckpoints.map((name) => (
                    <li key={name} className="text-[11px] text-amber-200/90 font-mono break-all">{name}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-100">
              LoRA Files ({models?.lora_files?.length ?? 0})
            </h4>
            <div className="max-h-40 overflow-y-auto rounded-lg border border-gray-800 bg-gray-950 p-3">
              {modelsLoading ? (
                <p className="text-xs text-gray-500">Loading LoRA files...</p>
              ) : (models?.lora_files?.length ?? 0) > 0 ? (
                <ul className="space-y-1">
                  {(models?.lora_files ?? []).map((name) => (
                    <li key={name} className="text-xs text-gray-300 font-mono break-all">{name}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-gray-500">No LoRA files found</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* System info */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4">
        <h3 className="text-lg font-semibold text-gray-100">System Information</h3>

        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Status</span>
            <span className="text-gray-200 capitalize">{health?.status ?? 'unknown'}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Database</span>
            <span className={health?.db_ok ? 'text-green-400' : 'text-red-400'}>
              {health?.db_ok ? 'OK' : 'Error'}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">Total Generations</span>
            <span className="text-gray-200 font-mono">{health?.total_generations ?? 0}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">ComfyUI Connected</span>
            <span className={health?.comfyui_connected ? 'text-green-400' : 'text-red-400'}>
              {health?.comfyui_connected ? 'Yes' : 'No'}
            </span>
          </div>
        </div>
      </div>

      {/* Default parameters (read-only) */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4">
        <h3 className="text-lg font-semibold text-gray-100">Default Parameters</h3>
        <p className="text-xs text-gray-500">These defaults are used when no preset is selected</p>

        <div className="grid grid-cols-2 gap-4">
          <InfoRow label="Steps" value="28" />
          <InfoRow label="CFG Scale" value="7.0" />
          <InfoRow label="Width" value="832" />
          <InfoRow label="Height" value="1216" />
          <InfoRow label="Sampler" value="euler" />
          <InfoRow label="Scheduler" value="normal" />
        </div>
      </div>

      {/* Usage Guide */}
      <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-5">
        <h3 className="text-lg font-semibold text-gray-100">Usage Guide</h3>

        {/* Tags Guide */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-violet-400">Tags — Gallery Filtering &amp; Classification</h4>
          <p className="text-xs text-gray-400">Comma-separated keywords. Use consistent tags for easy filtering later.</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div><span className="text-gray-500">Series:</span> <span className="text-gray-300 font-mono">series-a, series-c, latex-hood</span></div>
            <div><span className="text-gray-500">Purpose:</span> <span className="text-gray-300 font-mono">sns-post, test, portfolio, client-review</span></div>
            <div><span className="text-gray-500">Theme:</span> <span className="text-gray-300 font-mono">gas-mask, cyberpunk, dungeon, lab</span></div>
            <div><span className="text-gray-500">Quality:</span> <span className="text-gray-300 font-mono">favorite, redo, reference</span></div>
            <div><span className="text-gray-500">Platform:</span> <span className="text-gray-300 font-mono">twitter, pixiv, patreon</span></div>
          </div>
        </div>

        {/* Notes Guide */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-violet-400">Notes — Free Text Memo</h4>
          <p className="text-xs text-gray-400">Record context for why you created this image. Useful when reproducing or iterating.</p>
          <ul className="text-xs text-gray-400 space-y-1 list-disc list-inside">
            <li>SNS engagement: <span className="text-gray-300">"Twitter 200+ likes, good engagement"</span></li>
            <li>Iteration context: <span className="text-gray-300">"Changed lighting from neon to spotlight"</span></li>
            <li>Seed quality: <span className="text-gray-300">"This seed gives great pose, tweak prompt only"</span></li>
            <li>Client work: <span className="text-gray-300">"Client A request - needs revision"</span></li>
          </ul>
        </div>

        {/* Mood & LoRA Guide */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-violet-400">Mood &amp; LoRA System</h4>
          <p className="text-xs text-gray-400">Select mood chips on the Generate page, then click "Auto-select from moods" to get recommended LoRAs.</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div><span className="bg-violet-600/20 text-violet-400 px-1.5 py-0.5 rounded">cyberpunk</span> <span className="text-gray-500">→ neon lighting + style LoRA</span></div>
            <div><span className="bg-violet-600/20 text-violet-400 px-1.5 py-0.5 rounded">dungeon</span> <span className="text-gray-500">→ harness + dark mood</span></div>
            <div><span className="bg-violet-600/20 text-violet-400 px-1.5 py-0.5 rounded">lab</span> <span className="text-gray-500">→ clinical lighting + ickpot</span></div>
            <div><span className="bg-violet-600/20 text-violet-400 px-1.5 py-0.5 rounded">latex</span> <span className="text-gray-500">→ shiny clothes + latex catsuit</span></div>
            <div><span className="bg-violet-600/20 text-violet-400 px-1.5 py-0.5 rounded">bondage</span> <span className="text-gray-500">→ harness + panel gag</span></div>
          </div>
          <p className="text-xs text-gray-500 mt-1">Category slots: style(1) + eyes(1) + material(0-1) + fetish(0-2). Max |strength| total: 2.4</p>
        </div>

        {/* Workflow */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-violet-400">Recommended Workflow</h4>
          <ol className="text-xs text-gray-400 space-y-1 list-decimal list-inside">
            <li>Select a <span className="text-gray-300">Preset</span> (Series A-E) or build from scratch</li>
            <li>Choose <span className="text-gray-300">Mood chips</span> → auto-select LoRAs, or pick manually</li>
            <li>Write/refine your <span className="text-gray-300">Prompt</span></li>
            <li>Hit <span className="text-gray-300">Generate</span> → wait for completion</li>
            <li>If good → tag as <span className="font-mono text-gray-300">favorite</span>, add platform tags</li>
            <li>If close → use <span className="text-gray-300">Variation</span> (new seed, same params)</li>
            <li>If perfect → <span className="text-gray-300">Save as Preset</span> for reuse</li>
          </ol>
        </div>
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-200 font-mono">{value}</span>
    </div>
  )
}
