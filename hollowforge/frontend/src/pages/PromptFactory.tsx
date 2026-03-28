import { useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import {
  generatePromptBatch,
  generatePromptBatchAndQueue,
  getPromptFactoryCheckpointPreferences,
  getPromptFactoryCapabilities,
  updatePromptFactoryCheckpointPreferences,
  queuePromptBatch,
} from '../api/client'
import type {
  PromptFactoryCheckpointPreferenceEntry,
  PromptFactoryCheckpointPreferenceMode,
  PromptFactoryCreativeAutonomy,
  PromptFactoryDirectionBlueprint,
  PromptFactoryGenerateRequest,
  PromptFactoryGenerateResponse,
  PromptFactoryHeatLevel,
  PromptFactoryQueueResponse,
  PromptFactoryTone,
  PromptFactoryWorkflowLane,
} from '../api/client'
import { notify } from '../lib/toast'
import StoryPlannerMode from '../components/tools/story-planner/StoryPlannerMode'

const DEFAULT_CONCEPT =
  'Lab-451 character exploration, masked containment heroine, glossy materials, control-room and chamber variations, cinematic anime illustration'

const DEFAULT_CREATIVE =
  'Keep identity tight, prioritize strong silhouette, reflective surfaces, dense tag stacks, direct restraint and mask cues, editorial framing, and variation across camera distance, location, and story beat.'

const DEFAULT_EXPANSION_AXES = [
  'camera distance',
  'lighting mood',
  'material emphasis',
  'mask design',
  'location',
  'restraint device',
  'story beat',
]

const DEFAULT_FORBIDDEN_ELEMENTS = ['extra fingers', 'bad hands', 'text watermark']

const COUNT_PRESETS = [8, 16, 25, 48]

const TONE_OPTIONS: Array<{
  value: PromptFactoryTone
  label: string
  description: string
}> = [
  {
    value: 'editorial',
    label: 'Editorial',
    description: '재질, 구도, 포즈, 카메라 언어를 가장 직접적으로 밀어붙입니다.',
  },
  {
    value: 'campaign',
    label: 'Campaign',
    description: '키비주얼과 브랜드 훅 중심으로 정리합니다.',
  },
  {
    value: 'clinical',
    label: 'Clinical',
    description: '격리, 절차, apparatus, specimen 톤을 강화합니다.',
  },
  {
    value: 'teaser',
    label: 'Teaser',
    description: '노출보다 긴장감과 감춤의 밀도를 높입니다.',
  },
]

const HEAT_OPTIONS: Array<{
  value: PromptFactoryHeatLevel
  label: string
  description: string
}> = [
  {
    value: 'maximal',
    label: 'Maximal',
    description: '가장 직설적입니다. restraint, mask, harness, compression 같은 시각 요소를 바로 씁니다.',
  },
  {
    value: 'steamy',
    label: 'Steamy',
    description: '강한 성인 텐션을 유지하되 maximal보다 한 단계 절제합니다.',
  },
  {
    value: 'suggestive',
    label: 'Suggestive',
    description: '암시와 긴장감에 무게를 둡니다.',
  },
]

const AUTONOMY_OPTIONS: Array<{
  value: PromptFactoryCreativeAutonomy
  label: string
  description: string
}> = [
  {
    value: 'hybrid',
    label: 'Hybrid',
    description: '브리프를 앵커로 유지하면서 Grok이 장면과 구도를 확장합니다.',
  },
  {
    value: 'director',
    label: 'Director',
    description: '브리프를 씨앗으로 보고 더 과감한 세트피스와 연출을 발명하게 합니다.',
  },
  {
    value: 'strict',
    label: 'Strict',
    description: '사용자 브리프에 가깝게 붙습니다. 발명 폭은 가장 낮습니다.',
  },
]

const LANE_OPTIONS: PromptFactoryWorkflowLane[] = ['auto', 'sdxl_illustrious', 'classic_clip']

const QUICK_RECIPES: Array<{
  id: string
  label: string
  description: string
  tone: PromptFactoryTone
  heat: PromptFactoryHeatLevel
  autonomy: PromptFactoryCreativeAutonomy
  directionPassEnabled: boolean
  count: number
}> = [
  {
    id: 'balanced',
    label: 'Balanced Production',
    description: '기본 추천. 사람이 검토하기 쉬운 밀도와 발명성을 같이 가져갑니다.',
    tone: 'editorial',
    heat: 'maximal',
    autonomy: 'hybrid',
    directionPassEnabled: true,
    count: 16,
  },
  {
    id: 'director',
    label: 'Director Mode',
    description: '장면 발명과 set-piece 확장을 가장 적극적으로 사용합니다.',
    tone: 'editorial',
    heat: 'maximal',
    autonomy: 'director',
    directionPassEnabled: true,
    count: 12,
  },
  {
    id: 'strict',
    label: 'Brief-Lock',
    description: '브리프 충실형. 반복 검수나 세부 조정에 적합합니다.',
    tone: 'campaign',
    heat: 'steamy',
    autonomy: 'strict',
    directionPassEnabled: false,
    count: 8,
  },
]

const CHECKPOINT_PREFERENCE_MODES: Array<{
  value: PromptFactoryCheckpointPreferenceMode
  label: string
}> = [
  { value: 'default', label: 'Default' },
  { value: 'prefer', label: 'Prefer' },
  { value: 'force', label: 'Force' },
  { value: 'exclude', label: 'Exclude' },
]

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ERR_NETWORK' || !error.response) {
      return 'Prompt Factory backend에 연결할 수 없습니다. backend 서버와 /api/v1 프록시 상태를 확인하세요.'
    }
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0]
      if (typeof first === 'string' && first.trim()) {
        return first
      }
      if (typeof first?.msg === 'string' && first.msg.trim()) {
        return first.msg
      }
    }
    if (typeof error.message === 'string' && error.message.trim()) {
      return error.message
    }
  }
  return fallback
}

function parseCsvList(raw: string): string[] {
  return raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function toCsv(values: string[]): string {
  return values.join(', ')
}

function controlSignature(payload: PromptFactoryGenerateRequest): string {
  return JSON.stringify({
    concept_brief: payload.concept_brief,
    creative_brief: payload.creative_brief ?? null,
    count: payload.count,
    chunk_size: payload.chunk_size,
    workflow_lane: payload.workflow_lane,
    provider: payload.provider,
    tone: payload.tone,
    heat_level: payload.heat_level,
    creative_autonomy: payload.creative_autonomy,
    direction_pass_enabled: payload.direction_pass_enabled,
    target_lora_count: payload.target_lora_count,
    checkpoint_pool_size: payload.checkpoint_pool_size,
    include_negative_prompt: payload.include_negative_prompt,
    dedupe: payload.dedupe,
    forbidden_elements: payload.forbidden_elements ?? [],
    expansion_axes: payload.expansion_axes ?? [],
  })
}

function directionPackSignature(value: PromptFactoryDirectionBlueprint[]): string {
  return JSON.stringify(value)
}

function cloneDirectionPack(value: PromptFactoryDirectionBlueprint[]): PromptFactoryDirectionBlueprint[] {
  return value.map((direction) => ({ ...direction }))
}

function checkpointPreferenceSignature(
  entries: Array<{
    checkpoint: string
    mode: PromptFactoryCheckpointPreferenceMode
    priority_boost: number
    notes?: string | null
  }>,
): string {
  return JSON.stringify(
    [...entries]
      .map((entry) => ({
        checkpoint: entry.checkpoint,
        mode: entry.mode,
        priority_boost: entry.priority_boost,
        notes: entry.notes?.trim() || null,
      }))
      .sort((a, b) => a.checkpoint.localeCompare(b.checkpoint)),
  )
}

function toCheckpointPreferenceDraftMap(
  entries: PromptFactoryCheckpointPreferenceEntry[],
): Record<string, PromptFactoryCheckpointPreferenceEntry> {
  return Object.fromEntries(
    entries.map((entry) => [entry.checkpoint, { ...entry }]),
  )
}

function activeCheckpointPreferenceEntries(
  entries: PromptFactoryCheckpointPreferenceEntry[],
): Array<{
  checkpoint: string
  mode: PromptFactoryCheckpointPreferenceMode
  priority_boost: number
  notes?: string | null
}> {
  return entries
    .filter(
      (entry) =>
        entry.mode !== 'default' ||
        entry.priority_boost !== 0 ||
        Boolean(entry.notes?.trim()),
    )
    .map((entry) => ({
      checkpoint: entry.checkpoint,
      mode: entry.mode,
      priority_boost: entry.priority_boost,
      notes: entry.notes?.trim() || null,
    }))
}

async function copyText(value: string, label: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(value)
    notify.success(`${label} 복사 완료`)
  } catch {
    notify.error(`${label} 복사에 실패했습니다.`)
  }
}

function countAccentClass(value: number): string {
  if (value >= 48) return 'border-rose-500/40 bg-rose-500/10 text-rose-200'
  if (value >= 25) return 'border-amber-500/40 bg-amber-500/10 text-amber-100'
  return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100'
}

function Surface({
  title,
  description,
  children,
  tone = 'default',
}: {
  title: string
  description?: string
  children: React.ReactNode
  tone?: 'default' | 'accent'
}) {
  const toneClass =
    tone === 'accent'
      ? 'border-violet-700/40 bg-gradient-to-br from-violet-950/40 via-gray-900 to-gray-900 shadow-[0_18px_60px_-40px_rgba(139,92,246,0.7)]'
      : 'border-gray-800 bg-gray-900/90'

  return (
    <section className={`rounded-3xl border p-5 md:p-6 ${toneClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-gray-100">{title}</h3>
          {description && <p className="mt-1 text-sm leading-6 text-gray-400">{description}</p>}
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  )
}

function OptionTile({
  label,
  description,
  active,
  onClick,
}: {
  label: string
  description: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-2xl border px-4 py-4 text-left transition ${
        active
          ? 'border-violet-500/60 bg-violet-500/12 text-white shadow-[0_10px_30px_-20px_rgba(139,92,246,0.9)]'
          : 'border-gray-800 bg-gray-950/80 text-gray-300 hover:border-gray-600 hover:bg-gray-950'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold">{label}</span>
        {active && (
          <span className="rounded-full border border-violet-400/40 bg-violet-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-violet-200">
            Active
          </span>
        )}
      </div>
      <p className="mt-2 text-xs leading-5 text-gray-400">{description}</p>
    </button>
  )
}

function Metric({
  label,
  value,
  accent = 'default',
}: {
  label: string
  value: string
  accent?: 'default' | 'good' | 'warn'
}) {
  const accentClass =
    accent === 'good'
      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
      : accent === 'warn'
        ? 'border-amber-500/30 bg-amber-500/10 text-amber-100'
        : 'border-gray-800 bg-gray-950/80 text-gray-100'

  return (
    <div className={`rounded-2xl border px-4 py-3 ${accentClass}`}>
      <div className="text-[11px] uppercase tracking-[0.16em] text-gray-500">{label}</div>
      <div className="mt-2 text-sm font-semibold">{value}</div>
    </div>
  )
}

function KeyValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="max-w-[70%] text-right text-gray-200">{value}</span>
    </div>
  )
}

function DirectionCard({
  direction,
  index,
}: {
  direction: PromptFactoryDirectionBlueprint
  index: number
}) {
  return (
    <article className="rounded-2xl border border-gray-800 bg-gray-950/90 px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-gray-100">{direction.codename_stub}</h4>
          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-gray-500">{direction.series}</p>
        </div>
        <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-violet-200">
          #{index + 1}
        </span>
      </div>

      <div className="mt-4 space-y-2 text-xs leading-5 text-gray-300">
        <p><span className="text-gray-500">Scene</span> {direction.scene_hook}</p>
        <p><span className="text-gray-500">Camera</span> {direction.camera_plan}</p>
        <p><span className="text-gray-500">Pose</span> {direction.pose_plan}</p>
        <p><span className="text-gray-500">Environment</span> {direction.environment}</p>
        <p><span className="text-gray-500">Device</span> {direction.device_focus}</p>
        <p><span className="text-gray-500">Lighting</span> {direction.lighting_plan}</p>
        <p><span className="text-gray-500">Material</span> {direction.material_focus}</p>
        <p><span className="text-gray-500">Intensity</span> {direction.intensity_hook}</p>
      </div>
    </article>
  )
}

function DirectionEditorCard({
  direction,
  index,
  onChange,
}: {
  direction: PromptFactoryDirectionBlueprint
  index: number
  onChange: (field: keyof PromptFactoryDirectionBlueprint, value: string) => void
}) {
  return (
    <details className="rounded-2xl border border-gray-800 bg-gray-950/85 p-4">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-violet-100">
                Direction {index + 1}
              </span>
              <span className="text-sm font-semibold text-gray-100">{direction.codename_stub}</span>
            </div>
            <p className="mt-1 text-xs uppercase tracking-[0.16em] text-gray-500">{direction.series}</p>
          </div>
          <div className="max-w-sm text-right text-xs leading-5 text-gray-400">
            <p>{direction.scene_hook}</p>
            <p className="mt-1 text-gray-500">{direction.intensity_hook}</p>
          </div>
        </div>
      </summary>

      <div className="mt-5 grid gap-3 md:grid-cols-2">
        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Codename</span>
          <input
            type="text"
            value={direction.codename_stub}
            onChange={(event) => onChange('codename_stub', event.target.value)}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Series</span>
          <input
            type="text"
            value={direction.series}
            onChange={(event) => onChange('series', event.target.value)}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2 md:col-span-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Scene Hook</span>
          <textarea
            value={direction.scene_hook}
            onChange={(event) => onChange('scene_hook', event.target.value)}
            rows={3}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Camera</span>
          <textarea
            value={direction.camera_plan}
            onChange={(event) => onChange('camera_plan', event.target.value)}
            rows={3}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Pose</span>
          <textarea
            value={direction.pose_plan}
            onChange={(event) => onChange('pose_plan', event.target.value)}
            rows={3}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Environment</span>
          <textarea
            value={direction.environment}
            onChange={(event) => onChange('environment', event.target.value)}
            rows={3}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Device Focus</span>
          <textarea
            value={direction.device_focus}
            onChange={(event) => onChange('device_focus', event.target.value)}
            rows={3}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Lighting</span>
          <textarea
            value={direction.lighting_plan}
            onChange={(event) => onChange('lighting_plan', event.target.value)}
            rows={3}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Material</span>
          <textarea
            value={direction.material_focus}
            onChange={(event) => onChange('material_focus', event.target.value)}
            rows={3}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>

        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Intensity</span>
          <textarea
            value={direction.intensity_hook}
            onChange={(event) => onChange('intensity_hook', event.target.value)}
            rows={3}
            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
          />
        </label>
      </div>
    </details>
  )
}

function PromptPreviewCard({
  row,
}: {
  row: NonNullable<PromptFactoryGenerateResponse['rows']>[number]
}) {
  return (
    <article className="rounded-2xl border border-gray-800 bg-gray-950/85 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-gray-400">
              Set {row.set_no}
            </span>
            <span className="text-sm font-semibold text-gray-100">{row.codename}</span>
          </div>
          <p className="mt-1 text-xs uppercase tracking-[0.16em] text-gray-500">{row.series}</p>
        </div>
        <button
          type="button"
          onClick={() => void copyText(row.positive_prompt, `${row.codename} prompt`)}
          className="rounded-lg border border-gray-700 px-3 py-1.5 text-xs text-gray-200 transition hover:border-gray-500 hover:text-white"
        >
          Prompt 복사
        </button>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-2 text-xs text-gray-300 md:grid-cols-2">
        <div className="rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-2">
          <span className="text-gray-500">Checkpoint</span>
          <p className="mt-1 break-all text-gray-100">{row.checkpoint}</p>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-900/70 px-3 py-2">
          <span className="text-gray-500">Params</span>
          <p className="mt-1 text-gray-100">
            {row.sampler} / {row.steps} steps / cfg {row.cfg} / {row.width}x{row.height}
          </p>
        </div>
      </div>

      <div className="mt-3 rounded-2xl border border-gray-800 bg-black/30 px-4 py-3">
        <p className="text-[11px] uppercase tracking-[0.16em] text-gray-500">Positive Prompt</p>
        <p className="mt-2 break-words text-sm leading-6 text-gray-200">{row.positive_prompt}</p>
      </div>

      <details className="mt-3 rounded-2xl border border-gray-800 bg-gray-900/60 px-4 py-3">
        <summary className="cursor-pointer text-xs font-medium text-gray-300">Negative Prompt</summary>
        <p className="mt-3 break-words text-xs leading-5 text-gray-400">{row.negative_prompt ?? 'none'}</p>
      </details>

      <div className="mt-3 flex flex-wrap gap-2">
        {row.loras.map((lora) => (
          <span
            key={`${row.set_no}-${lora.filename}`}
            className="rounded-full border border-violet-500/25 bg-violet-500/8 px-2.5 py-1 text-[11px] text-violet-100"
          >
            {lora.filename} ({lora.strength})
          </span>
        ))}
        {row.loras.length === 0 && (
          <span className="rounded-full border border-gray-700 bg-gray-900 px-2.5 py-1 text-[11px] text-gray-400">
            no LoRA
          </span>
        )}
      </div>
    </article>
  )
}

export default function PromptFactory() {
  const queryClient = useQueryClient()
  const [conceptBrief, setConceptBrief] = useState(DEFAULT_CONCEPT)
  const [creativeBrief, setCreativeBrief] = useState(DEFAULT_CREATIVE)
  const [count, setCount] = useState(8)
  const [tone, setTone] = useState<PromptFactoryTone>('editorial')
  const [heatLevel, setHeatLevel] = useState<PromptFactoryHeatLevel>('maximal')
  const [creativeAutonomy, setCreativeAutonomy] = useState<PromptFactoryCreativeAutonomy>('hybrid')
  const [directionPassEnabled, setDirectionPassEnabled] = useState(true)
  const [workflowLane, setWorkflowLane] = useState<PromptFactoryWorkflowLane>('auto')
  const [provider, setProvider] = useState<'default' | 'openrouter' | 'xai'>('default')
  const [targetLoraCount, setTargetLoraCount] = useState(2)
  const [checkpointPoolSize, setCheckpointPoolSize] = useState(3)
  const [expansionAxesRaw, setExpansionAxesRaw] = useState(toCsv(DEFAULT_EXPANSION_AXES))
  const [forbiddenElementsRaw, setForbiddenElementsRaw] = useState(toCsv(DEFAULT_FORBIDDEN_ELEMENTS))
  const [checkpointPreferenceSearch, setCheckpointPreferenceSearch] = useState('')
  const [showOnlyCustomizedCheckpoints, setShowOnlyCustomizedCheckpoints] = useState(false)
  const [mode, setMode] = useState<'advanced' | 'story-planner'>('advanced')
  const [checkpointPreferenceDrafts, setCheckpointPreferenceDrafts] = useState<
    Record<string, PromptFactoryCheckpointPreferenceEntry> | null
  >(null)
  const [editableDirectionPack, setEditableDirectionPack] = useState<PromptFactoryDirectionBlueprint[]>([])
  const [lastPreview, setLastPreview] = useState<PromptFactoryGenerateResponse | null>(null)
  const [lastPreviewControlSignature, setLastPreviewControlSignature] = useState<string | null>(null)
  const [lastPreviewDirectionSignature, setLastPreviewDirectionSignature] = useState<string | null>(null)
  const [lastRun, setLastRun] = useState<PromptFactoryQueueResponse | null>(null)

  const {
    data: capabilities,
    isLoading: capabilitiesLoading,
    error: capabilitiesError,
  } = useQuery({
    queryKey: ['prompt-factory-capabilities'],
    queryFn: getPromptFactoryCapabilities,
    staleTime: 60_000,
  })

  const { data: checkpointPreferences, isLoading: checkpointPreferencesLoading } = useQuery({
    queryKey: ['prompt-factory-checkpoint-preferences'],
    queryFn: getPromptFactoryCheckpointPreferences,
    staleTime: 60_000,
  })

  const buildPayload = (
    directionPackOverride?: PromptFactoryDirectionBlueprint[],
  ): PromptFactoryGenerateRequest => {
    const normalizedDirectionPack = directionPackOverride
      ?.map((direction) => ({
        ...direction,
        codename_stub: direction.codename_stub.trim(),
        series: direction.series.trim(),
        scene_hook: direction.scene_hook.trim(),
        camera_plan: direction.camera_plan.trim(),
        pose_plan: direction.pose_plan.trim(),
        environment: direction.environment.trim(),
        device_focus: direction.device_focus.trim(),
        lighting_plan: direction.lighting_plan.trim(),
        material_focus: direction.material_focus.trim(),
        intensity_hook: direction.intensity_hook.trim(),
      }))
      .filter((direction) =>
        Object.values(direction).every((value) => value.length > 0),
      )

    const effectiveCount = normalizedDirectionPack?.length || count

    return {
      concept_brief: conceptBrief.trim(),
      creative_brief: creativeBrief.trim() ? creativeBrief.trim() : null,
      count: effectiveCount,
      chunk_size: Math.min(effectiveCount, 25),
      workflow_lane: workflowLane,
      provider,
      tone,
      heat_level: heatLevel,
      creative_autonomy: creativeAutonomy,
      direction_pass_enabled: directionPassEnabled,
      target_lora_count: targetLoraCount,
      checkpoint_pool_size: checkpointPoolSize,
      include_negative_prompt: true,
      dedupe: true,
      forbidden_elements: parseCsvList(forbiddenElementsRaw),
      direction_pack_override: normalizedDirectionPack,
      expansion_axes: parseCsvList(expansionAxesRaw),
    }
  }

  const currentControlPayload = buildPayload()
  const currentControlSignature = controlSignature(currentControlPayload)
  const currentDirectionSignature = directionPackSignature(editableDirectionPack)

  const previewMutation = useMutation({
    mutationFn: (payload: PromptFactoryGenerateRequest) => generatePromptBatch(payload),
    onSuccess: (data, payload) => {
      setLastRun(null)
      setLastPreview(data)
      setEditableDirectionPack(cloneDirectionPack(data.direction_pack))
      setLastPreviewControlSignature(controlSignature(payload))
      setLastPreviewDirectionSignature(directionPackSignature(data.direction_pack))
      notify.success(`${data.generated_count}개 프롬프트를 프리뷰했습니다.`)
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Prompt batch preview 실행에 실패했습니다.'))
    },
  })

  const queueMutation = useMutation({
    mutationFn: async (input: {
      payload: PromptFactoryGenerateRequest
      preview: PromptFactoryGenerateResponse | null
      usePreview: boolean
    }) => {
      if (input.usePreview && input.preview) {
        return queuePromptBatch(input.preview)
      }
      return generatePromptBatchAndQueue(input.payload)
    },
    onSuccess: async (data, variables) => {
      setLastRun(data)
      setLastPreview(data.prompt_batch)
      setEditableDirectionPack(cloneDirectionPack(data.prompt_batch.direction_pack))
      setLastPreviewControlSignature(controlSignature(variables.payload))
      setLastPreviewDirectionSignature(directionPackSignature(data.prompt_batch.direction_pack))
      notify.success(`${data.prompt_batch.generated_count}개 프롬프트를 생성하고 ${data.queued_generations.length}개를 큐에 등록했습니다.`)
      await queryClient.invalidateQueries({ queryKey: ['active-generations'] })
      await queryClient.invalidateQueries({ queryKey: ['queue-summary'] })
      await queryClient.invalidateQueries({ queryKey: ['system-health'] })
      await queryClient.invalidateQueries({ queryKey: ['gallery-recent'] })
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Prompt batch queue 실행에 실패했습니다.'))
    },
  })

  const checkpointPreferenceMutation = useMutation({
    mutationFn: (entries: PromptFactoryCheckpointPreferenceEntry[]) =>
      updatePromptFactoryCheckpointPreferences({
        entries: activeCheckpointPreferenceEntries(entries),
      }),
    onSuccess: async (data) => {
      setCheckpointPreferenceDrafts(toCheckpointPreferenceDraftMap(data.entries))
      notify.success('Checkpoint 우선 제작 설정을 저장했습니다.')
      await queryClient.invalidateQueries({ queryKey: ['prompt-factory-checkpoint-preferences'] })
      await queryClient.invalidateQueries({ queryKey: ['prompt-factory-capabilities'] })
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Checkpoint 우선 제작 설정 저장에 실패했습니다.'))
    },
  })

  const selectedProviderReady = useMemo(() => {
    if (!capabilities) return false
    if (provider === 'default') return capabilities.ready
    if (provider === 'openrouter') return capabilities.openrouter_configured
    return capabilities.xai_configured
  }, [capabilities, provider])
  const canRun = selectedProviderReady
  const isBusy =
    previewMutation.isPending || queueMutation.isPending || checkpointPreferenceMutation.isPending
  const activeBatch = lastRun?.prompt_batch ?? lastPreview
  const activeBatchSource = lastRun ? 'queued' : lastPreview ? 'preview' : null
  const controlsDirtySincePreview = Boolean(
    lastPreview &&
      lastPreviewControlSignature &&
      lastPreviewControlSignature !== currentControlSignature,
  )
  const directionEditsDirty = Boolean(
    lastPreview &&
      lastPreviewDirectionSignature &&
      lastPreviewDirectionSignature !== currentDirectionSignature,
  )
  const currentPreviewReusable = Boolean(
    lastPreview &&
      lastPreviewControlSignature === currentControlSignature &&
      lastPreviewDirectionSignature === currentDirectionSignature,
  )

  const selectedTone = useMemo(
    () => TONE_OPTIONS.find((option) => option.value === tone) ?? TONE_OPTIONS[0],
    [tone],
  )
  const selectedHeat = useMemo(
    () => HEAT_OPTIONS.find((option) => option.value === heatLevel) ?? HEAT_OPTIONS[0],
    [heatLevel],
  )
  const selectedAutonomy = useMemo(
    () => AUTONOMY_OPTIONS.find((option) => option.value === creativeAutonomy) ?? AUTONOMY_OPTIONS[0],
    [creativeAutonomy],
  )
  const laneLabel = useMemo(() => {
    switch (workflowLane) {
      case 'sdxl_illustrious':
        return 'SDXL Illustrious'
      case 'classic_clip':
        return 'Classic CLIP'
      default:
        return capabilities?.recommended_lane ?? 'Auto'
    }
  }, [capabilities?.recommended_lane, workflowLane])
  const selectedProviderLabel =
    provider === 'default' ? capabilities?.default_provider ?? 'default' : provider
  const selectedProviderStatus = useMemo(() => {
    if (capabilitiesLoading) return 'checking'
    if (capabilitiesError) return 'offline'
    if (!capabilities) return 'offline'
    return selectedProviderReady ? 'ready' : 'misconfigured'
  }, [capabilities, capabilitiesError, capabilitiesLoading, selectedProviderReady])
  const canQueue = useMemo(() => {
    if (selectedProviderStatus === 'offline') return false
    if (currentPreviewReusable) return true
    return selectedProviderReady
  }, [currentPreviewReusable, selectedProviderReady, selectedProviderStatus])

  const previewRows = activeBatch?.rows.slice(0, 6) ?? []
  const directionPreview = activeBatch?.direction_pack.slice(0, 4) ?? []
  const topCheckpoints = activeBatch?.benchmark.top_checkpoints ?? []
  const savedCheckpointPreferenceEntries = useMemo(
    () => checkpointPreferences?.entries ?? checkpointPreferenceMutation.data?.entries ?? [],
    [checkpointPreferenceMutation.data?.entries, checkpointPreferences?.entries],
  )
  const savedCheckpointPreferenceDrafts = useMemo(
    () => toCheckpointPreferenceDraftMap(savedCheckpointPreferenceEntries),
    [savedCheckpointPreferenceEntries],
  )
  const benchmarkCueGroups = activeBatch
    ? [
        { label: 'Material', values: activeBatch.benchmark.material_cues },
        { label: 'Control', values: activeBatch.benchmark.control_cues },
        { label: 'Camera', values: activeBatch.benchmark.camera_cues },
        { label: 'Environment', values: activeBatch.benchmark.environment_cues },
        { label: 'Exposure', values: activeBatch.benchmark.exposure_cues },
      ]
    : []
  const checkpointPreferenceEntries = useMemo(
    () => Object.values(checkpointPreferenceDrafts ?? savedCheckpointPreferenceDrafts),
    [checkpointPreferenceDrafts, savedCheckpointPreferenceDrafts],
  )
  const activeCheckpointPreferenceCount = useMemo(
    () => activeCheckpointPreferenceEntries(checkpointPreferenceEntries).length,
    [checkpointPreferenceEntries],
  )
  const checkpointPreferenceDirty = useMemo(
    () =>
      checkpointPreferenceSignature(activeCheckpointPreferenceEntries(checkpointPreferenceEntries)) !==
      checkpointPreferenceSignature(activeCheckpointPreferenceEntries(savedCheckpointPreferenceEntries)),
    [checkpointPreferenceEntries, savedCheckpointPreferenceEntries],
  )
  const filteredCheckpointPreferences = useMemo(() => {
    const query = checkpointPreferenceSearch.trim().toLowerCase()
    return checkpointPreferenceEntries.filter((entry) => {
      const matchesSearch =
        !query ||
        entry.checkpoint.toLowerCase().includes(query) ||
        (entry.architecture ?? '').toLowerCase().includes(query)
      if (!matchesSearch) return false
      if (!showOnlyCustomizedCheckpoints) return true
      return (
        entry.mode !== 'default' ||
        entry.priority_boost !== 0 ||
        Boolean(entry.notes?.trim())
      )
    })
  }, [checkpointPreferenceEntries, checkpointPreferenceSearch, showOnlyCustomizedCheckpoints])
  const queueButtonLabel = currentPreviewReusable
    ? `현재 Preview ${lastPreview?.generated_count ?? 0}개 그대로 Queue`
    : directionEditsDirty && editableDirectionPack.length > 0
      ? 'Edited Directions로 Generate 후 Queue'
      : '지금 Generate 후 Queue'
  const queueIntentMessage = currentPreviewReusable
    ? '지금 누르면 마지막 preview 결과를 다시 생성하지 않고 그대로 generation queue에 넣습니다.'
    : directionEditsDirty && editableDirectionPack.length > 0
      ? '지금 누르면 편집된 direction pack으로 새 prompt batch를 만든 뒤 바로 queue에 넣습니다.'
      : '지금 누르면 현재 설정으로 새 prompt batch를 만들고 즉시 queue에 넣습니다.'

  const handlePreview = (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault()
    if (!conceptBrief.trim()) {
      notify.error('Concept brief를 입력하세요.')
      return
    }
    previewMutation.mutate(currentControlPayload)
  }

  const handleDirectionPreview = () => {
    if (editableDirectionPack.length === 0) {
      notify.error('편집할 direction pack preview가 아직 없습니다.')
      return
    }
    if (editableDirectionPack.some((direction) => Object.values(direction).some((value) => !value.trim()))) {
      notify.error('Direction pack의 빈 칸을 먼저 채우세요.')
      return
    }
    previewMutation.mutate(buildPayload(editableDirectionPack))
  }

  const handleQueue = () => {
    if (!conceptBrief.trim()) {
      notify.error('Concept brief를 입력하세요.')
      return
    }
    const payloadForQueue =
      directionEditsDirty && editableDirectionPack.length > 0
        ? buildPayload(editableDirectionPack)
        : currentControlPayload

    queueMutation.mutate({
      payload: payloadForQueue,
      preview: currentPreviewReusable ? lastPreview : null,
      usePreview: currentPreviewReusable,
    })
  }

  const applyRecipe = (recipeId: string) => {
    const recipe = QUICK_RECIPES.find((item) => item.id === recipeId)
    if (!recipe) return
    setTone(recipe.tone)
    setHeatLevel(recipe.heat)
    setCreativeAutonomy(recipe.autonomy)
    setDirectionPassEnabled(recipe.directionPassEnabled)
    setCount(recipe.count)
  }

  const resetToDefaults = () => {
    setConceptBrief(DEFAULT_CONCEPT)
    setCreativeBrief(DEFAULT_CREATIVE)
    setCount(8)
    setTone('editorial')
    setHeatLevel('maximal')
    setCreativeAutonomy('hybrid')
    setDirectionPassEnabled(true)
    setWorkflowLane('auto')
    setProvider('default')
    setTargetLoraCount(2)
    setCheckpointPoolSize(3)
    setExpansionAxesRaw(toCsv(DEFAULT_EXPANSION_AXES))
    setForbiddenElementsRaw(toCsv(DEFAULT_FORBIDDEN_ELEMENTS))
    setEditableDirectionPack(lastPreview?.direction_pack ? cloneDirectionPack(lastPreview.direction_pack) : [])
  }

  const resetDirectionEditor = () => {
    setEditableDirectionPack(cloneDirectionPack(lastPreview?.direction_pack ?? []))
  }

  const updateDirection = (
    index: number,
    field: keyof PromptFactoryDirectionBlueprint,
    value: string,
  ) => {
    setEditableDirectionPack((current) =>
      current.map((direction, directionIndex) =>
        directionIndex === index ? { ...direction, [field]: value } : direction,
      ),
    )
  }

  const updateCheckpointPreference = (
    checkpoint: string,
    patch: Partial<Pick<PromptFactoryCheckpointPreferenceEntry, 'mode' | 'priority_boost' | 'notes'>>,
  ) => {
    setCheckpointPreferenceDrafts((current) => {
      const base = current ?? savedCheckpointPreferenceDrafts
      const existing = base[checkpoint]
      if (!existing) return base
      return {
        ...base,
        [checkpoint]: {
          ...existing,
          ...patch,
        },
      }
    })
  }

  const resetCheckpointPreferences = () => {
    setCheckpointPreferenceDrafts(null)
  }

  const saveCheckpointPreferences = () => {
    checkpointPreferenceMutation.mutate(checkpointPreferenceEntries)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 rounded-3xl border border-white/10 bg-gray-950/90 p-3 shadow-2xl shadow-black/20">
        <button
          type="button"
          onClick={() => setMode('story-planner')}
          className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
            mode === 'story-planner'
              ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
              : 'border-gray-700 bg-gray-950 text-gray-300 hover:border-gray-500 hover:text-white'
          }`}
        >
          Story Planner
        </button>
        <button
          type="button"
          onClick={() => setMode('advanced')}
          className={`rounded-full border px-4 py-2 text-sm font-semibold transition ${
            mode === 'advanced'
              ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
              : 'border-gray-700 bg-gray-950 text-gray-300 hover:border-gray-500 hover:text-white'
          }`}
        >
          Advanced Batch
        </button>
        <button
          type="button"
          disabled
          className="cursor-not-allowed rounded-full border border-gray-800 bg-gray-950 px-4 py-2 text-sm font-semibold text-gray-500 opacity-70"
        >
          Character Profile - Coming Soon
        </button>
      </div>

      {mode === 'story-planner' ? (
        <StoryPlannerMode />
      ) : (
        <>
      <Surface
        title="Prompt Factory"
        description="브리프를 넣으면 benchmark를 읽고, 필요하면 direction pack을 먼저 발명한 뒤, 최종 프롬프트를 프리뷰하거나 그대로 큐에 넣습니다."
        tone="accent"
      >
        <div className="grid gap-4 xl:grid-cols-[1.4fr_0.9fr]">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-violet-400/30 bg-violet-400/10 px-3 py-1.5 text-xs font-medium text-violet-100">
                {laneLabel}
              </span>
              <span className="rounded-full border border-gray-700 bg-gray-950/80 px-3 py-1.5 text-xs font-medium text-gray-200">
                Tone {selectedTone.label}
              </span>
              <span className="rounded-full border border-gray-700 bg-gray-950/80 px-3 py-1.5 text-xs font-medium text-gray-200">
                Heat {selectedHeat.label}
              </span>
              <span className="rounded-full border border-gray-700 bg-gray-950/80 px-3 py-1.5 text-xs font-medium text-gray-200">
                Autonomy {selectedAutonomy.label}
              </span>
              <span className="rounded-full border border-gray-700 bg-gray-950/80 px-3 py-1.5 text-xs font-medium text-gray-200">
                Direction Pass {directionPassEnabled ? 'On' : 'Off'}
              </span>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
              <Metric label="Current Count" value={`${count} rows`} accent={count >= 25 ? 'warn' : 'good'} />
              <Metric label="Preview Reusable" value={currentPreviewReusable ? 'Yes' : 'No'} accent={currentPreviewReusable ? 'good' : 'default'} />
              <Metric label="Editable Directions" value={`${editableDirectionPack.length}`} accent={editableDirectionPack.length ? 'good' : 'default'} />
              <Metric label="Checkpoint Prefs" value={`${activeCheckpointPreferenceCount}`} accent={activeCheckpointPreferenceCount > 0 ? 'good' : 'default'} />
              <Metric label="Factory Ready" value={canRun ? 'Yes' : 'No'} accent={canRun ? 'good' : 'warn'} />
              <Metric label="Queue Ready" value={canQueue ? 'Yes' : 'No'} accent={canQueue ? 'good' : 'warn'} />
            </div>

            <p className="max-w-3xl text-sm leading-6 text-gray-300">
              지금 모드에서는 <span className="font-medium text-white">{selectedAutonomy.description}</span>{' '}
              Grok은 <span className="font-medium text-white">{selectedTone.description}</span>{' '}
              그리고 <span className="font-medium text-white">{selectedHeat.description}</span>
            </p>
          </div>

          <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
            <p className="text-[11px] uppercase tracking-[0.18em] text-violet-200/70">Human Workflow</p>
            <div className="mt-4 grid gap-3">
              <div className="rounded-2xl border border-gray-800 bg-gray-950/80 px-4 py-3">
                <div className="text-xs font-semibold text-white">1. Brief</div>
                <p className="mt-1 text-xs leading-5 text-gray-400">컨셉과 연출 방향을 입력합니다.</p>
              </div>
              <div className="rounded-2xl border border-gray-800 bg-gray-950/80 px-4 py-3">
                <div className="text-xs font-semibold text-white">2. Direction Pack</div>
                <p className="mt-1 text-xs leading-5 text-gray-400">켜져 있으면 먼저 장면 블루프린트를 만듭니다.</p>
              </div>
              <div className="rounded-2xl border border-gray-800 bg-gray-950/80 px-4 py-3">
                <div className="text-xs font-semibold text-white">3. Preview</div>
                <p className="mt-1 text-xs leading-5 text-gray-400">사람이 보고 판단할 수 있게 prompt row를 확인합니다.</p>
              </div>
              <div className="rounded-2xl border border-gray-800 bg-gray-950/80 px-4 py-3">
                <div className="text-xs font-semibold text-white">4. Edit</div>
                <p className="mt-1 text-xs leading-5 text-gray-400">direction pack을 다듬고 다시 preview할 수 있습니다.</p>
              </div>
              <div className="rounded-2xl border border-gray-800 bg-gray-950/80 px-4 py-3">
                <div className="text-xs font-semibold text-white">5. Queue</div>
                <p className="mt-1 text-xs leading-5 text-gray-400">검토가 끝난 batch만 그대로 큐에 넣습니다.</p>
              </div>
            </div>
          </div>
        </div>
      </Surface>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_380px]">
        <div className="space-y-6">
          <Surface
            title="1. Brief Inputs"
            description="모델이 그대로 반복하지 않고 확장할 seed를 입력합니다. 모호한 문장보다 시각 요소 중심이 좋습니다."
          >
            <form className="space-y-6" onSubmit={handlePreview}>
              <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-4">
                    <label className="text-sm font-medium text-gray-200" htmlFor="concept-brief">
                      Concept Brief
                    </label>
                    <span className="text-xs text-gray-500">{conceptBrief.length}/600</span>
                  </div>
                  <textarea
                    id="concept-brief"
                    value={conceptBrief}
                    onChange={(event) => setConceptBrief(event.target.value)}
                    rows={6}
                    className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
                    placeholder="예: sealed latex hood, glossy black catsuit, intake chamber, suspended restraint frame, lab-451 containment heroine"
                  />
                  <p className="text-xs leading-5 text-gray-500">
                    캐릭터 정체성과 핵심 모티프를 넣는 칸입니다. 세계관, outfit, signature motif를 우선 적으세요.
                  </p>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-4">
                    <label className="text-sm font-medium text-gray-200" htmlFor="creative-brief">
                      Creative Brief
                    </label>
                    <span className="text-xs text-gray-500">{creativeBrief.length}/600</span>
                  </div>
                  <textarea
                    id="creative-brief"
                    value={creativeBrief}
                    onChange={(event) => setCreativeBrief(event.target.value)}
                    rows={6}
                    className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
                    placeholder="예: low angle dominance framing, apparatus-heavy set design, stronger restraint geometry, sharper editorial sheen"
                  />
                  <p className="text-xs leading-5 text-gray-500">
                    구도, 연출, 카메라, 질감, 장치, story beat처럼 모델이 확장할 축을 넣는 칸입니다.
                  </p>
                </div>
              </div>

              <div className="rounded-2xl border border-gray-800 bg-gray-950/70 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-gray-100">Quick Count</p>
                    <p className="mt-1 text-xs text-gray-500">소규모 프리뷰부터 시작해서 괜찮으면 바로 확장하는 흐름이 가장 안전합니다.</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {COUNT_PRESETS.map((preset) => (
                      <button
                        key={preset}
                        type="button"
                        onClick={() => setCount(preset)}
                        className={`rounded-full border px-3 py-1.5 text-xs transition ${
                          count === preset
                            ? `font-semibold ${countAccentClass(preset)}`
                            : 'border-gray-700 bg-gray-950 text-gray-300 hover:border-gray-500 hover:text-white'
                        }`}
                      >
                        {preset}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </form>
          </Surface>

          <Surface
            title="2. Creative Controls"
            description="사람이 바로 이해할 수 있도록 톤, 수위, 발명성은 카드형으로 분리했습니다. 눈으로 보고 선택하면 됩니다."
          >
            <div className="space-y-6">
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-100">Tone</p>
                    <p className="text-xs text-gray-500">이미지가 어떤 프레이밍으로 읽히는지 결정합니다.</p>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {TONE_OPTIONS.map((option) => (
                    <OptionTile
                      key={option.value}
                      label={option.label}
                      description={option.description}
                      active={tone === option.value}
                      onClick={() => setTone(option.value)}
                    />
                  ))}
                </div>
              </div>

              <div>
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-100">Heat</p>
                    <p className="text-xs text-gray-500">프롬프트가 도달해야 하는 최소 수위입니다.</p>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  {HEAT_OPTIONS.map((option) => (
                    <OptionTile
                      key={option.value}
                      label={option.label}
                      description={option.description}
                      active={heatLevel === option.value}
                      onClick={() => setHeatLevel(option.value)}
                    />
                  ))}
                </div>
              </div>

              <div>
                <div className="mb-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-100">Creative Autonomy</p>
                    <p className="text-xs text-gray-500">브리프를 얼마나 강하게 reinterpret 할지 정합니다.</p>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  {AUTONOMY_OPTIONS.map((option) => (
                    <OptionTile
                      key={option.value}
                      label={option.label}
                      description={option.description}
                      active={creativeAutonomy === option.value}
                      onClick={() => setCreativeAutonomy(option.value)}
                    />
                  ))}
                </div>
              </div>
            </div>
          </Surface>

          <Surface
            title="3. Fine Controls"
            description="Lane, provider, expansion axes, forbidden elements처럼 세부 조정이 필요한 항목만 아래에 모았습니다."
          >
            <div className="grid gap-5 md:grid-cols-2">
              <div className="space-y-4">
                <label className="block space-y-2">
                  <span className="text-sm font-medium text-gray-200">Direction Pass</span>
                  <button
                    type="button"
                    onClick={() => setDirectionPassEnabled((value) => !value)}
                    className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${
                      directionPassEnabled
                        ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
                        : 'border-gray-800 bg-gray-950 text-gray-300 hover:border-gray-600'
                    }`}
                  >
                    <div>
                      <div className="text-sm font-semibold">{directionPassEnabled ? 'Enabled' : 'Disabled'}</div>
                      <div className="mt-1 text-xs leading-5 text-gray-400">
                        켜면 먼저 장면 블루프린트를 발명하고, 그 결과를 최종 프롬프트에 반영합니다.
                      </div>
                    </div>
                    <div className={`h-6 w-11 rounded-full p-1 transition ${directionPassEnabled ? 'bg-violet-500/30' : 'bg-gray-800'}`}>
                      <div className={`h-4 w-4 rounded-full bg-white transition ${directionPassEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
                    </div>
                  </button>
                </label>

                <label className="block space-y-2">
                  <span className="text-sm font-medium text-gray-200">Workflow Lane</span>
                  <select
                    value={workflowLane}
                    onChange={(event) => setWorkflowLane(event.target.value as PromptFactoryWorkflowLane)}
                    className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                  >
                    {LANE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block space-y-2">
                  <span className="text-sm font-medium text-gray-200">Provider</span>
                  <select
                    value={provider}
                    onChange={(event) => setProvider(event.target.value as 'default' | 'openrouter' | 'xai')}
                    className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                  >
                    <option value="default">default</option>
                    <option value="openrouter">openrouter</option>
                    <option value="xai">xai</option>
                  </select>
                </label>

                <div className="grid grid-cols-2 gap-3">
                  <label className="block space-y-2">
                    <span className="text-sm font-medium text-gray-200">Target LoRA Count</span>
                    <input
                      type="number"
                      min={1}
                      max={4}
                      value={targetLoraCount}
                      onChange={(event) => setTargetLoraCount(Math.max(1, Math.min(4, Number(event.target.value) || 2)))}
                      className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                    />
                  </label>

                  <label className="block space-y-2">
                    <span className="text-sm font-medium text-gray-200">Checkpoint Pool Size</span>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={checkpointPoolSize}
                      onChange={(event) => setCheckpointPoolSize(Math.max(1, Math.min(5, Number(event.target.value) || 3)))}
                      className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                    />
                  </label>
                </div>
              </div>

              <div className="space-y-4">
                <label className="block space-y-2">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-sm font-medium text-gray-200">Expansion Axes</span>
                    <span className="text-xs text-gray-500">{parseCsvList(expansionAxesRaw).length} axes</span>
                  </div>
                  <textarea
                    value={expansionAxesRaw}
                    onChange={(event) => setExpansionAxesRaw(event.target.value)}
                    rows={5}
                    className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
                    placeholder="camera distance, lighting mood, mask design, location, restraint device"
                  />
                </label>

                <label className="block space-y-2">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-sm font-medium text-gray-200">Forbidden Elements</span>
                    <span className="text-xs text-gray-500">{parseCsvList(forbiddenElementsRaw).length} items</span>
                  </div>
                  <textarea
                    value={forbiddenElementsRaw}
                    onChange={(event) => setForbiddenElementsRaw(event.target.value)}
                    rows={4}
                    className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm leading-6 text-gray-100 outline-none transition focus:border-violet-500"
                    placeholder="school setting, casual selfie vibe"
                  />
                </label>
              </div>
            </div>
          </Surface>

          <Surface
            title="4. Checkpoint Priorities"
            description="모델별 우선 제작 설정입니다. 아무 것도 저장하지 않으면 지금처럼 favorite benchmark 순서대로 동작합니다."
          >
            {checkpointPreferencesLoading ? (
              <p className="text-sm text-gray-500">Checkpoint settings를 불러오는 중입니다...</p>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <Metric label="Customized" value={`${activeCheckpointPreferenceCount}`} accent={activeCheckpointPreferenceCount > 0 ? 'good' : 'default'} />
                  <Metric label="Dirty" value={checkpointPreferenceDirty ? 'Yes' : 'No'} accent={checkpointPreferenceDirty ? 'warn' : 'good'} />
                  <Metric label="Visible Models" value={`${filteredCheckpointPreferences.length}`} />
                  <Metric label="Default Rule" value="Favorite Rank" />
                </div>

                <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4 text-sm text-gray-300">
                  <p className="font-medium text-gray-100">Mode guide</p>
                  <p className="mt-2 text-xs leading-6 text-gray-400">
                    `Default`는 기존 favorite 기반 순위 유지, `Prefer`는 상단으로 끌어올림, `Force`는 pool 앞쪽으로 강제 진입, `Exclude`는 Prompt Factory 후보에서 제외입니다.
                  </p>
                </div>

                <div className="flex flex-wrap items-end gap-3">
                  <label className="block min-w-[260px] flex-1 space-y-2">
                    <span className="text-sm font-medium text-gray-200">Search Model</span>
                    <input
                      type="text"
                      value={checkpointPreferenceSearch}
                      onChange={(event) => setCheckpointPreferenceSearch(event.target.value)}
                      className="w-full rounded-2xl border border-gray-800 bg-gray-950 px-4 py-3 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                      placeholder="checkpoint name or architecture"
                    />
                  </label>

                  <button
                    type="button"
                    onClick={() => setShowOnlyCustomizedCheckpoints((value) => !value)}
                    className={`rounded-2xl border px-4 py-3 text-sm transition ${
                      showOnlyCustomizedCheckpoints
                        ? 'border-violet-500/40 bg-violet-500/10 text-violet-100'
                        : 'border-gray-700 bg-gray-950 text-gray-300 hover:border-gray-500 hover:text-white'
                    }`}
                  >
                    {showOnlyCustomizedCheckpoints ? 'Customized Only' : 'Show All Models'}
                  </button>

                  <button
                    type="button"
                    onClick={resetCheckpointPreferences}
                    disabled={!checkpointPreferenceDirty}
                    className="rounded-2xl border border-gray-700 px-4 py-3 text-sm text-gray-300 transition hover:border-gray-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Reset Checkpoint Drafts
                  </button>

                  <button
                    type="button"
                    onClick={saveCheckpointPreferences}
                    disabled={!checkpointPreferenceDirty || checkpointPreferenceMutation.isPending}
                    className="rounded-2xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {checkpointPreferenceMutation.isPending ? 'Saving...' : 'Save Checkpoint Settings'}
                  </button>
                </div>

                <div className="space-y-3">
                  {filteredCheckpointPreferences.map((entry) => (
                    <div
                      key={entry.checkpoint}
                      className="rounded-2xl border border-gray-800 bg-gray-950/85 p-4"
                    >
                      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_160px_130px_minmax(180px,0.9fr)]">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold text-gray-100">{entry.checkpoint}</span>
                            <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-gray-400">
                              {entry.architecture ?? 'Unknown'}
                            </span>
                            {!entry.available && (
                              <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-amber-100">
                                Unavailable
                              </span>
                            )}
                          </div>
                          <p className="mt-2 text-xs leading-5 text-gray-500">
                            favorites {entry.favorite_count} · updated {entry.updated_at ?? 'never'}
                          </p>
                        </div>

                        <label className="block space-y-2">
                          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Mode</span>
                          <select
                            value={entry.mode}
                            onChange={(event) =>
                              updateCheckpointPreference(entry.checkpoint, {
                                mode: event.target.value as PromptFactoryCheckpointPreferenceMode,
                              })
                            }
                            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                          >
                            {CHECKPOINT_PREFERENCE_MODES.map((mode) => (
                              <option key={mode.value} value={mode.value}>
                                {mode.label}
                              </option>
                            ))}
                          </select>
                        </label>

                        <label className="block space-y-2">
                          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Boost</span>
                          <input
                            type="number"
                            min={-20}
                            max={20}
                            value={entry.priority_boost}
                            onChange={(event) =>
                              updateCheckpointPreference(entry.checkpoint, {
                                priority_boost: Math.max(-20, Math.min(20, Number(event.target.value) || 0)),
                              })
                            }
                            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                          />
                        </label>

                        <label className="block space-y-2">
                          <span className="text-xs font-medium uppercase tracking-[0.14em] text-gray-500">Notes</span>
                          <input
                            type="text"
                            value={entry.notes ?? ''}
                            onChange={(event) =>
                              updateCheckpointPreference(entry.checkpoint, {
                                notes: event.target.value,
                              })
                            }
                            className="w-full rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none transition focus:border-violet-500"
                            placeholder="optional note"
                          />
                        </label>
                      </div>
                    </div>
                  ))}
                  {filteredCheckpointPreferences.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-gray-700 bg-gray-950/80 px-4 py-6 text-sm text-gray-500">
                      표시할 checkpoint가 없습니다. 검색어를 지우거나 customized filter를 해제하세요.
                    </div>
                  )}
                </div>
              </div>
            )}
          </Surface>

          <Surface
            title="5. Preview And Queue"
            description="fresh preview, edited preview, queue를 분리해서 사람이 무엇을 확정하는지 명확하게 보이도록 구성했습니다."
          >
            <div className="space-y-4">
              <div className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <Metric label="Tone" value={selectedTone.label} />
                  <Metric label="Heat" value={selectedHeat.label} />
                  <Metric label="Autonomy" value={selectedAutonomy.label} />
                  <Metric label="Direction Pass" value={directionPassEnabled ? 'Enabled' : 'Disabled'} accent={directionPassEnabled ? 'good' : 'default'} />
                </div>
                {selectedProviderStatus === 'offline' && (
                  <div className="mt-4 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                    Prompt Factory backend 연결이 없습니다. backend 서버 또는 `/api/v1` 프록시가 살아 있는지 확인하세요.
                  </div>
                )}
                {selectedProviderStatus === 'misconfigured' && (
                  <div className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                    현재 선택한 provider `{selectedProviderLabel}` 가 설정되지 않았습니다. Provider를 `default`로 바꾸거나 사용 가능한 provider를 선택하세요.
                  </div>
                )}
                {controlsDirtySincePreview && (
                  <div className="mt-4 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                    마지막 preview 이후 설정이 바뀌었습니다. 지금 queue하면 새로운 결과를 다시 생성해서 넣습니다.
                  </div>
                )}
                {directionEditsDirty && (
                  <div className="mt-4 rounded-2xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm text-sky-100">
                    direction pack 편집 내용이 아직 preview에 반영되지 않았습니다. edited preview를 한 번 더 돌린 뒤 queue하는 편이 안전합니다.
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={() => handlePreview()}
                  disabled={isBusy || !canRun}
                  className="rounded-2xl bg-violet-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {previewMutation.isPending ? 'Previewing...' : 'Preview Directions & Prompts'}
                </button>

                <button
                  type="button"
                  onClick={handleDirectionPreview}
                  disabled={isBusy || !canRun || editableDirectionPack.length === 0}
                  className="rounded-2xl border border-sky-600/40 bg-sky-500/10 px-5 py-3 text-sm font-semibold text-sky-100 transition hover:border-sky-500 hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {previewMutation.isPending && directionEditsDirty ? 'Re-Previewing...' : 'Preview Edited Directions'}
                </button>

                <button
                  type="button"
                  onClick={handleQueue}
                  disabled={isBusy || !canQueue}
                  className="rounded-2xl border border-gray-700 bg-gray-950 px-5 py-3 text-sm font-semibold text-gray-100 transition hover:border-gray-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {queueMutation.isPending ? 'Queueing...' : queueButtonLabel}
                </button>

                <button
                  type="button"
                  onClick={resetToDefaults}
                  className="rounded-2xl border border-gray-700 px-4 py-3 text-sm text-gray-300 transition hover:border-gray-500 hover:text-white"
                >
                  Reset Defaults
                </button>
              </div>

              <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm text-emerald-100">
                {queueIntentMessage}
              </div>
            </div>
          </Surface>

          <Surface
            title="6. Direction Editor"
            description="preview된 direction pack을 사람이 직접 다듬을 수 있습니다. 수정 후 edited preview를 돌리면 같은 구조로 프롬프트를 다시 뽑습니다."
          >
            {editableDirectionPack.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-gray-700 bg-gray-950/70 px-4 py-6 text-sm text-gray-500">
                direction pack이 아직 없습니다. 먼저 preview를 실행하면 여기서 바로 편집할 수 있습니다.
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <Metric label="Loaded Directions" value={`${editableDirectionPack.length}`} accent="good" />
                  <Metric label="Editor Dirty" value={directionEditsDirty ? 'Yes' : 'No'} accent={directionEditsDirty ? 'warn' : 'good'} />
                  <Metric label="Reusable Preview" value={currentPreviewReusable ? 'Yes' : 'No'} accent={currentPreviewReusable ? 'good' : 'default'} />
                  <Metric label="Queue Mode" value={currentPreviewReusable ? 'Reuse Preview' : 'Regenerate'} accent={currentPreviewReusable ? 'good' : 'warn'} />
                </div>

                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={handleDirectionPreview}
                    disabled={isBusy || !canRun}
                    className="rounded-2xl bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Edited Preview 실행
                  </button>
                  <button
                    type="button"
                    onClick={resetDirectionEditor}
                    disabled={editableDirectionPack.length === 0}
                    className="rounded-2xl border border-gray-700 px-4 py-2.5 text-sm text-gray-300 transition hover:border-gray-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Latest Preview로 되돌리기
                  </button>
                </div>

                <div className="space-y-4">
                  {editableDirectionPack.map((direction, index) => (
                    <DirectionEditorCard
                      key={`${direction.codename_stub}-${index}`}
                      direction={direction}
                      index={index}
                      onChange={(field, value) => updateDirection(index, field, value)}
                    />
                  ))}
                </div>
              </div>
            )}
          </Surface>
        </div>

        <aside className="space-y-6 xl:sticky xl:top-6 xl:self-start">
          <Surface
            title="Quick Recipes"
            description="자주 쓰는 조합을 한 번에 적용할 수 있습니다."
          >
            <div className="space-y-3">
              {QUICK_RECIPES.map((recipe) => (
                <button
                  key={recipe.id}
                  type="button"
                  onClick={() => applyRecipe(recipe.id)}
                  className="w-full rounded-2xl border border-gray-800 bg-gray-950/80 px-4 py-4 text-left transition hover:border-gray-600 hover:bg-gray-950"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-sm font-semibold text-gray-100">{recipe.label}</span>
                    <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-gray-400">
                      {recipe.count} rows
                    </span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-gray-400">{recipe.description}</p>
                </button>
              ))}
            </div>
          </Surface>

          <Surface
            title="Factory Status"
            description="현재 provider와 benchmark 진입 가능 상태를 바로 확인할 수 있습니다."
          >
            {capabilitiesLoading ? (
              <p className="text-sm text-gray-500">Loading capabilities...</p>
            ) : capabilitiesError ? (
              <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-100">
                {getErrorMessage(capabilitiesError, 'Prompt Factory capabilities를 불러오지 못했습니다.')}
              </div>
            ) : (
              <div className="divide-y divide-gray-800">
                <KeyValue label="Ready" value={capabilities?.ready ? 'Yes' : 'No'} />
                <KeyValue label="Default Provider" value={capabilities?.default_provider ?? '-'} />
                <KeyValue label="Default Model" value={capabilities?.default_model ?? '-'} />
                <KeyValue label="Recommended Lane" value={capabilities?.recommended_lane ?? '-'} />
                <KeyValue label="Selected Provider" value={selectedProviderLabel} />
                <KeyValue label="Selected Provider Ready" value={selectedProviderReady ? 'Yes' : 'No'} />
                <KeyValue label="OpenRouter" value={capabilities?.openrouter_configured ? 'Configured' : 'Missing'} />
                <KeyValue label="xAI" value={capabilities?.xai_configured ? 'Configured' : 'Missing'} />
              </div>
            )}

            {capabilities?.notes.length ? (
              <div className="mt-4 space-y-2 rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
                {capabilities.notes.slice(0, 3).map((note) => (
                  <p key={note} className="text-xs leading-5 text-gray-400">
                    {note}
                  </p>
                ))}
              </div>
            ) : null}
          </Surface>

          <Surface
            title="Current Human View"
            description="사람이 판단하기 좋은 핵심 지표만 따로 보여줍니다."
          >
            <div className="grid gap-3">
              <Metric label="Preview Source" value={activeBatchSource ?? 'none'} />
              <Metric label="Editor Dirty" value={directionEditsDirty ? 'Yes' : 'No'} accent={directionEditsDirty ? 'warn' : 'good'} />
              <Metric label="Direction Blueprints" value={`${activeBatch?.direction_pack.length ?? 0}`} accent={activeBatch?.direction_pack.length ? 'good' : 'default'} />
              <Metric label="Prompt Rows" value={`${activeBatch?.generated_count ?? 0}`} accent={activeBatch?.generated_count ? 'good' : 'default'} />
              <Metric label="Queued Generations" value={`${lastRun?.queued_generations.length ?? 0}`} accent={(lastRun?.queued_generations.length ?? 0) > 0 ? 'good' : 'default'} />
            </div>
          </Surface>

          <Surface
            title="Checkpoint Mix"
            description="현재 프리뷰 또는 최근 실행 기준 상위 checkpoint입니다."
          >
            <div className="space-y-2">
              {(topCheckpoints.length ? topCheckpoints : capabilities?.supported_lanes ?? []).slice(0, 5).map((item) => (
                <div
                  key={item}
                  className="rounded-2xl border border-gray-800 bg-gray-950 px-3 py-2 text-xs text-gray-300"
                >
                  {item}
                </div>
              ))}
              {topCheckpoints.length === 0 && (
                <p className="text-sm text-gray-500">아직 preview 결과가 없습니다.</p>
              )}
            </div>
          </Surface>
        </aside>
      </div>

      {activeBatch && (
        <>
          <Surface
            title="Latest Result"
            description="지금 사람이 읽어야 하는 결과를 direction pack과 prompt row로 나눠서 보여줍니다."
          >
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <Metric label="Mode" value={activeBatchSource === 'queued' ? 'Queued Result' : 'Preview Result'} accent={activeBatchSource === 'queued' ? 'good' : 'default'} />
              <Metric label="Generated" value={`${activeBatch.generated_count}`} accent="good" />
              <Metric label="Chunks" value={`${activeBatch.chunk_count}`} />
              <Metric label="Resolution" value={`${activeBatch.benchmark.width}×${activeBatch.benchmark.height}`} />
              <Metric label="Sampler" value={activeBatch.benchmark.sampler} />
            </div>
          </Surface>

          <Surface
            title="Favorite Cue Pack"
            description="favorites에서 복원한 비노골적 성인 연출 cue입니다. preview가 약할 때 어떤 방향으로 보강됐는지 바로 읽을 수 있습니다."
          >
            <div className="grid gap-4 xl:grid-cols-2">
              {benchmarkCueGroups.map((group) => (
                <div key={group.label} className="rounded-2xl border border-gray-800 bg-gray-950/80 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-gray-400">{group.label}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {group.values.slice(0, 5).map((value) => (
                      <span
                        key={`${group.label}-${value}`}
                        className="rounded-full border border-violet-500/25 bg-violet-500/10 px-2.5 py-1 text-[11px] text-violet-100"
                      >
                        {value}
                      </span>
                    ))}
                    {group.values.length === 0 && (
                      <span className="rounded-full border border-gray-700 bg-gray-900 px-2.5 py-1 text-[11px] text-gray-400">
                        none
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Surface>

          <div className="grid gap-6 xl:grid-cols-[1.25fr_0.95fr]">
            <Surface
              title="Prompt Rows"
              description="프롬프트를 사람 눈으로 읽기 쉽게 카드형으로 펼쳤습니다. preview가 재사용 가능한 상태면 이 결과 그대로 queue할 수 있습니다."
            >
              <div className="space-y-4">
                {previewRows.map((row) => (
                  <PromptPreviewCard key={`${row.set_no}-${row.codename}`} row={row} />
                ))}
              </div>
            </Surface>

            <Surface
              title="Direction Pack"
              description="그록이 발명한 장면 블루프린트입니다. 사람이 보기엔 이쪽이 더 빠르게 품질 판단이 됩니다."
            >
              <div className="space-y-4">
                {directionPreview.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-gray-700 bg-gray-950/80 px-4 py-6 text-sm text-gray-500">
                    Direction pass가 꺼져 있거나 아직 결과가 없습니다.
                  </div>
                ) : (
                  directionPreview.map((direction, index) => (
                    <DirectionCard key={`${direction.codename_stub}-${index}`} direction={direction} index={index} />
                  ))
                )}
              </div>
            </Surface>
          </div>
        </>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-gray-800 bg-gray-900/90 px-5 py-4">
        <div className="text-sm text-gray-400">
          Queue와 방향 검토 흐름이 분리되어 있어서, 사람이 보기 전에 생성이 바로 들어가지 않습니다.
        </div>
        <div className="flex flex-wrap gap-3">
          <Link
            to="/queue"
            className="rounded-2xl border border-gray-700 px-4 py-2 text-sm text-gray-200 transition hover:border-gray-500 hover:text-white"
          >
            Queue 보기
          </Link>
          <Link
            to="/generate"
            className="rounded-2xl border border-gray-700 px-4 py-2 text-sm text-gray-200 transition hover:border-gray-500 hover:text-white"
          >
            수동 Generate로 이동
          </Link>
        </div>
      </div>
        </>
      )}
    </div>
  )
}
