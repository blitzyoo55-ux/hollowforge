import type { ReactNode } from 'react'
import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import axios from 'axios'

import {
  generateStoryPlannerAnchors,
  getStoryPlannerCatalog,
  planStoryEpisode,
  type StoryPlannerAnchorQueueResponse,
  type StoryPlannerLane,
  type StoryPlannerPlanRequest,
  type StoryPlannerPlanResponse,
  type StoryPlannerPreferredAnchorBeat,
} from '../../../api/client'
import { notify } from '../../../lib/toast'
import StoryPlannerAnchorResults from './StoryPlannerAnchorResults'
import StoryPlannerInputPanel from './StoryPlannerInputPanel'
import StoryPlannerPlanReview from './StoryPlannerPlanReview'

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ERR_NETWORK' || !error.response) {
      return 'Story Planner backend에 연결할 수 없습니다. backend 서버와 /api/v1 프록시 상태를 확인하세요.'
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

function buildPlanRequest({
  storyPrompt,
  lane,
  useRegistryCharacters,
  leadCharacterId,
  supportCharacterId,
  supportLockMode,
  supportFreeformDescription,
  locationId,
  preferredAnchorBeat,
}: {
  storyPrompt: string
  lane: StoryPlannerLane
  useRegistryCharacters: boolean
  leadCharacterId: string
  supportCharacterId: string
  supportLockMode: 'unlocked' | 'registry' | 'freeform'
  supportFreeformDescription: string
  locationId: string
  preferredAnchorBeat: StoryPlannerPreferredAnchorBeat
}) {
  const cast: StoryPlannerPlanRequest['cast'] = []

  const trimmedLeadCharacterId = leadCharacterId.trim()
  const trimmedSupportCharacterId = supportCharacterId.trim()
  const trimmedSupportFreeformDescription = supportFreeformDescription.trim()

  if (useRegistryCharacters && trimmedLeadCharacterId) {
    cast.push({
      role: 'lead' as const,
      source_type: 'registry' as const,
      character_id: trimmedLeadCharacterId,
    })
  }

  if (supportLockMode === 'registry' && trimmedSupportCharacterId) {
    cast.push({
      role: 'support' as const,
      source_type: 'registry' as const,
      character_id: trimmedSupportCharacterId,
    })
  }

  if (supportLockMode === 'freeform' && trimmedSupportFreeformDescription) {
    cast.push({
      role: 'support' as const,
      source_type: 'freeform' as const,
      freeform_description: trimmedSupportFreeformDescription,
    })
  }

  return {
    story_prompt: storyPrompt.trim(),
    lane,
    cast,
    location_id: locationId.trim() || null,
    preferred_anchor_beat: preferredAnchorBeat,
  }
}

function getSubmittedCastCount({
  useRegistryCharacters,
  leadCharacterId,
  supportLockMode,
  supportCharacterId,
  supportFreeformDescription,
}: {
  useRegistryCharacters: boolean
  leadCharacterId: string
  supportLockMode: 'unlocked' | 'registry' | 'freeform'
  supportCharacterId: string
  supportFreeformDescription: string
}) {
  let count = 0

  if (useRegistryCharacters && leadCharacterId.trim()) {
    count += 1
  }
  if (supportLockMode === 'registry' && supportCharacterId.trim()) {
    count += 1
  }
  if (supportLockMode === 'freeform' && supportFreeformDescription.trim()) {
    count += 1
  }

  return count
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
      <div className="mt-2 break-all text-sm font-semibold">{value}</div>
    </div>
  )
}

function StoryPlannerShell({
  children,
}: {
  children: ReactNode
}) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(99,102,241,0.12),_transparent_32%),linear-gradient(180deg,_#020617_0%,_#0f172a_100%)] text-gray-100">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        {children}
      </div>
    </div>
  )
}

export default function StoryPlannerMode() {
  const [storyPrompt, setStoryPrompt] = useState('')
  const [lane, setLane] = useState<StoryPlannerLane>('unrestricted')
  const [useRegistryCharacters, setUseRegistryCharacters] = useState(false)
  const [leadCharacterId, setLeadCharacterId] = useState('')
  const [supportCharacterId, setSupportCharacterId] = useState('')
  const [locationId, setLocationId] = useState('')
  const [preferredAnchorBeat, setPreferredAnchorBeat] = useState<StoryPlannerPreferredAnchorBeat>('auto')
  const [supportLockMode, setSupportLockMode] = useState<'unlocked' | 'registry' | 'freeform'>('unlocked')
  const [supportFreeformDescription, setSupportFreeformDescription] = useState('')
  const [plannedEpisode, setPlannedEpisode] = useState<StoryPlannerPlanResponse | null>(null)
  const [queuedResult, setQueuedResult] = useState<StoryPlannerAnchorQueueResponse | null>(null)
  const draftVersionRef = useRef(0)
  const planRequestIdRef = useRef(0)
  const queueRequestIdRef = useRef(0)

  const {
    data: catalog,
    isLoading: catalogLoading,
    error: catalogError,
  } = useQuery({
    queryKey: ['story-planner-catalog'],
    queryFn: getStoryPlannerCatalog,
    staleTime: 60_000,
  })

  const leadCharacter = useMemo(
    () => catalog?.characters.find((character) => character.id === leadCharacterId) ?? null,
    [catalog, leadCharacterId],
  )
  const supportCharacter = useMemo(
    () => catalog?.characters.find((character) => character.id === supportCharacterId) ?? null,
    [catalog, supportCharacterId],
  )
  const location = useMemo(
    () => catalog?.locations.find((entry) => entry.id === locationId) ?? null,
    [catalog, locationId],
  )

  const clearPlannedResults = () => {
    draftVersionRef.current += 1
    setPlannedEpisode(null)
    setQueuedResult(null)
  }

  const planMutation = useMutation({
    mutationFn: async ({
      draftVersion,
      requestId,
      payload,
    }: {
      draftVersion: number
      requestId: number
      payload: StoryPlannerPlanRequest
    }) => ({
      draftVersion,
      requestId,
      response: await planStoryEpisode(payload),
    }),
    onSuccess: ({ draftVersion, requestId, response }) => {
      if (draftVersion !== draftVersionRef.current || requestId !== planRequestIdRef.current) {
        return
      }
      setPlannedEpisode(response)
      setQueuedResult(null)
      notify.success('Story episode plan generated.')
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Story Planner preview 실행에 실패했습니다.'))
    },
  })

  const generateMutation = useMutation({
    mutationFn: async ({
      approvedPlan,
      draftVersion,
      requestId,
    }: {
      approvedPlan: StoryPlannerPlanResponse
      draftVersion: number
      requestId: number
    }) => ({
      draftVersion,
      requestId,
      response: await generateStoryPlannerAnchors({
        approved_plan: approvedPlan,
        candidate_count: 2,
      }),
    }),
    onSuccess: ({ draftVersion, requestId, response }) => {
      if (draftVersion !== draftVersionRef.current || requestId !== queueRequestIdRef.current) {
        return
      }
      setQueuedResult(response)
      notify.success(`${response.queued_generation_count}개의 anchor render를 큐에 등록했습니다.`)
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Story Planner anchor queue 실행에 실패했습니다.'))
    },
  })

  const handlePlanSubmit = () => {
    const requestId = planRequestIdRef.current + 1
    planRequestIdRef.current = requestId
    const draftVersion = draftVersionRef.current
    planMutation.mutate({
      draftVersion,
      requestId,
      payload: buildPlanRequest({
        storyPrompt,
        lane,
        useRegistryCharacters,
        leadCharacterId,
        supportCharacterId,
        supportLockMode,
        supportFreeformDescription,
        locationId,
        preferredAnchorBeat,
      }),
    })
  }

  const handleApproveAndGenerate = () => {
    if (!plannedEpisode) {
      return
    }
    const requestId = queueRequestIdRef.current + 1
    queueRequestIdRef.current = requestId
    const draftVersion = draftVersionRef.current
    generateMutation.mutate({
      approvedPlan: plannedEpisode,
      draftVersion,
      requestId,
    })
  }

  const catalogMetrics = [
    { label: 'Characters', value: `${catalog?.characters.length ?? 0}`, accent: 'default' as const },
    { label: 'Locations', value: `${catalog?.locations.length ?? 0}`, accent: 'default' as const },
    { label: 'Policy Packs', value: `${catalog?.policy_packs.length ?? 0}`, accent: 'default' as const },
    {
      label: 'Registry Cast',
      value: `${getSubmittedCastCount({
        useRegistryCharacters,
        leadCharacterId,
        supportLockMode,
        supportCharacterId,
        supportFreeformDescription,
      })}/2`,
      accent:
        getSubmittedCastCount({
          useRegistryCharacters,
          leadCharacterId,
          supportLockMode,
          supportCharacterId,
          supportFreeformDescription,
        }) > 0
          ? 'good'
          : 'default',
    },
  ] as const

  return (
    <StoryPlannerShell>
      <section className="rounded-3xl border border-white/10 bg-gray-950/90 p-6 shadow-2xl shadow-black/20">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-[11px] uppercase tracking-[0.18em] text-violet-200/80">Prompt Factory / Story Planner</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">Story Planner</h1>
            <p className="mt-3 text-sm leading-6 text-gray-300">
              Draft an episode, resolve the lane and cast, approve the preview, and queue four anchor stills with one pass.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {catalogMetrics.map((metric) => (
              <Metric
                key={metric.label}
                label={metric.label}
                value={metric.value}
                accent={metric.accent}
              />
            ))}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-violet-100">
            Story Planner
          </span>
          <span className="rounded-full border border-gray-700 bg-gray-950 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-gray-300">
            Advanced Batch
          </span>
          <span className="cursor-not-allowed rounded-full border border-gray-800 bg-gray-950 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-gray-500 opacity-70">
            Character Profile - Coming Soon
          </span>
        </div>
      </section>

      {catalogLoading ? (
        <section className="rounded-3xl border border-white/10 bg-gray-950/90 p-6 text-sm text-gray-400">
          Loading Story Planner catalog...
        </section>
      ) : catalogError ? (
        <section className="rounded-3xl border border-rose-500/20 bg-rose-500/10 p-6 text-sm text-rose-100">
          {getErrorMessage(catalogError, 'Story Planner catalog를 불러오지 못했습니다.')}
        </section>
      ) : (
        <div className="space-y-6">
          <StoryPlannerInputPanel
            catalog={catalog ?? null}
            storyPrompt={storyPrompt}
            lane={lane}
            useRegistryCharacters={useRegistryCharacters}
            leadCharacterId={leadCharacterId}
            supportCharacterId={supportCharacterId}
            locationId={locationId}
            preferredAnchorBeat={preferredAnchorBeat}
            supportLockMode={supportLockMode}
            supportFreeformDescription={supportFreeformDescription}
            isPlanning={planMutation.isPending}
            onStoryPromptChange={(value) => {
              clearPlannedResults()
              setStoryPrompt(value)
            }}
            onLaneChange={(value) => {
              clearPlannedResults()
              setLane(value)
            }}
            onUseRegistryCharactersChange={(value) => {
              clearPlannedResults()
              setUseRegistryCharacters(value)
              setSupportLockMode((current) => {
                if (value) {
                  return 'registry'
                }
                if (!value && current === 'registry') {
                  return 'unlocked'
                }
                return current
              })
              if (value) {
                setSupportFreeformDescription('')
              } else {
                setSupportCharacterId('')
              }
            }}
            onLeadCharacterIdChange={(value) => {
              clearPlannedResults()
              setLeadCharacterId(value)
            }}
            onSupportCharacterIdChange={(value) => {
              clearPlannedResults()
              setSupportCharacterId(value)
            }}
            onLocationIdChange={(value) => {
              clearPlannedResults()
              setLocationId(value)
            }}
            onPreferredAnchorBeatChange={(value) => {
              clearPlannedResults()
              setPreferredAnchorBeat(value)
            }}
            onSupportLockModeChange={(value) => {
              clearPlannedResults()
              setSupportLockMode(value)
            }}
            onSupportFreeformDescriptionChange={(value) => {
              clearPlannedResults()
              setSupportFreeformDescription(value)
            }}
            onSubmit={handlePlanSubmit}
          />

          {plannedEpisode ? (
            <StoryPlannerPlanReview
              plan={plannedEpisode}
              isGenerating={generateMutation.isPending}
              onApproveAndGenerate={handleApproveAndGenerate}
            />
          ) : (
            <section className="rounded-3xl border border-dashed border-white/10 bg-gray-950/70 p-6 text-sm leading-6 text-gray-400">
              Plan a story episode to see the resolved cast, location, and four-shot preview here.
            </section>
          )}

          {queuedResult && plannedEpisode ? (
            <StoryPlannerAnchorResults result={queuedResult} plan={plannedEpisode} />
          ) : null}
        </div>
      )}

      <section className="rounded-3xl border border-white/10 bg-gray-950/90 p-6 text-sm text-gray-300">
        <p>
          Story Planner keeps the approval loop separate from the main batch flow so anchor renders only queue after review.
        </p>
        {leadCharacter ? (
          <p className="mt-4 text-xs leading-5 text-gray-500">
            Lead selection: {leadCharacter.name} · {leadCharacter.canonical_anchor}
          </p>
        ) : null}
        {supportLockMode === 'registry' && supportCharacter ? (
          <p className="mt-2 text-xs leading-5 text-gray-500">
            Support selection: {supportCharacter.name} · {supportCharacter.canonical_anchor}
          </p>
        ) : supportLockMode === 'freeform' && supportFreeformDescription.trim() ? (
          <p className="mt-2 text-xs leading-5 text-gray-500">
            Support selection: freeform · {supportFreeformDescription.trim()}
          </p>
        ) : null}
        {location ? (
          <p className="mt-2 text-xs leading-5 text-gray-500">
            Location lock: {location.name} · {location.setting_anchor}
          </p>
        ) : null}
      </section>
    </StoryPlannerShell>
  )
}
