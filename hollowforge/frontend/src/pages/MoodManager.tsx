import { useMemo, useState, type FormEvent } from 'react'
import axios from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  createMood,
  deleteMood,
  getLoras,
  listMoods,
  updateMood,
  type MoodMapping,
  type MoodMappingCreate,
  type MoodMappingUpdate,
} from '../api/client'
import EmptyState from '../components/EmptyState'

interface MoodFormState {
  mood_keyword: string
  lora_ids: string[]
  prompt_additions: string
}

const DEFAULT_FORM: MoodFormState = {
  mood_keyword: '',
  lora_ids: [],
  prompt_additions: '',
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }
  return fallback
}

function formatDateTime(value: string): string {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

export default function MoodManager() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingMood, setEditingMood] = useState<MoodMapping | null>(null)
  const [form, setForm] = useState<MoodFormState>(DEFAULT_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [busyDeleteId, setBusyDeleteId] = useState<string | null>(null)

  const { data: moods, isLoading, isError } = useQuery({
    queryKey: ['moods'],
    queryFn: listMoods,
  })

  const { data: loras } = useQuery({
    queryKey: ['loras'],
    queryFn: () => getLoras(),
  })

  const loraNameById = useMemo(
    () => new Map((loras ?? []).map((lora) => [lora.id, lora.display_name])),
    [loras],
  )

  const createMutation = useMutation({
    mutationFn: (data: MoodMappingCreate) => createMood(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['moods'] })
      toast.success('Mood mapping created')
      closeModal()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to create mood mapping'))
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: MoodMappingUpdate }) => updateMood(id, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['moods'] })
      toast.success('Mood mapping updated')
      closeModal()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to update mood mapping'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteMood(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['moods'] })
      toast.success('Mood mapping deleted')
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to delete mood mapping'))
    },
    onSettled: () => {
      setBusyDeleteId(null)
    },
  })

  const openCreateModal = () => {
    setEditingMood(null)
    setForm(DEFAULT_FORM)
    setFormError(null)
    setShowForm(true)
  }

  const openEditModal = (mood: MoodMapping) => {
    setEditingMood(mood)
    setForm({
      mood_keyword: mood.mood_keyword,
      lora_ids: mood.lora_ids,
      prompt_additions: mood.prompt_additions,
    })
    setFormError(null)
    setShowForm(true)
  }

  const closeModal = () => {
    setShowForm(false)
    setEditingMood(null)
    setForm(DEFAULT_FORM)
    setFormError(null)
  }

  const toggleLora = (loraId: string) => {
    setForm((prev) => {
      const has = prev.lora_ids.includes(loraId)
      return {
        ...prev,
        lora_ids: has ? prev.lora_ids.filter((id) => id !== loraId) : [...prev.lora_ids, loraId],
      }
    })
  }

  const handleDelete = (mood: MoodMapping) => {
    if (!window.confirm(`Delete mood mapping "${mood.mood_keyword}"?`)) {
      return
    }
    setBusyDeleteId(mood.id)
    deleteMutation.mutate(mood.id)
  }

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const moodKeyword = form.mood_keyword.trim()
    if (!moodKeyword) {
      setFormError('Mood keyword is required')
      return
    }

    setFormError(null)
    if (editingMood) {
      const payload: MoodMappingUpdate = {
        mood_keyword: moodKeyword,
        lora_ids: form.lora_ids,
        prompt_additions: form.prompt_additions.trim(),
      }
      updateMutation.mutate({ id: editingMood.id, data: payload })
      return
    }

    const payload: MoodMappingCreate = {
      mood_keyword: moodKeyword,
      lora_ids: form.lora_ids,
      prompt_additions: form.prompt_additions.trim(),
    }
    createMutation.mutate(payload)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Mood Manager</h2>
          <p className="text-sm text-gray-400 mt-1">Map mood keywords to LoRA combinations and prompt additions</p>
        </div>
        <button
          onClick={openCreateModal}
          className="bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Add Mood
        </button>
      </div>

      <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
        {isLoading ? (
          <div className="p-6 text-sm text-gray-400">Loading mood mappings...</div>
        ) : isError ? (
          <div className="p-6 text-sm text-red-400">Failed to load mood mappings</div>
        ) : !moods || moods.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="Mood 매핑이 없습니다"
              description={'"Add Mood"로 첫 매핑을 생성하세요.'}
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-950/70 border-b border-gray-800 text-gray-400">
                <tr>
                  <th className="text-left px-4 py-3 font-medium">Keyword</th>
                  <th className="text-left px-4 py-3 font-medium">LoRAs</th>
                  <th className="text-left px-4 py-3 font-medium">Prompt Additions</th>
                  <th className="text-left px-4 py-3 font-medium">Created</th>
                  <th className="text-left px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(moods ?? []).map((mood) => (
                  <tr key={mood.id} className="border-b border-gray-800/60 last:border-b-0">
                    <td className="px-4 py-3 text-gray-200 font-medium">{mood.mood_keyword}</td>
                    <td className="px-4 py-3 text-gray-300">
                      {mood.lora_ids.length > 0 ? (
                        <div className="flex flex-wrap gap-1.5">
                          {mood.lora_ids.map((loraId) => (
                            <span
                              key={`${mood.id}-${loraId}`}
                              className="inline-flex items-center rounded-full px-2 py-0.5 text-xs bg-violet-600/20 border border-violet-500/40 text-violet-200"
                            >
                              {loraNameById.get(loraId) ?? loraId}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-gray-500">None</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-300">
                      {mood.prompt_additions ? (
                        <span className="line-clamp-2">{mood.prompt_additions}</span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-400">{formatDateTime(mood.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => openEditModal(mood)}
                          className="bg-blue-600/80 hover:bg-blue-500 text-white rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors duration-200"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(mood)}
                          disabled={busyDeleteId === mood.id}
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
          <div className="w-full max-w-2xl bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-100">
                {editingMood ? 'Edit Mood Mapping' : 'Add Mood Mapping'}
              </h3>
              <button
                onClick={closeModal}
                className="text-gray-500 hover:text-gray-300 transition-colors duration-200"
                aria-label="Close modal"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Mood Keyword</label>
                <input
                  type="text"
                  required
                  maxLength={60}
                  value={form.mood_keyword}
                  onChange={(e) => setForm((prev) => ({ ...prev, mood_keyword: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">LoRA Profiles</label>
                <div className="max-h-48 overflow-y-auto rounded-lg border border-gray-800 bg-gray-950 p-3 space-y-2">
                  {(loras ?? []).length > 0 ? (
                    (loras ?? []).map((lora) => (
                      <label key={lora.id} className="flex items-center gap-2 text-sm text-gray-300">
                        <input
                          type="checkbox"
                          checked={form.lora_ids.includes(lora.id)}
                          onChange={() => toggleLora(lora.id)}
                          className="accent-violet-500"
                        />
                        <span className="text-gray-200">{lora.display_name}</span>
                        <span className="text-xs text-gray-500 font-mono break-all">{lora.filename}</span>
                      </label>
                    ))
                  ) : (
                    <p className="text-xs text-gray-500">No LoRA profiles found</p>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Prompt Additions</label>
                <textarea
                  rows={4}
                  value={form.prompt_additions}
                  onChange={(e) => setForm((prev) => ({ ...prev, prompt_additions: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none resize-y"
                />
              </div>

              {formError && (
                <div className="rounded-lg p-2.5 text-sm bg-red-900/20 border border-red-800/50 text-red-400">
                  {formError}
                </div>
              )}

              <div className="flex gap-3 pt-1">
                <button
                  type="button"
                  onClick={closeModal}
                  className="bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm transition-colors duration-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
                >
                  {editingMood ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
