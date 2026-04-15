import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'
import { useSearchParams } from 'react-router-dom'
import {
  assembleComicEpisodePages,
  exportComicEpisodePages,
  generateComicPanelDialogues,
  getComicEpisode,
  getComicCharacterVersions,
  getComicCharacters,
  getCurrentAnimationShot,
  getProductionEpisode,
  getComicPanelRenderJobs,
  importComicStoryPlan,
  launchAnimationPreset,
  listComicEpisodes,
  queueComicPanelRenders,
  reconcileStaleAnimationJobs,
  selectComicPanelRenderAsset,
  type AnimationCurrentShotResponse,
  type AnimationReconciliationResponse,
  type AnimationShotVariantResponse,
  type StoryPlannerPlanResponse,
  type ComicEpisodeDetailResponse,
  type ComicCharacterVersionResponse,
  type ComicHandoffExportSummaryResponse,
  type ComicPageAssemblyBatchResponse,
  type ComicManuscriptProfileId,
  type ComicPageExportResponse,
  type ComicPageLayoutTemplateId,
  type ComicPanelDialogueResponse,
  type ComicPanelRenderAssetResponse,
  type ComicPanelRenderQueueResponse,
  type ComicRenderExecutionMode,
  type ComicRenderJobResponse,
} from '../api/client'
import ComicDialogueEditor from '../components/comic/ComicDialogueEditor'
import ComicEpisodeDraftPanel from '../components/comic/ComicEpisodeDraftPanel'
import ComicHandoffReviewPanel from '../components/comic/ComicHandoffReviewPanel'
import ComicPageAssemblyPanel from '../components/comic/ComicPageAssemblyPanel'
import ComicPanelBoard, { type ComicPanelRenderStatusSummary } from '../components/comic/ComicPanelBoard'
import ComicTeaserOpsPanel from '../components/comic/ComicTeaserOpsPanel'
import { notify } from '../lib/toast'

const DEFAULT_TEASER_PRESET_ID = 'sdxl_ipadapter_microanim_v2'

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as AxiosError<{ detail?: string }>)?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (error instanceof Error && error.message.trim()) return error.message
  return fallback
}

function firstPanelId(detail: ComicEpisodeDetailResponse | null): string | null {
  if (!detail) return null
  for (const sceneDetail of detail.scenes) {
    if (sceneDetail.panels[0]) return sceneDetail.panels[0].id
  }
  return null
}

function buildInitialApprovedPlanJson(): string {
  return ''
}

function isPendingComicRenderJob(job: ComicRenderJobResponse): boolean {
  return ['draft', 'queued', 'submitted', 'processing'].includes(job.status)
}

function getComicRenderJobRecency(job: ComicRenderJobResponse): number {
  const timestamp = job.updated_at
    ?? job.completed_at
    ?? job.submitted_at
    ?? job.created_at
  const parsed = Date.parse(timestamp)
  return Number.isNaN(parsed) ? 0 : parsed
}

function countPendingComicRenderJobs(renderJobs: ComicRenderJobResponse[]): number {
  return renderJobs.filter((job) => isPendingComicRenderJob(job)).length
}

function isPendingAnimationShotVariant(variant: AnimationShotVariantResponse): boolean {
  return ['draft', 'queued', 'submitted', 'processing'].includes(variant.status)
}

function getAnimationShotVariantRecency(variant: AnimationShotVariantResponse): number {
  const timestamp = variant.completed_at
    ?? variant.created_at
  const parsed = Date.parse(timestamp)
  return Number.isNaN(parsed) ? 0 : parsed
}

function findLatestAnimationShotVariant(
  variants: AnimationShotVariantResponse[],
  predicate: (variant: AnimationShotVariantResponse) => boolean,
): AnimationShotVariantResponse | null {
  let latestVariant: AnimationShotVariantResponse | null = null
  let latestRecency = -1

  for (const variant of variants) {
    if (!predicate(variant)) continue
    const recency = getAnimationShotVariantRecency(variant)
    if (recency >= latestRecency) {
      latestVariant = variant
      latestRecency = recency
    }
  }

  return latestVariant
}

function resolveAnimationOutputHref(outputPath: string | null): string | null {
  const trimmed = outputPath?.trim()
  if (!trimmed) return null
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (trimmed.startsWith('/data/')) return trimmed
  if (trimmed.startsWith('/')) return `/data${trimmed}`
  return `/data/${trimmed}`
}

function isMp4OutputPath(outputPath: string | null): boolean {
  const trimmed = outputPath?.trim()
  return Boolean(trimmed && /\.mp4(?:$|\?)/i.test(trimmed))
}

function sameComicPanelRemoteJobHint(
  left: ComicPanelRemoteJobHint | null,
  right: ComicPanelRemoteJobHint | null,
): boolean {
  if (left === right) return true
  if (!left || !right) return false
  return left.remoteJobCount === right.remoteJobCount
    && left.pendingRemoteJobCount === right.pendingRemoteJobCount
}

function mergeRemoteJobHintIntoQueueState(
  queueState: ComicPanelQueueResponseState,
  remoteJobHint: ComicPanelRemoteJobHint,
): ComicPanelQueueResponseState {
  const nextRemoteWorker = queueState.remoteWorker
    && (
      queueState.remoteWorker.remote_job_count !== remoteJobHint.remoteJobCount
      || queueState.remoteWorker.pending_render_job_count !== remoteJobHint.pendingRemoteJobCount
    )
    ? {
        ...queueState.remoteWorker,
        remote_job_count: remoteJobHint.remoteJobCount,
        pending_render_job_count: remoteJobHint.pendingRemoteJobCount,
      }
    : queueState.remoteWorker

  if (
    sameComicPanelRemoteJobHint(queueState.remoteJobHint, remoteJobHint)
    && nextRemoteWorker === queueState.remoteWorker
  ) {
    return queueState
  }

  return {
    ...queueState,
    remoteWorker: nextRemoteWorker,
    remoteJobHint,
  }
}

function buildRemoteJobHintFromRenderJobs(
  renderJobs: ComicRenderJobResponse[],
): ComicPanelRemoteJobHint {
  return {
    remoteJobCount: renderJobs.length,
    pendingRemoteJobCount: countPendingComicRenderJobs(renderJobs),
  }
}

function resolveRemoteJobHintFromRenderJobs(
  renderJobs: ComicRenderJobResponse[],
  fallbackHint: ComicPanelRemoteJobHint | null,
): ComicPanelRemoteJobHint {
  const fallbackRemoteJobCount = fallbackHint?.remoteJobCount ?? 0
  if (renderJobs.length === 0 && fallbackRemoteJobCount > 0 && fallbackHint) {
    return fallbackHint
  }
  return buildRemoteJobHintFromRenderJobs(renderJobs)
}

function getRemoteJobHintFromQueueState(
  queueState: ComicPanelQueueResponseState | null,
): ComicPanelRemoteJobHint | null {
  if (queueState?.remoteJobHint) return queueState.remoteJobHint
  if (!queueState?.remoteWorker) return null
  return {
    remoteJobCount: queueState.remoteWorker.remote_job_count,
    pendingRemoteJobCount: queueState.remoteWorker.pending_render_job_count,
  }
}

function getComicRenderJobTimelineRecency(job: ComicRenderJobResponse): number {
  const timestamp = job.created_at
    ?? job.submitted_at
    ?? job.updated_at
    ?? job.completed_at
  const parsed = Date.parse(timestamp)
  return Number.isNaN(parsed) ? 0 : parsed
}

function findLatestComicRenderJob(
  renderJobs: ComicRenderJobResponse[],
  predicate: (job: ComicRenderJobResponse) => boolean,
): ComicRenderJobResponse | null {
  let latestJob: ComicRenderJobResponse | null = null
  let latestRecency = -1

  for (const renderJob of renderJobs) {
    if (!predicate(renderJob)) continue
    const recency = getComicRenderJobRecency(renderJob)
    if (recency >= latestRecency) {
      latestJob = renderJob
      latestRecency = recency
    }
  }

  return latestJob
}

function findFirstFailedComicRenderJob(
  renderJobs: ComicRenderJobResponse[],
): ComicRenderJobResponse | null {
  let firstFailedJob: ComicRenderJobResponse | null = null

  for (const renderJob of renderJobs) {
    if (!renderJob.error_message?.trim()) continue
    if (!firstFailedJob) {
      firstFailedJob = renderJob
      continue
    }
    if (renderJob.request_index < firstFailedJob.request_index) {
      firstFailedJob = renderJob
      continue
    }
    if (renderJob.request_index === firstFailedJob.request_index) {
      const renderJobRecency = getComicRenderJobRecency(renderJob)
      const firstFailedJobRecency = getComicRenderJobRecency(firstFailedJob)
      if (renderJobRecency < firstFailedJobRecency) {
        firstFailedJob = renderJob
        continue
      }
      if (renderJobRecency === firstFailedJobRecency) {
        const renderJobTimelineRecency = getComicRenderJobTimelineRecency(renderJob)
        const firstFailedJobTimelineRecency = getComicRenderJobTimelineRecency(firstFailedJob)
        if (renderJobTimelineRecency < firstFailedJobTimelineRecency) {
          firstFailedJob = renderJob
        }
      }
    }
  }

  return firstFailedJob
}

interface ComicPanelRemoteJobHint {
  remoteJobCount: number
  pendingRemoteJobCount: number
}

interface ComicProductionContext {
  productionEpisodeId: string
  workId: string
  seriesId: string | null
  contentMode: string
}

function mergeRemoteJobOutputsIntoAssets(
  assets: ComicPanelRenderAssetResponse[],
  renderJobs: ComicRenderJobResponse[],
): ComicPanelRenderAssetResponse[] {
  if (renderJobs.length === 0) return assets

  const nextAssets = [...assets]
  const assetIndexById = new Map(
    nextAssets.map((asset, index) => [asset.id, index]),
  )
  let changed = false

  for (const renderJob of renderJobs) {
    const existingIndex = assetIndexById.get(renderJob.render_asset_id)
    if (existingIndex === undefined) {
      assetIndexById.set(renderJob.render_asset_id, nextAssets.length)
      nextAssets.push({
        id: renderJob.render_asset_id,
        scene_panel_id: renderJob.scene_panel_id,
        generation_id: renderJob.generation_id,
        asset_role: 'candidate',
        storage_path: renderJob.output_path,
        prompt_snapshot: renderJob.request_json,
        quality_score: null,
        bubble_safe_zones: [],
        crop_metadata: null,
        render_notes: null,
        is_selected: false,
        created_at: renderJob.created_at,
        updated_at: renderJob.updated_at,
      })
      changed = true
      continue
    }

    const existingAsset = nextAssets[existingIndex]
    const nextAsset = {
      ...existingAsset,
      generation_id: renderJob.generation_id ?? existingAsset.generation_id,
      storage_path: renderJob.output_path ?? existingAsset.storage_path,
      prompt_snapshot: existingAsset.prompt_snapshot ?? renderJob.request_json,
      updated_at: renderJob.updated_at ?? existingAsset.updated_at,
    }
    if (
      nextAsset.generation_id !== existingAsset.generation_id
      || nextAsset.storage_path !== existingAsset.storage_path
      || nextAsset.prompt_snapshot !== existingAsset.prompt_snapshot
      || nextAsset.updated_at !== existingAsset.updated_at
    ) {
      nextAssets[existingIndex] = nextAsset
      changed = true
    }
  }

  return changed ? nextAssets : assets
}

function mergeQueuedPanelAssets(
  existingAssets: ComicPanelRenderAssetResponse[],
  incomingAssets: ComicPanelRenderAssetResponse[],
): ComicPanelRenderAssetResponse[] {
  if (existingAssets.length === 0) return incomingAssets
  if (incomingAssets.length === 0) return existingAssets

  const nextAssets = [...existingAssets]
  const assetIndexById = new Map(
    nextAssets.map((asset, index) => [asset.id, index]),
  )

  for (const incomingAsset of incomingAssets) {
    const existingIndex = assetIndexById.get(incomingAsset.id)
    if (existingIndex === undefined) {
      assetIndexById.set(incomingAsset.id, nextAssets.length)
      nextAssets.push(incomingAsset)
      continue
    }

    const existingAsset = nextAssets[existingIndex]
    nextAssets[existingIndex] = {
      ...existingAsset,
      ...incomingAsset,
      generation_id: incomingAsset.generation_id ?? existingAsset.generation_id,
      storage_path: incomingAsset.storage_path ?? existingAsset.storage_path,
      prompt_snapshot: incomingAsset.prompt_snapshot ?? existingAsset.prompt_snapshot,
      quality_score: incomingAsset.quality_score ?? existingAsset.quality_score,
      crop_metadata: incomingAsset.crop_metadata ?? existingAsset.crop_metadata,
      render_notes: incomingAsset.render_notes ?? existingAsset.render_notes,
      is_selected: existingAsset.is_selected || incomingAsset.is_selected,
      asset_role: existingAsset.is_selected && !incomingAsset.is_selected
        ? existingAsset.asset_role
        : incomingAsset.asset_role,
    }
  }

  return nextAssets
}

interface ComicPanelQueueResponseState {
  localPreview: ComicPanelRenderQueueResponse | null
  remoteWorker: ComicPanelRenderQueueResponse | null
  latestExecutionMode: ComicRenderExecutionMode | null
  remoteJobHint: ComicPanelRemoteJobHint | null
}

function emptyComicPanelQueueResponseState(): ComicPanelQueueResponseState {
  return {
    localPreview: null,
    remoteWorker: null,
    latestExecutionMode: null,
    remoteJobHint: null,
  }
}

function buildPanelRenderStatusSummary(
  queueResponseState: ComicPanelQueueResponseState | null,
  assets: ComicPanelRenderAssetResponse[],
  renderJobs: ComicRenderJobResponse[],
  remoteJobHint: ComicPanelRemoteJobHint | null,
): ComicPanelRenderStatusSummary {
  const queueRemoteJobHint = getRemoteJobHintFromQueueState(queueResponseState)
  const remoteWorkerQueueResponse = queueResponseState?.remoteWorker ?? null
  const remoteJobCountHint = queueRemoteJobHint?.remoteJobCount
    ?? remoteWorkerQueueResponse?.remote_job_count
    ?? remoteJobHint?.remoteJobCount
    ?? 0
  const pendingRemoteJobCountHint = queueRemoteJobHint?.pendingRemoteJobCount
    ?? remoteWorkerQueueResponse?.pending_render_job_count
    ?? remoteJobHint?.pendingRemoteJobCount
    ?? 0
  const materializedAssetCount = assets.filter((asset) => Boolean(asset.storage_path)).length
  const executionMode = queueResponseState?.latestExecutionMode
    ?? (renderJobs.length > 0 || remoteJobCountHint > 0 ? 'remote_worker' : 'local_preview')

  const firstFailureJob = findFirstFailedComicRenderJob(renderJobs)
  const latestExternalJob = findLatestComicRenderJob(renderJobs, (job) => Boolean(job.external_job_url?.trim()))

  return {
    executionMode,
    materializedAssetCount,
    remoteJobCount: renderJobs.length > 0
      ? renderJobs.length
      : remoteJobCountHint,
    pendingRemoteCount: renderJobs.length > 0
      ? renderJobs.filter((job) => isPendingComicRenderJob(job)).length
      : pendingRemoteJobCountHint,
    latestFailureMessage: firstFailureJob?.error_message ?? null,
    latestExternalJobUrl: latestExternalJob?.external_job_url ?? null,
  }
}

function parseApprovedPlanJson(approvedPlanJson: string): {
  parsed: StoryPlannerPlanResponse | null
  error: string | null
} {
  const trimmed = approvedPlanJson.trim()
  if (!trimmed) {
    return {
      parsed: null,
      error: 'Paste an approved Story Planner JSON payload to enable import.',
    }
  }

  let parsedValue: unknown
  try {
    parsedValue = JSON.parse(trimmed)
  } catch {
    return {
      parsed: null,
      error: 'Approved plan JSON must be valid JSON.',
    }
  }

  if (!parsedValue || typeof parsedValue !== 'object' || Array.isArray(parsedValue)) {
    return {
      parsed: null,
      error: 'Approved plan JSON must be a single object payload.',
    }
  }

  const plan = parsedValue as Record<string, unknown>
  const requiredKeys = [
    'story_prompt',
    'lane',
    'policy_pack_id',
    'approval_token',
    'anchor_render',
    'resolved_cast',
    'location',
    'episode_brief',
    'shots',
  ]
  const missingKeys = requiredKeys.filter((key) => !(key in plan))
  if (missingKeys.length > 0) {
    return {
      parsed: null,
      error: `Approved plan JSON is missing required fields: ${missingKeys.join(', ')}.`,
    }
  }

  if (typeof plan.approval_token !== 'string' || plan.approval_token.length !== 64) {
    return {
      parsed: null,
      error: 'approval_token must be a 64-character digest from Story Planner.',
    }
  }

  if (!Array.isArray(plan.shots) || plan.shots.length !== 4) {
    return {
      parsed: null,
      error: 'shots must contain the canonical four Story Planner shots.',
    }
  }

  const shotNumbers = plan.shots.map((shot) =>
    typeof shot === 'object' && shot !== null ? (shot as { shot_no?: unknown }).shot_no : null,
  )
  if (shotNumbers.join(',') !== '1,2,3,4') {
    return {
      parsed: null,
      error: 'shots must use shot_no values 1, 2, 3, 4 in order.',
    }
  }

  return {
    parsed: plan as unknown as StoryPlannerPlanResponse,
    error: null,
  }
}

export default function ComicStudio() {
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null)
  const [selectedCharacterVersionId, setSelectedCharacterVersionId] = useState<string | null>(null)
  const [title, setTitle] = useState('Comic Episode Draft')
  const [panelMultiplier, setPanelMultiplier] = useState(2)
  const [approvedPlanJson, setApprovedPlanJson] = useState(buildInitialApprovedPlanJson())
  const [currentEpisode, setCurrentEpisode] = useState<ComicEpisodeDetailResponse | null>(null)
  const [episodeCharacterVersion, setEpisodeCharacterVersion] = useState<ComicCharacterVersionResponse | null>(null)
  const [selectedPanelId, setSelectedPanelId] = useState<string | null>(null)
  const [panelAssets, setPanelAssets] = useState<Record<string, ComicPanelRenderAssetResponse[]>>({})
  const [panelQueueResponses, setPanelQueueResponses] = useState<Record<string, ComicPanelQueueResponseState>>({})
  const [panelDialogues, setPanelDialogues] = useState<Record<string, ComicPanelDialogueResponse[]>>({})
  const [layoutTemplateId, setLayoutTemplateId] = useState<ComicPageLayoutTemplateId>('jp_2x2_v1')
  const [manuscriptProfileId, setManuscriptProfileId] = useState<ComicManuscriptProfileId>('jp_manga_rightbound_v1')
  const [handoffResult, setHandoffResult] = useState<ComicPageAssemblyBatchResponse | ComicPageExportResponse | null>(null)
  const [latestSuccessfulExportSummary, setLatestSuccessfulExportSummary] = useState<ComicHandoffExportSummaryResponse | null>(null)
  const [activeHandoffSurface, setActiveHandoffSurface] = useState<'pages' | 'handoff'>('pages')
  const [latestAnimationReconciliation, setLatestAnimationReconciliation] = useState<AnimationReconciliationResponse | null>(null)
  const [latestLaunchedTeaserLaunch, setLatestLaunchedTeaserLaunch] = useState<{
    generationId: string
    jobId: string
    animationShotId: string | null
    animationShotVariantId: string | null
  } | null>(null)
  const approvedPlanDraft = useMemo(
    () => parseApprovedPlanJson(approvedPlanJson),
    [approvedPlanJson],
  )
  const productionEpisodeId = searchParams.get('production_episode_id')?.trim() || null
  const mode = searchParams.get('mode')
  const hasProductionContext = Boolean(productionEpisodeId)
  const isCreateFromProduction = hasProductionContext && mode === 'create_from_production'
  const isOpenCurrent = hasProductionContext && mode === 'open_current'

  const charactersQuery = useQuery({
    queryKey: ['comic-characters'],
    queryFn: () => getComicCharacters(),
    refetchOnWindowFocus: false,
  })

  const activeCharacterId = selectedCharacterId ?? charactersQuery.data?.[0]?.id ?? null

  const draftCharacterVersionsQuery = useQuery({
    queryKey: ['comic-character-versions', activeCharacterId],
    queryFn: () => getComicCharacterVersions(activeCharacterId),
    enabled: Boolean(activeCharacterId),
    refetchOnWindowFocus: false,
  })

  const productionEpisodeQuery = useQuery({
    queryKey: ['comic-production-episode', productionEpisodeId],
    queryFn: () => getProductionEpisode(productionEpisodeId as string),
    enabled: isCreateFromProduction,
    refetchOnWindowFocus: false,
  })

  const linkedEpisodesQuery = useQuery({
    queryKey: ['comic-episodes', productionEpisodeId],
    queryFn: () =>
      hasProductionContext && productionEpisodeId
        ? listComicEpisodes({ production_episode_id: productionEpisodeId })
        : listComicEpisodes(),
    enabled: Boolean(productionEpisodeId),
    refetchOnWindowFocus: false,
  })

  const autoOpenEpisodeId = useMemo(() => {
    if (!isOpenCurrent) return null
    const rows = linkedEpisodesQuery.data ?? []
    if (rows.length !== 1) return null
    return rows[0].episode.id
  }, [isOpenCurrent, linkedEpisodesQuery.data])

  const linkedEpisodeDetailQuery = useQuery({
    queryKey: ['comic-episode', autoOpenEpisodeId],
    queryFn: () => getComicEpisode(autoOpenEpisodeId as string),
    enabled: Boolean(autoOpenEpisodeId),
    refetchOnWindowFocus: false,
  })
  const productionContext = useMemo<ComicProductionContext | null>(() => {
    if (!isCreateFromProduction || !productionEpisodeQuery.data) return null
    const episode = productionEpisodeQuery.data
    return {
      productionEpisodeId: episode.id,
      workId: episode.work_id,
      seriesId: episode.series_id,
      contentMode: episode.content_mode,
    }
  }, [isCreateFromProduction, productionEpisodeQuery.data])

  const effectiveCharacterVersionId = selectedCharacterVersionId ?? draftCharacterVersionsQuery.data?.[0]?.id ?? null

  const currentCharacterId = currentEpisode?.episode.character_id ?? activeCharacterId
  const currentCharacterVersionId = currentEpisode?.episode.character_version_id ?? effectiveCharacterVersionId

  const currentEpisodeCharacterVersionsQuery = useQuery({
    queryKey: ['comic-episode-character-versions', currentEpisode?.episode.character_id ?? null],
    queryFn: () => getComicCharacterVersions(currentEpisode!.episode.character_id),
    enabled: Boolean(currentEpisode?.episode.character_id),
    refetchOnWindowFocus: false,
  })

  const currentCharacter = useMemo(
    () => charactersQuery.data?.find((character) => character.id === currentCharacterId) ?? null,
    [charactersQuery.data, currentCharacterId],
  )

  const currentCharacterVersion = useMemo(
    () => {
      if (currentEpisode) {
        return currentEpisodeCharacterVersionsQuery.data?.find(
          (version) => version.id === currentCharacterVersionId,
        ) ?? episodeCharacterVersion ?? null
      }

      return draftCharacterVersionsQuery.data?.find((version) => version.id === currentCharacterVersionId) ?? null
    },
    [
      currentEpisode,
      currentEpisodeCharacterVersionsQuery.data,
      currentCharacterVersionId,
      draftCharacterVersionsQuery.data,
      episodeCharacterVersion,
    ],
  )

  const selectedSceneDetail = useMemo(() => {
    if (!currentEpisode) return null
    return currentEpisode.scenes.find((sceneDetail) =>
      sceneDetail.panels.some((panel) => panel.id === (selectedPanelId ?? firstPanelId(currentEpisode))),
    ) ?? currentEpisode.scenes[0] ?? null
  }, [currentEpisode, selectedPanelId])

  const selectedPanel = selectedSceneDetail?.panels.find(
    (panel) => panel.id === (selectedPanelId ?? firstPanelId(currentEpisode)),
  )
    ?? selectedSceneDetail?.panels[0]
    ?? null
  const currentEpisodeId = currentEpisode?.episode.id ?? null
  const allPanels = useMemo(
    () => currentEpisode?.scenes.flatMap((sceneDetail) => sceneDetail.panels) ?? [],
    [currentEpisode],
  )
  const activeEpisodeIdRef = useRef<string | null>(null)
  const activeEpisodePanelIdsRef = useRef<Set<string>>(new Set())
  const titlePrefilledProductionEpisodeIdRef = useRef<string | null>(null)
  const selectedPanelQueueResponseState = selectedPanel
    ? panelQueueResponses[selectedPanel.id] ?? emptyComicPanelQueueResponseState()
    : null
  const selectedPanelRemoteJobHint = useMemo(
    () => (selectedPanel
      ? {
          remoteJobCount: selectedPanel.remote_job_count,
          pendingRemoteJobCount: selectedPanel.pending_remote_job_count,
        }
      : null),
    [selectedPanel],
  )
  const selectedPanelTrackedRemoteJobHint = getRemoteJobHintFromQueueState(selectedPanelQueueResponseState)
    ?? selectedPanelRemoteJobHint
  const selectedPanelHasTrackedRemoteJobs = Boolean(
    selectedPanel?.id && (
      selectedPanelQueueResponseState?.remoteWorker
      || (selectedPanelTrackedRemoteJobHint?.remoteJobCount ?? 0) > 0
    ),
  )
  const applyLoadedEpisodeDetail = (episodeDetail: ComicEpisodeDetailResponse) => {
    activeEpisodeIdRef.current = episodeDetail.episode.id
    activeEpisodePanelIdsRef.current = new Set(
      episodeDetail.scenes.flatMap((sceneDetail) => sceneDetail.panels.map((panel) => panel.id)),
    )
    setCurrentEpisode(episodeDetail)
    setEpisodeCharacterVersion(null)
    setSelectedPanelId(firstPanelId(episodeDetail))
    setPanelAssets({})
    setPanelQueueResponses({})
    setPanelDialogues({})
    setHandoffResult(null)
    setLatestSuccessfulExportSummary(null)
    setActiveHandoffSurface('pages')
  }

  const clearLoadedEpisodeState = () => {
    activeEpisodeIdRef.current = null
    activeEpisodePanelIdsRef.current = new Set()
    setCurrentEpisode(null)
    setEpisodeCharacterVersion(null)
    setSelectedPanelId(null)
    setPanelAssets({})
    setPanelQueueResponses({})
    setPanelDialogues({})
    setHandoffResult(null)
    setLatestSuccessfulExportSummary(null)
    setActiveHandoffSurface('pages')
  }

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!effectiveCharacterVersionId) {
        throw new Error('Choose a character version before importing a story plan.')
      }
      if (isCreateFromProduction && !productionContext) {
        throw new Error('Production episode context must load before import.')
      }
      if (!approvedPlanDraft.parsed) {
        throw new Error(approvedPlanDraft.error ?? 'Provide a valid approved Story Planner plan.')
      }
      if (isCreateFromProduction && productionContext?.productionEpisodeId) {
        const linkedRows = await queryClient.fetchQuery({
          queryKey: ['comic-episodes', productionContext.productionEpisodeId],
          queryFn: () => listComicEpisodes({ production_episode_id: productionContext.productionEpisodeId }),
        })
        if (linkedRows.length > 0) {
          throw new Error('A comic episode is already linked to this production episode. Open the existing linked episode instead of importing a duplicate.')
        }
      }
      return importComicStoryPlan({
        approved_plan: approvedPlanDraft.parsed,
        character_version_id: effectiveCharacterVersionId,
        title,
        panel_multiplier: panelMultiplier,
        work_id: productionContext?.workId ?? null,
        series_id: productionContext?.seriesId ?? null,
        production_episode_id: productionContext?.productionEpisodeId ?? null,
      })
    },
    onSuccess: (episodeDetail) => {
      activeEpisodeIdRef.current = episodeDetail.episode.id
      activeEpisodePanelIdsRef.current = new Set(
        episodeDetail.scenes.flatMap((sceneDetail) => sceneDetail.panels.map((panel) => panel.id)),
      )
      setCurrentEpisode(episodeDetail)
      setEpisodeCharacterVersion(
        draftCharacterVersionsQuery.data?.find(
          (version) => version.id === episodeDetail.episode.character_version_id,
        ) ?? null,
      )
      setSelectedPanelId(firstPanelId(episodeDetail))
      setPanelAssets({})
      setPanelQueueResponses({})
      setPanelDialogues({})
      setHandoffResult(null)
      setLatestSuccessfulExportSummary(null)
      setActiveHandoffSurface('pages')
      notify.success('Comic episode imported')
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to import story plan'))
    },
  })

  useEffect(() => {
    activeEpisodeIdRef.current = currentEpisodeId
    activeEpisodePanelIdsRef.current = new Set(allPanels.map((panel) => panel.id))
  }, [allPanels, currentEpisodeId])

  useEffect(() => {
    if (!isCreateFromProduction) return
    if (!productionContext) return
    if (titlePrefilledProductionEpisodeIdRef.current === productionContext.productionEpisodeId) return
    setTitle(productionEpisodeQuery.data?.title ?? 'Comic Episode Draft')
    titlePrefilledProductionEpisodeIdRef.current = productionContext.productionEpisodeId
  }, [isCreateFromProduction, productionContext, productionEpisodeQuery.data?.title])

  useEffect(() => {
    if (!linkedEpisodeDetailQuery.data) return
    applyLoadedEpisodeDetail(linkedEpisodeDetailQuery.data)
  }, [linkedEpisodeDetailQuery.data])

  useEffect(() => {
    if (!isOpenCurrent) return
    const rows = linkedEpisodesQuery.data ?? []
    if (rows.length <= 1) return
    clearLoadedEpisodeState()
  }, [isOpenCurrent, linkedEpisodesQuery.data])

  const openLinkedEpisodeMutation = useMutation({
    mutationFn: (episodeId: string) => getComicEpisode(episodeId),
    onSuccess: (episodeDetail) => {
      applyLoadedEpisodeDetail(episodeDetail)
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to open linked comic episode'))
    },
  })

  const queueRenderMutation = useMutation({
    mutationFn: ({
      panelId,
      executionMode,
    }: {
      panelId: string
      executionMode: ComicRenderExecutionMode
    }) => queueComicPanelRenders(panelId, {
      candidate_count: 3,
      execution_mode: executionMode,
    }),
    onSuccess: (response, variables) => {
      if (
        !activeEpisodeIdRef.current
        || !activeEpisodePanelIdsRef.current.has(response.panel.id)
      ) {
        return
      }

      setPanelAssets((current) => {
        const existingAssets = current[response.panel.id] ?? []
        return {
          ...current,
          [response.panel.id]: mergeQueuedPanelAssets(existingAssets, response.render_assets),
        }
      })
      setPanelQueueResponses((current) => {
        const existingState = current[response.panel.id] ?? emptyComicPanelQueueResponseState()
        const nextRemoteJobHint = {
          remoteJobCount: response.remote_job_count,
          pendingRemoteJobCount: response.pending_render_job_count,
        }
        return {
          ...current,
          [response.panel.id]: response.execution_mode === 'remote_worker'
            ? {
                ...existingState,
                latestExecutionMode: response.execution_mode,
                remoteWorker: response,
                remoteJobHint: nextRemoteJobHint,
              }
            : {
                ...existingState,
                latestExecutionMode: response.execution_mode,
                localPreview: response,
                remoteJobHint: existingState.remoteJobHint,
              },
        }
      })
      setSelectedPanelId(response.panel.id)
      if (variables.executionMode === 'remote_worker') {
        void queryClient.invalidateQueries({
          queryKey: ['comic-panel-render-jobs', activeEpisodeIdRef.current, response.panel.id],
        })
      }
      notify.success(
        variables.executionMode === 'remote_worker'
          ? 'Remote comic panel render jobs queued'
          : 'Comic panel local previews queued',
      )
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to queue comic panel renders'))
    },
  })

  const selectAssetMutation = useMutation({
    mutationFn: ({ panelId, assetId }: { panelId: string; assetId: string }) =>
      selectComicPanelRenderAsset(panelId, assetId),
    onSuccess: (asset, variables) => {
      setPanelAssets((current) => {
        const previousAssets = current[variables.panelId] ?? []
        const nextAssets = previousAssets.map((candidate) =>
          candidate.id === asset.id
            ? asset
            : { ...candidate, is_selected: false },
        )
        if (!nextAssets.some((candidate) => candidate.id === asset.id)) {
          nextAssets.push(asset)
        }
        return {
          ...current,
          [variables.panelId]: nextAssets,
        }
      })
      notify.success('Selected panel asset updated')
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to select panel asset'))
    },
  })

  const dialogueMutation = useMutation({
    mutationFn: (panelId: string) => generateComicPanelDialogues(panelId),
    onSuccess: (response) => {
      setPanelDialogues((current) => ({
        ...current,
        [response.panel.id]: response.dialogues,
      }))
      setSelectedPanelId(response.panel.id)
      notify.success('Panel dialogues generated')
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to generate panel dialogues'))
    },
  })

  const assembleMutation = useMutation({
    mutationFn: (episodeId: string) => assembleComicEpisodePages(episodeId, layoutTemplateId, manuscriptProfileId),
    onSuccess: (response) => {
      setCurrentEpisode((current) =>
        current
          ? {
              ...current,
              pages: response.pages,
            }
          : current,
      )
      setHandoffResult(response)
      setLatestSuccessfulExportSummary(null)
      setActiveHandoffSurface('handoff')
      notify.success('Comic pages assembled')
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to assemble comic pages'))
    },
  })

  const exportMutation = useMutation({
    mutationFn: (episodeId: string) => exportComicEpisodePages(episodeId, layoutTemplateId, manuscriptProfileId),
    onSuccess: (response) => {
      setCurrentEpisode((current) =>
        current
          ? {
              ...current,
              pages: response.pages,
            }
          : current,
      )
      setHandoffResult(response)
      setLatestSuccessfulExportSummary(response.latest_export_summary)
      setActiveHandoffSurface('handoff')
      notify.success('Comic handoff ZIP exported')
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to export comic handoff ZIP'))
    },
  })

  const selectedPanelRenderJobsQuery = useQuery({
    queryKey: ['comic-panel-render-jobs', currentEpisodeId, selectedPanel?.id ?? null],
    queryFn: () => getComicPanelRenderJobs(selectedPanel!.id),
    enabled: selectedPanelHasTrackedRemoteJobs,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      const latestJobs = (query.state.data as ComicRenderJobResponse[] | undefined)
        ?? []
      const fallbackRemoteJobHint = getRemoteJobHintFromQueueState(selectedPanelQueueResponseState)
        ?? selectedPanelRemoteJobHint
      if (query.state.data !== undefined) {
        if (latestJobs.some((job) => isPendingComicRenderJob(job))) return 2000
        return (latestJobs.length === 0 && (fallbackRemoteJobHint?.pendingRemoteJobCount ?? 0) > 0)
          ? 2000
          : false
      }
      const pendingRemoteJobCount = fallbackRemoteJobHint?.pendingRemoteJobCount
        ?? 0
      return pendingRemoteJobCount > 0 ? 2000 : false
    },
  })

  useEffect(() => {
    if (!currentEpisodeId || !selectedPanel?.id || selectedPanelRenderJobsQuery.data === undefined) return
    const panelId = selectedPanel.id
    const renderJobs = selectedPanelRenderJobsQuery.data
    queueMicrotask(() => {
      setPanelAssets((current) => {
        const currentAssets = current[panelId] ?? []
        const nextAssets = mergeRemoteJobOutputsIntoAssets(currentAssets, renderJobs)
        if (nextAssets === currentAssets) return current
        return {
          ...current,
          [panelId]: nextAssets,
        }
      })

      setPanelQueueResponses((current) => {
        const existingState = current[panelId] ?? emptyComicPanelQueueResponseState()
        const existingRemoteJobHint = getRemoteJobHintFromQueueState(existingState)
        const remoteJobHint = resolveRemoteJobHintFromRenderJobs(
          renderJobs,
          existingRemoteJobHint ?? selectedPanelRemoteJobHint,
        )
        const nextState = mergeRemoteJobHintIntoQueueState(existingState, remoteJobHint)
        if (nextState === existingState) return current
        return {
          ...current,
          [panelId]: nextState,
        }
      })
    })
  }, [currentEpisodeId, selectedPanel?.id, selectedPanelRemoteJobHint, selectedPanelRenderJobsQuery.data])

  const availableVersions = draftCharacterVersionsQuery.data ?? []
  const selectedPanelRenderJobs = selectedPanelRenderJobsQuery.data ?? []
  const selectedPanelResolvedRemoteJobHint = selectedPanelRenderJobsQuery.data !== undefined
    ? resolveRemoteJobHintFromRenderJobs(
        selectedPanelRenderJobs,
        getRemoteJobHintFromQueueState(selectedPanelQueueResponseState) ?? selectedPanelRemoteJobHint,
      )
    : getRemoteJobHintFromQueueState(selectedPanelQueueResponseState) ?? selectedPanelRemoteJobHint
  const panelHasSelectedAsset = (panelId: string): boolean =>
    (panelAssets[panelId] ?? []).some((asset) => asset.is_selected)
  const panelHasMaterializedSelectedAsset = (panelId: string): boolean =>
    (panelAssets[panelId] ?? []).some((asset) => asset.is_selected && Boolean(asset.storage_path))

  const selectedPanelHasSelectedAsset = selectedPanel ? panelHasSelectedAsset(selectedPanel.id) : false
  const selectedPanelHasMaterializedSelectedAsset = selectedPanel
    ? panelHasMaterializedSelectedAsset(selectedPanel.id)
    : false
  const selectedPanelSelectedAsset = selectedPanel
    ? (panelAssets[selectedPanel.id] ?? []).find((asset) => asset.is_selected) ?? null
    : null
  const selectedPanelSelectedAssetId = selectedPanelSelectedAsset?.id ?? null
  const selectedPanelSelectedGenerationId = selectedPanelSelectedAsset?.generation_id ?? null
  const selectedPanelHasQueuedRenders = selectedPanel ? (panelAssets[selectedPanel.id]?.length ?? 0) > 0 : false
  const allPanelsHaveMaterializedSelectedAssets = allPanels.length > 0
    && allPanels.every((panel) => panelHasMaterializedSelectedAsset(panel.id))
  const canGenerateDialogues = Boolean(selectedPanel && selectedPanelHasMaterializedSelectedAsset)
  const canAssemblePages = Boolean(currentEpisode && allPanelsHaveMaterializedSelectedAssets)
  const handoffHardBlockCount = handoffResult?.handoff_validation.hard_blocks.length ?? 0
  const canExportPages = Boolean(
    currentEpisode
    && currentEpisode.pages.length > 0
    && allPanelsHaveMaterializedSelectedAssets
    && handoffResult
    && handoffHardBlockCount === 0,
  )
  const isCreateFromProductionContextReady = Boolean(isCreateFromProduction && productionContext)
  const createFromProductionLinkedRows = isCreateFromProduction ? (linkedEpisodesQuery.data ?? []) : []
  const hasLinkedEpisodesForCreateFromProduction = createFromProductionLinkedRows.length > 0
  const isCreateFromProductionLinkageLoading = Boolean(
    isCreateFromProduction && linkedEpisodesQuery.isLoading && !linkedEpisodesQuery.data,
  )
  const isImportBlockedByCreateFromProduction = Boolean(
    isCreateFromProduction
    && (
      !isCreateFromProductionContextReady
      || hasLinkedEpisodesForCreateFromProduction
      || isCreateFromProductionLinkageLoading
    ),
  )
  const openCurrentAmbiguousRows = isOpenCurrent
    ? (linkedEpisodesQuery.data ?? []).filter((row) => row.episode.id !== autoOpenEpisodeId)
    : []
  const canImportStoryPlan = Boolean(
    effectiveCharacterVersionId
    && approvedPlanDraft.parsed
    && !isImportBlockedByCreateFromProduction,
  )
  const importValidationMessage = isImportBlockedByCreateFromProduction
    ? (
      hasLinkedEpisodesForCreateFromProduction
        ? 'A comic episode is already linked to this production episode. Open the linked episode below instead of importing a duplicate.'
      : isCreateFromProductionLinkageLoading
        ? 'Checking linked comic episodes for this production episode before import.'
      : productionEpisodeQuery.isError
        ? 'Production episode context failed to load; retry before import.'
        : 'Loading production episode context before import.'
    )
    : !effectiveCharacterVersionId
    ? 'Choose a character version before importing a story plan.'
    : approvedPlanDraft.error
  const dialogueReadinessMessage = !selectedPanel
    ? null
    : !selectedPanelHasQueuedRenders
      ? 'Queue renders for this panel before drafting dialogues.'
      : !selectedPanelHasSelectedAsset
        ? 'Select a winning render for this panel before drafting dialogues.'
        : !selectedPanelHasMaterializedSelectedAsset
          ? 'Wait for the selected render file to finish materializing before drafting dialogues.'
          : null
  const pageAssemblyReadinessMessage = !currentEpisode
    ? null
    : !allPanelsHaveMaterializedSelectedAssets
      ? 'Select a winning render for every panel before assembling pages or exporting the handoff ZIP. Layout template = page composition. Manuscript profile = print/handoff intent.'
      : currentEpisode.pages.length === 0
        ? 'Run page assembly before exporting the handoff ZIP. Layout template = page composition. Manuscript profile = print/handoff intent.'
        : null
  const handoffReadinessMessage = !currentEpisode
    ? null
    : currentEpisode.pages.length === 0
      ? 'Run page assembly before handoff review and export.'
      : handoffHardBlockCount > 0
        ? 'Hard blocks must be resolved before export.'
        : (handoffResult?.handoff_validation.soft_warnings.length ?? 0) > 0
          ? 'Review warnings, then export when ready.'
          : 'Layered handoff package is ready for export.'
  const teaserReadinessMessage = !selectedPanel
    ? null
    : !selectedPanelHasSelectedAsset
      ? 'Select a winning render for this panel before launching teaser animation.'
      : !selectedPanelHasMaterializedSelectedAsset
        ? 'Wait for the selected render file to finish materializing before launching teaser animation.'
        : !selectedPanelSelectedGenerationId
          ? 'Selected render is missing a generation id, so teaser rerun is unavailable.'
          : null
  const selectedDialogues = selectedPanel ? panelDialogues[selectedPanel.id] ?? [] : []

  const selectedPanelCurrentShotQuery = useQuery({
    queryKey: ['comic-current-shot', currentEpisodeId, selectedPanel?.id ?? null, selectedPanelSelectedAssetId],
    queryFn: () => getCurrentAnimationShot({
      scene_panel_id: selectedPanel!.id,
      selected_render_asset_id: selectedPanelSelectedAssetId!,
      limit: 8,
    }),
    enabled: Boolean(selectedPanelSelectedAssetId && selectedPanelHasMaterializedSelectedAsset),
    refetchOnWindowFocus: false,
    refetchInterval: (query) => {
      const variants = (query.state.data as AnimationCurrentShotResponse | null | undefined)?.variants ?? []
      return variants.some((variant) => isPendingAnimationShotVariant(variant)) ? 2000 : false
    },
  })

  const reconcileAnimationMutation = useMutation({
    mutationFn: () => reconcileStaleAnimationJobs(),
    onSuccess: (response) => {
      setLatestAnimationReconciliation(response)
      void queryClient.invalidateQueries({
        queryKey: ['comic-current-shot'],
      })
      notify.success('Stale animation jobs reconciled')
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to reconcile stale animation jobs'))
    },
  })

  const rerunTeaserMutation = useMutation({
    mutationFn: () => {
      if (!currentEpisode?.episode.id || !selectedPanel?.id || !selectedPanelSelectedAssetId || !selectedPanelSelectedGenerationId) {
        throw new Error('Select a materialized render before launching teaser animation.')
      }
      return launchAnimationPreset(DEFAULT_TEASER_PRESET_ID, {
        generation_id: selectedPanelSelectedGenerationId,
        episode_id: currentEpisode.episode.id,
        scene_panel_id: selectedPanel.id,
        selected_render_asset_id: selectedPanelSelectedAssetId,
        dispatch_immediately: true,
        request_overrides: {},
      })
    },
    onSuccess: (response) => {
      if (selectedPanelSelectedGenerationId) {
        setLatestLaunchedTeaserLaunch({
          generationId: selectedPanelSelectedGenerationId,
          jobId: response.animation_job.id,
          animationShotId: response.animation_shot_id,
          animationShotVariantId: response.animation_shot_variant_id,
        })
      }
      void queryClient.invalidateQueries({
        queryKey: ['comic-current-shot', currentEpisodeId, selectedPanel?.id ?? null, selectedPanelSelectedAssetId],
      })
      notify.success(`Teaser rerun launched (${response.animation_job.id})`)
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to launch teaser animation'))
    },
  })

  const selectedPanelCurrentShot = selectedPanelCurrentShotQuery.data?.shot ?? null
  const selectedPanelCurrentShotVariants = useMemo(
    () => [...(selectedPanelCurrentShotQuery.data?.variants ?? [])].sort(
      (left, right) => getAnimationShotVariantRecency(right) - getAnimationShotVariantRecency(left),
    ),
    [selectedPanelCurrentShotQuery.data],
  )
  const latestSuccessfulTeaserVariant = useMemo(
    () => findLatestAnimationShotVariant(
      selectedPanelCurrentShotVariants,
      (variant) => variant.status === 'completed' && isMp4OutputPath(variant.output_path),
    ),
    [selectedPanelCurrentShotVariants],
  )
  const latestFailedTeaserVariant = useMemo(
    () => findLatestAnimationShotVariant(
      selectedPanelCurrentShotVariants,
      (variant) => variant.status === 'failed' && Boolean(variant.error_message?.trim()),
    ),
    [selectedPanelCurrentShotVariants],
  )
  const latestSuccessfulTeaserVariantHref = latestSuccessfulTeaserVariant
    ? resolveAnimationOutputHref(latestSuccessfulTeaserVariant.output_path)
    : null
  const selectedPanelSelectedAssetHref = selectedPanelSelectedAsset
    ? resolveAnimationOutputHref(selectedPanelSelectedAsset.storage_path)
    : null
  const latestLaunchedTeaserJobId = latestLaunchedTeaserLaunch?.generationId === selectedPanelSelectedGenerationId
    ? latestLaunchedTeaserLaunch.jobId
    : null
  const latestLaunchedTeaserShotId = latestLaunchedTeaserLaunch?.generationId === selectedPanelSelectedGenerationId
    ? latestLaunchedTeaserLaunch.animationShotId
    : null
  const latestLaunchedTeaserVariantId = latestLaunchedTeaserLaunch?.generationId === selectedPanelSelectedGenerationId
    ? latestLaunchedTeaserLaunch.animationShotVariantId
    : null
  const currentShotErrorMessage = selectedPanelCurrentShotQuery.error
    ? getErrorMessage(selectedPanelCurrentShotQuery.error, 'Failed to load teaser shot')
    : null
  const panelRenderStatuses = Object.fromEntries(
    allPanels.map((panel) => [
      panel.id,
        buildPanelRenderStatusSummary(
          panelQueueResponses[panel.id] ?? null,
          panelAssets[panel.id] ?? [],
          panel.id === selectedPanel?.id ? selectedPanelRenderJobs : [],
          panel.id === selectedPanel?.id
            ? selectedPanelResolvedRemoteJobHint
            : {
                remoteJobCount: panel.remote_job_count,
                pendingRemoteJobCount: panel.pending_remote_job_count,
              },
        ),
      ]),
  ) as Record<string, ComicPanelRenderStatusSummary>

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <span className="inline-flex rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-violet-300">
              Character OS Comic MVP
            </span>
            <div>
              <h1 className="text-2xl font-bold text-gray-100">Comic Studio</h1>
              <p className="mt-1 text-sm font-medium text-violet-200">Comic Handoff Workspace</p>
              <p className="mt-1 max-w-3xl text-sm text-gray-400">
                Import one approved Story Planner episode, keep lineage visible from character version to panel, and drive render, dialogue, and Japanese page handoff steps in one workspace.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-gray-500">Scenes</p>
              <p className="mt-1 text-2xl font-semibold text-gray-100">{currentEpisode?.scenes.length ?? 0}</p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-gray-500">Panels</p>
              <p className="mt-1 text-2xl font-semibold text-gray-100">
                {currentEpisode?.scenes.reduce((total, sceneDetail) => total + sceneDetail.panels.length, 0) ?? 0}
              </p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-gray-500">Dialogues</p>
              <p className="mt-1 text-2xl font-semibold text-gray-100">
                {Object.values(panelDialogues).reduce((total, dialogues) => total + dialogues.length, 0)}
              </p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-gray-500">Pages</p>
              <p className="mt-1 text-2xl font-semibold text-gray-100">{currentEpisode?.pages.length ?? 0}</p>
            </div>
          </div>
        </div>
      </section>

      {hasLinkedEpisodesForCreateFromProduction && (
        <section className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-200">Duplicate Import Blocked</h2>
          <p className="mt-2 text-sm text-amber-50/90">
            A comic episode is already linked to this production episode. Open the existing linked episode manually instead of importing another track.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {createFromProductionLinkedRows.map((row) => (
              <button
                key={row.episode.id}
                type="button"
                onClick={() => openLinkedEpisodeMutation.mutate(row.episode.id)}
                disabled={openLinkedEpisodeMutation.isPending}
                className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-100 hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Open Existing Linked Episode {row.episode.title}
              </button>
            ))}
          </div>
        </section>
      )}

      {openCurrentAmbiguousRows.length > 0 && (
        <section className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-amber-200">Open Current Ambiguity</h2>
          <p className="mt-2 text-sm text-amber-50/90">
            Multiple comic episodes are linked to this production episode. Select one to open manually.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {openCurrentAmbiguousRows.map((row) => (
              <button
                key={row.episode.id}
                type="button"
                onClick={() => openLinkedEpisodeMutation.mutate(row.episode.id)}
                disabled={openLinkedEpisodeMutation.isPending}
                className="rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-xs font-medium text-amber-100 hover:bg-amber-500/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Open {row.episode.title}
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,430px)_minmax(0,1fr)]">
        <ComicEpisodeDraftPanel
          characters={charactersQuery.data ?? []}
          characterVersions={availableVersions}
          selectedCharacterId={activeCharacterId}
          selectedCharacterVersionId={effectiveCharacterVersionId}
          title={title}
          panelMultiplier={panelMultiplier}
          approvedPlanJson={approvedPlanJson}
          productionContext={productionContext}
          canImport={canImportStoryPlan}
          importValidationMessage={importValidationMessage}
          isLoadingCatalog={charactersQuery.isLoading || draftCharacterVersionsQuery.isLoading}
          isImporting={importMutation.isPending}
          onCharacterChange={(characterId) => {
            setSelectedCharacterId(characterId || null)
            setSelectedCharacterVersionId(null)
          }}
          onCharacterVersionChange={(characterVersionId) => setSelectedCharacterVersionId(characterVersionId || null)}
          onTitleChange={setTitle}
          onPanelMultiplierChange={(value) => setPanelMultiplier(Number.isFinite(value) ? Math.max(1, Math.min(8, value)) : 2)}
          onApprovedPlanJsonChange={setApprovedPlanJson}
          onImport={() => importMutation.mutate()}
        />

        <ComicPanelBoard
          episode={currentEpisode}
          selectedPanelId={selectedPanel?.id ?? null}
          panelAssets={panelAssets}
          panelRenderStatuses={panelRenderStatuses}
          characterName={currentCharacter?.name ?? null}
          characterVersionName={currentCharacterVersion?.version_name ?? null}
          queueingPanelId={queueRenderMutation.isPending ? queueRenderMutation.variables?.panelId ?? null : null}
          queueingExecutionMode={queueRenderMutation.isPending ? queueRenderMutation.variables?.executionMode ?? null : null}
          selectingAssetId={selectAssetMutation.variables?.assetId ?? null}
          onSelectPanel={setSelectedPanelId}
          onQueueRenders={(panelId, executionMode) => queueRenderMutation.mutate({ panelId, executionMode })}
          onSelectAsset={(panelId, assetId) => selectAssetMutation.mutate({ panelId, assetId })}
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
        <ComicDialogueEditor
          episodeTitle={currentEpisode?.episode.title ?? null}
          sceneNo={selectedSceneDetail?.scene.scene_no ?? null}
          selectedPanel={selectedPanel}
          characterName={currentCharacter?.name ?? null}
          characterVersionName={currentCharacterVersion?.version_name ?? null}
          dialogues={selectedDialogues}
          canGenerate={canGenerateDialogues}
          readinessMessage={dialogueReadinessMessage}
          isGenerating={dialogueMutation.isPending}
          onGenerate={(panelId) => dialogueMutation.mutate(panelId)}
        />
        <div className="space-y-6">
          <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wide text-gray-500">Workflow</p>
                <h2 className="mt-1 text-lg font-semibold text-gray-100">Assemble -&gt; Handoff Review -&gt; Export</h2>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setActiveHandoffSurface('pages')}
                  className={[
                    'rounded-full border px-3 py-1.5 text-xs font-medium uppercase tracking-wide transition',
                    activeHandoffSurface === 'pages'
                      ? 'border-sky-500/40 bg-sky-500/10 text-sky-200'
                      : 'border-gray-700 bg-gray-950/70 text-gray-300 hover:border-sky-500/30 hover:text-sky-100',
                  ].join(' ')}
                >
                  Pages
                </button>
                <button
                  type="button"
                  onClick={() => setActiveHandoffSurface('handoff')}
                  className={[
                    'rounded-full border px-3 py-1.5 text-xs font-medium uppercase tracking-wide transition',
                    activeHandoffSurface === 'handoff'
                      ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200'
                      : 'border-gray-700 bg-gray-950/70 text-gray-300 hover:border-emerald-500/30 hover:text-emerald-100',
                  ].join(' ')}
                >
                  Handoff
                </button>
              </div>
            </div>
          </section>

          <ComicPageAssemblyPanel
            episode={currentEpisode}
            layoutTemplateId={layoutTemplateId}
            manuscriptProfileId={manuscriptProfileId}
            canAssemble={canAssemblePages}
            readinessMessage={pageAssemblyReadinessMessage}
            isAssembling={assembleMutation.isPending}
            layeredManifestPath={handoffResult?.layered_manifest_path ?? null}
            handoffValidationPath={handoffResult?.handoff_validation_path ?? null}
            isActive={activeHandoffSurface === 'pages'}
            onLayoutTemplateChange={setLayoutTemplateId}
            onManuscriptProfileChange={setManuscriptProfileId}
            onAssemble={(episodeId) => assembleMutation.mutate(episodeId)}
          />

          <ComicHandoffReviewPanel
            episode={currentEpisode}
            validation={handoffResult?.handoff_validation ?? null}
            pageSummaries={handoffResult?.page_summaries ?? []}
            layeredManifestPath={handoffResult?.layered_manifest_path ?? null}
            handoffValidationPath={handoffResult?.handoff_validation_path ?? null}
            latestExportSummary={latestSuccessfulExportSummary}
            canExport={canExportPages}
            readinessMessage={handoffReadinessMessage}
            isExporting={exportMutation.isPending}
            isActive={activeHandoffSurface === 'handoff'}
            onExport={(episodeId) => exportMutation.mutate(episodeId)}
          />

          <ComicTeaserOpsPanel
            selectedPanel={selectedPanel}
            selectedAssetPath={selectedPanelSelectedAsset?.storage_path ?? null}
            selectedAssetGenerationId={selectedPanelSelectedGenerationId}
            selectedAssetOutputHref={selectedPanelSelectedAssetHref}
            currentShot={selectedPanelCurrentShot}
            currentShotErrorMessage={currentShotErrorMessage}
            currentShotVariants={selectedPanelCurrentShotVariants}
            latestFailedVariant={latestFailedTeaserVariant}
            latestSuccessfulVariant={latestSuccessfulTeaserVariant}
            latestSuccessfulVariantHref={latestSuccessfulTeaserVariantHref}
            latestReconcileSummary={latestAnimationReconciliation}
            latestLaunchedTeaserJobId={latestLaunchedTeaserJobId}
            latestLaunchedTeaserShotId={latestLaunchedTeaserShotId}
            latestLaunchedTeaserVariantId={latestLaunchedTeaserVariantId}
            presetId={DEFAULT_TEASER_PRESET_ID}
            readinessMessage={teaserReadinessMessage}
            canRerun={Boolean(!teaserReadinessMessage && selectedPanelSelectedGenerationId)}
            isReconciling={reconcileAnimationMutation.isPending}
            isRerunning={rerunTeaserMutation.isPending}
            onReconcile={() => reconcileAnimationMutation.mutate()}
            onRerun={() => rerunTeaserMutation.mutate()}
          />
        </div>
      </div>
    </div>
  )
}
