import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { AxiosError } from 'axios'
import {
  createSequenceBlueprint,
  createSequenceRun,
  getSequenceRun,
  listSequenceBlueprints,
  listSequenceRuns,
  startSequenceRun,
  type SequenceBlueprintCreate,
} from '../api/client'
import EmptyState from '../components/EmptyState'
import SequenceBlueprintForm from '../components/SequenceBlueprintForm'
import SequenceRunReview from '../components/SequenceRunReview'
import { notify } from '../lib/toast'

function getErrorMessage(error: unknown, fallback: string): string {
  const detail = (error as AxiosError<{ detail?: string }>)?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  return fallback
}

function formatDate(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

export default function SequenceStudio() {
  const queryClient = useQueryClient()
  const [selectedBlueprintId, setSelectedBlueprintId] = useState<string | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const blueprintsQuery = useQuery({
    queryKey: ['sequence-blueprints'],
    queryFn: () => listSequenceBlueprints(),
    refetchInterval: 30_000,
  })

  const runsQuery = useQuery({
    queryKey: ['sequence-runs'],
    queryFn: () => listSequenceRuns(),
    refetchInterval: (query) => {
      const rows = query.state.data ?? []
      return rows.some((row) => row.run.status === 'planning' || row.run.status === 'animating')
        ? 10_000
        : 30_000
    },
  })

  const effectiveSelectedBlueprintId = useMemo(() => {
    const rows = blueprintsQuery.data ?? []
    if (rows.length === 0) return null
    if (selectedBlueprintId && rows.some((row) => row.blueprint.id === selectedBlueprintId)) {
      return selectedBlueprintId
    }
    return rows[0].blueprint.id
  }, [blueprintsQuery.data, selectedBlueprintId])

  const effectiveSelectedRunId = useMemo(() => {
    const rows = runsQuery.data ?? []
    if (rows.length === 0) return null
    if (selectedRunId && rows.some((row) => row.run.id === selectedRunId)) {
      return selectedRunId
    }
    return rows[0].run.id
  }, [runsQuery.data, selectedRunId])

  const runDetailQuery = useQuery({
    queryKey: ['sequence-run', effectiveSelectedRunId],
    queryFn: () => getSequenceRun(effectiveSelectedRunId as string),
    enabled: Boolean(effectiveSelectedRunId),
    refetchInterval: (query) => {
      const run = query.state.data?.run
      if (!run) return false
      return run.status === 'planning' || run.status === 'animating' ? 10_000 : false
    },
  })

  const createBlueprintMutation = useMutation({
    mutationFn: (payload: SequenceBlueprintCreate) => createSequenceBlueprint(payload),
    onSuccess: async (data) => {
      notify.success('Sequence blueprint created')
      setSelectedBlueprintId(data.blueprint.id)
      await queryClient.invalidateQueries({ queryKey: ['sequence-blueprints'] })
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to create sequence blueprint'))
    },
  })

  const createRunMutation = useMutation({
    mutationFn: (blueprintId: string) => createSequenceRun({ sequence_blueprint_id: blueprintId, candidate_count: 4 }),
    onSuccess: async (data) => {
      notify.success('Sequence run created')
      setSelectedRunId(data.run.id)
      queryClient.setQueryData(['sequence-run', data.run.id], data)
      await queryClient.invalidateQueries({ queryKey: ['sequence-runs'] })
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to create sequence run'))
    },
  })

  const assembleMutation = useMutation({
    mutationFn: (runId: string) => startSequenceRun(runId),
    onSuccess: async (data) => {
      notify.success('Rough-cut assembly requested')
      queryClient.setQueryData(['sequence-run', data.run.id], data)
      await queryClient.invalidateQueries({ queryKey: ['sequence-runs'] })
    },
    onError: (error) => {
      notify.error(getErrorMessage(error, 'Failed to assemble rough cut'))
    },
  })

  const selectedBlueprint = useMemo(
    () => blueprintsQuery.data?.find((row) => row.blueprint.id === effectiveSelectedBlueprintId) ?? null,
    [blueprintsQuery.data, effectiveSelectedBlueprintId],
  )

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-gray-800 bg-gray-900/70 p-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <span className="inline-flex rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs font-medium uppercase tracking-wide text-violet-300">
              Stage 1 Sequence
            </span>
            <div>
              <h1 className="text-2xl font-bold text-gray-100">Animation Track Studio</h1>
              <p className="mt-1 max-w-3xl text-sm text-gray-400">
                Plan sequence blueprints, launch animation-track runs, and review shot-by-shot progress with rough-cut candidates in one place.
              </p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-gray-500">Blueprints</p>
              <p className="mt-1 text-2xl font-semibold text-gray-100">{blueprintsQuery.data?.length ?? 0}</p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-gray-500">Runs</p>
              <p className="mt-1 text-2xl font-semibold text-gray-100">{runsQuery.data?.length ?? 0}</p>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950/70 px-4 py-3">
              <p className="text-[11px] uppercase tracking-wide text-gray-500">Active</p>
              <p className="mt-1 text-2xl font-semibold text-gray-100">
                {runsQuery.data?.filter((row) => row.run.status === 'planning' || row.run.status === 'animating').length ?? 0}
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,460px)_minmax(0,1fr)]">
        <SequenceBlueprintForm
          onSubmit={(payload) => createBlueprintMutation.mutate(payload)}
          isSubmitting={createBlueprintMutation.isPending}
        />

        <section className="space-y-4 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-100">Blueprint Library</h2>
              <p className="text-sm text-gray-400">
                Select a blueprint to inspect its planned shots or launch a new orchestration run.
              </p>
            </div>
          </div>

          {blueprintsQuery.isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
            </div>
          ) : blueprintsQuery.isError ? (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              Failed to load sequence blueprints.
            </div>
          ) : blueprintsQuery.data && blueprintsQuery.data.length > 0 ? (
            <div className="space-y-3">
              {blueprintsQuery.data.map((item) => {
                const isSelected = item.blueprint.id === effectiveSelectedBlueprintId
                return (
                  <article
                    key={item.blueprint.id}
                    className={`w-full rounded-xl border p-4 text-left transition ${
                      isSelected
                        ? 'border-violet-500/40 bg-violet-500/10'
                        : 'border-gray-800 bg-gray-950/60 hover:border-gray-700'
                    }`}
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full border border-gray-700 bg-gray-900 px-2 py-0.5 text-xs text-gray-300">
                            {item.blueprint.content_mode}
                          </span>
                          <span className="text-sm font-semibold text-gray-100">{item.blueprint.executor_policy}</span>
                        </div>
                        <p className="text-sm text-gray-400">
                          {item.blueprint.character_id} in {item.blueprint.location_id}
                        </p>
                        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                          <span>{item.blueprint.target_duration_sec}s target</span>
                          <span>{item.planned_shots.length} planned shots</span>
                          <span>{formatDate(item.blueprint.created_at)}</span>
                        </div>
                        <div className="flex flex-wrap gap-2 pt-1">
                          {item.planned_shots.slice(0, 4).map((shot) => (
                            <span
                              key={`${item.blueprint.id}-${shot.shot_no}`}
                              className="rounded-md border border-gray-800 bg-gray-900 px-2 py-1 text-[11px] text-gray-400"
                            >
                              {shot.shot_no}. {shot.beat_type}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="flex flex-col gap-2 sm:min-w-[140px]">
                        <button
                          type="button"
                          onClick={() => setSelectedBlueprintId(item.blueprint.id)}
                          className="rounded-xl border border-gray-700 bg-gray-900/80 px-4 py-2 text-sm font-medium text-gray-200 transition hover:border-violet-500/40 hover:text-white"
                        >
                          {isSelected ? 'Selected' : 'Inspect'}
                        </button>
                        <button
                          type="button"
                          onClick={() => createRunMutation.mutate(item.blueprint.id)}
                          disabled={createRunMutation.isPending}
                          className="rounded-xl border border-violet-500/40 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-200 transition hover:bg-violet-500/20 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {createRunMutation.isPending && selectedBlueprint?.blueprint.id === item.blueprint.id
                            ? 'Launching...'
                            : 'Launch Run'}
                        </button>
                      </div>
                    </div>
                  </article>
                )
              })}
            </div>
          ) : (
            <EmptyState
              title="No sequence blueprints yet"
              description="Create a Stage 1 blueprint to seed shots and start the first orchestration run."
            />
          )}
        </section>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(300px,360px)_minmax(0,1fr)]">
        <section className="space-y-4 rounded-2xl border border-gray-800 bg-gray-900/70 p-5">
          <div>
            <h2 className="text-lg font-semibold text-gray-100">Run List</h2>
            <p className="text-sm text-gray-400">
              Monitor blueprint executions and open a run for per-shot review.
            </p>
          </div>

          {runsQuery.isLoading ? (
            <div className="flex items-center justify-center py-10">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-violet-400 border-t-transparent" />
            </div>
          ) : runsQuery.isError ? (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
              Failed to load sequence runs.
            </div>
          ) : runsQuery.data && runsQuery.data.length > 0 ? (
            <div className="space-y-3">
              {runsQuery.data.map((item) => {
                const isSelected = item.run.id === effectiveSelectedRunId
                return (
                  <button
                    key={item.run.id}
                    type="button"
                    onClick={() => setSelectedRunId(item.run.id)}
                    className={`w-full rounded-xl border p-4 text-left transition ${
                      isSelected
                        ? 'border-violet-500/40 bg-violet-500/10'
                        : 'border-gray-800 bg-gray-950/60 hover:border-gray-700'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-gray-100">{item.run.id}</p>
                        <p className="mt-1 text-xs text-gray-500">{formatDate(item.run.created_at)}</p>
                      </div>
                      <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-xs font-medium text-violet-300">
                        {item.run.status}
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-3 text-sm text-gray-400">
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-gray-500">Shots</p>
                        <p className="mt-1 font-medium text-gray-100">{item.shot_count}</p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-wide text-gray-500">Rough Cuts</p>
                        <p className="mt-1 font-medium text-gray-100">{item.rough_cut_candidate_count}</p>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          ) : (
            <EmptyState
              title="No runs yet"
              description="Launch a run from the blueprint library to start Stage 1 orchestration."
            />
          )}
        </section>

        <SequenceRunReview
          runDetail={runDetailQuery.data ?? null}
          isLoading={runDetailQuery.isLoading}
          isError={runDetailQuery.isError}
          isAssembling={assembleMutation.isPending}
          onAssembleRoughCut={() => {
            if (!effectiveSelectedRunId) return
            assembleMutation.mutate(effectiveSelectedRunId)
          }}
        />
      </div>
    </div>
  )
}
