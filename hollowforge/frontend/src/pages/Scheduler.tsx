import { useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createSchedulerJob,
  deleteSchedulerJob,
  getPresets,
  getSchedulerJobs,
  runSchedulerJobNow,
  updateSchedulerJob,
  type ScheduledJobCreate,
  type ScheduledJobResponse,
} from '../api/client'
import EmptyState from '../components/EmptyState'

interface JobFormState {
  name: string
  preset_id: string
  count: number
  time: string
}

const DEFAULT_FORM: JobFormState = {
  name: '',
  preset_id: '',
  count: 4,
  time: '02:00',
}

function formatDateTime(value: string | null): string {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

function formatClock(hour: number, minute: number): string {
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

function statusToneClass(status: string | null): string {
  if (!status) return 'text-gray-400'
  if (status.startsWith('success')) return 'text-green-400'
  if (status.startsWith('error')) return 'text-red-400'
  return 'text-gray-300'
}

export default function Scheduler() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<JobFormState>(DEFAULT_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null)
  const [busyJobId, setBusyJobId] = useState<string | null>(null)

  const { data: jobs, isLoading, isError } = useQuery({
    queryKey: ['scheduler-jobs'],
    queryFn: getSchedulerJobs,
    refetchInterval: 30_000,
  })

  const { data: presets } = useQuery({
    queryKey: ['presets'],
    queryFn: getPresets,
  })

  const presetNameById = useMemo(
    () => new Map((presets ?? []).map((preset) => [preset.id, preset.name])),
    [presets],
  )

  const createMutation = useMutation({
    mutationFn: (data: ScheduledJobCreate) => createSchedulerJob(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['scheduler-jobs'] })
      setNotice({ ok: true, text: 'Scheduled job created' })
      setShowForm(false)
      setForm({
        ...DEFAULT_FORM,
        preset_id: presets?.[0]?.id ?? '',
      })
      setFormError(null)
    },
    onError: () => {
      setFormError('Failed to create scheduled job')
    },
  })

  const openCreateModal = () => {
    setNotice(null)
    setFormError(null)
    setForm({
      ...DEFAULT_FORM,
      preset_id: presets?.[0]?.id ?? '',
    })
    setShowForm(true)
  }

  const closeCreateModal = () => {
    setShowForm(false)
    setFormError(null)
  }

  const handleCreate = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const [hourRaw, minuteRaw] = form.time.split(':')
    const hour = Number(hourRaw)
    const minute = Number(minuteRaw)

    if (!form.name.trim()) {
      setFormError('Name is required')
      return
    }
    if (!form.preset_id) {
      setFormError('Preset selection is required')
      return
    }
    if (
      !Number.isInteger(hour) ||
      !Number.isInteger(minute) ||
      hour < 0 ||
      hour > 23 ||
      minute < 0 ||
      minute > 59
    ) {
      setFormError('Time must be in HH:MM format')
      return
    }

    createMutation.mutate({
      name: form.name.trim(),
      preset_id: form.preset_id,
      count: form.count,
      cron_hour: hour,
      cron_minute: minute,
      enabled: true,
    })
  }

  const handleToggleEnabled = (job: ScheduledJobResponse) => {
    setBusyJobId(job.id)
    setNotice(null)
    updateSchedulerJob(job.id, { enabled: !job.enabled })
      .then(async () => {
        await queryClient.invalidateQueries({ queryKey: ['scheduler-jobs'] })
      })
      .catch(() => {
        setNotice({ ok: false, text: 'Failed to update enabled state' })
      })
      .finally(() => {
        setBusyJobId(null)
      })
  }

  const handleDelete = (job: ScheduledJobResponse) => {
    if (!window.confirm(`Delete scheduled job "${job.name}"?`)) {
      return
    }
    setBusyJobId(job.id)
    setNotice(null)
    deleteSchedulerJob(job.id)
      .then(async () => {
        await queryClient.invalidateQueries({ queryKey: ['scheduler-jobs'] })
        setNotice({ ok: true, text: 'Scheduled job deleted' })
      })
      .catch(() => {
        setNotice({ ok: false, text: 'Failed to delete scheduled job' })
      })
      .finally(() => {
        setBusyJobId(null)
      })
  }

  const handleRunNow = (job: ScheduledJobResponse) => {
    setBusyJobId(job.id)
    setNotice(null)
    runSchedulerJobNow(job.id)
      .then(async (result) => {
        await queryClient.invalidateQueries({ queryKey: ['scheduler-jobs'] })
        setNotice({
          ok: result.success,
          text: result.status || (result.success ? 'Run queued' : 'Run failed'),
        })
      })
      .catch(() => {
        setNotice({ ok: false, text: 'Failed to trigger run-now' })
      })
      .finally(() => {
        setBusyJobId(null)
      })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Scheduler</h2>
          <p className="text-sm text-gray-400 mt-1">Nightly preset batch automation</p>
        </div>
        <button
          onClick={openCreateModal}
          disabled={!presets || presets.length === 0}
          className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Add Job
        </button>
      </div>

      {notice && (
        <div
          className={`rounded-lg p-3 text-sm ${
            notice.ok
              ? 'bg-green-900/20 border border-green-800/50 text-green-400'
              : 'bg-red-900/20 border border-red-800/50 text-red-400'
          }`}
        >
          {notice.text}
        </div>
      )}

      {(!presets || presets.length === 0) && (
        <div className="bg-amber-900/20 border border-amber-800/50 rounded-xl p-4 text-sm text-amber-300">
          No presets found. Create at least one preset before adding scheduler jobs.
        </div>
      )}

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        {isLoading ? (
          <div className="p-6 text-sm text-gray-400">Loading scheduler jobs...</div>
        ) : isError ? (
          <div className="p-6 text-sm text-red-400">Failed to load scheduler jobs</div>
        ) : !jobs || jobs.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="예약된 작업이 없습니다"
              description={'"Add Job"으로 첫 예약 작업을 추가하세요.'}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-950/70 border-b border-gray-800 text-gray-400">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Name</th>
                  <th className="text-left px-4 py-3 font-medium">Preset</th>
                  <th className="text-left px-4 py-3 font-medium">Count</th>
                  <th className="text-left px-4 py-3 font-medium">Time</th>
                  <th className="text-left px-4 py-3 font-medium">Next Run</th>
                  <th className="text-left px-4 py-3 font-medium">Last Run</th>
                  <th className="text-left px-4 py-3 font-medium">Status</th>
                  <th className="text-left px-4 py-3 font-medium">Enabled</th>
                  <th className="text-left px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} className="border-b border-gray-800/60 last:border-b-0">
                    <td className="px-4 py-3 text-gray-200 font-medium">{job.name}</td>
                    <td className="px-4 py-3 text-gray-300">{presetNameById.get(job.preset_id) ?? job.preset_id}</td>
                    <td className="px-4 py-3 text-gray-300">{job.count}</td>
                    <td className="px-4 py-3 text-gray-300 font-mono">{formatClock(job.cron_hour, job.cron_minute)}</td>
                    <td className="px-4 py-3 text-gray-400">{formatDateTime(job.next_run_at)}</td>
                    <td className="px-4 py-3 text-gray-400">{formatDateTime(job.last_run_at)}</td>
                    <td className={`px-4 py-3 ${statusToneClass(job.last_run_status)}`}>
                      {job.last_run_status ?? '-'}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => handleToggleEnabled(job)}
                        disabled={busyJobId === job.id}
                        className={`inline-flex h-6 w-11 rounded-full border transition-colors duration-200 ${
                          job.enabled
                            ? 'bg-green-600/40 border-green-500/70'
                            : 'bg-gray-700 border-gray-600'
                        } ${busyJobId === job.id ? 'opacity-50 cursor-not-allowed' : ''}`}
                        aria-label={`Toggle ${job.name}`}
                      >
                        <span
                          className={`mt-1 h-4 w-4 rounded-full bg-white transition-transform duration-200 ${
                            job.enabled ? 'translate-x-5' : 'translate-x-1'
                          }`}
                        />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleRunNow(job)}
                          disabled={busyJobId === job.id}
                          className="bg-blue-600/80 hover:bg-blue-500 disabled:opacity-50 text-white rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors duration-200"
                        >
                          Run Now
                        </button>
                        <button
                          onClick={() => handleDelete(job)}
                          disabled={busyJobId === job.id}
                          className="bg-red-600/80 hover:bg-red-500 disabled:opacity-50 text-white rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors duration-200"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showForm && (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-100">Add Scheduled Job</h3>
              <button
                onClick={closeCreateModal}
                className="text-gray-500 hover:text-gray-300 transition-colors duration-200"
                aria-label="Close modal"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Name</label>
                <input
                  type="text"
                  required
                  maxLength={120}
                  value={form.name}
                  onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Preset</label>
                <select
                  required
                  value={form.preset_id}
                  onChange={(e) => setForm((prev) => ({ ...prev, preset_id: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                >
                  <option value="">-- Select preset --</option>
                  {(presets ?? []).map((preset) => (
                    <option key={preset.id} value={preset.id}>
                      {preset.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Count</label>
                  <input
                    type="number"
                    min={1}
                    max={24}
                    value={form.count}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        count: Math.max(1, Math.min(24, Number(e.target.value) || 1)),
                      }))
                    }
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Run Time (HH:MM)</label>
                  <input
                    type="time"
                    value={form.time}
                    step={60}
                    onChange={(e) => setForm((prev) => ({ ...prev, time: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                  />
                </div>
              </div>

              {formError && (
                <div className="rounded-lg p-2.5 text-sm bg-red-900/20 border border-red-800/50 text-red-400">
                  {formError}
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={closeCreateModal}
                  className="bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm transition-colors duration-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
                >
                  {createMutation.isPending ? 'Creating...' : 'Create Job'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
