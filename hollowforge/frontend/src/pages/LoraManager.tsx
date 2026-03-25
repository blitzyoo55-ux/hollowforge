import { useMemo, useState, type FormEvent } from 'react'
import axios from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  createLora,
  deleteLora,
  getLoras,
  getModels,
  updateLora,
  type LoraProfile,
  type LoraProfileCreate,
  type LoraProfileUpdate,
} from '../api/client'
import EmptyState from '../components/EmptyState'

type LoraCategory = 'style' | 'eyes' | 'material' | 'fetish'

interface LoraFormState {
  display_name: string
  filename: string
  category: LoraCategory
  default_strength: number
  tags: string
  notes: string
  compatible_checkpoints: string[]
}

const CATEGORY_ORDER: LoraCategory[] = ['style', 'eyes', 'material', 'fetish']
const CATEGORY_LABELS: Record<LoraCategory, string> = {
  style: 'Style',
  eyes: 'Eyes',
  material: 'Material',
  fetish: 'Fetish',
}

const DEFAULT_FORM: LoraFormState = {
  display_name: '',
  filename: '',
  category: 'style',
  default_strength: 0.7,
  tags: '',
  notes: '',
  compatible_checkpoints: [],
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

export default function LoraManager() {
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingLora, setEditingLora] = useState<LoraProfile | null>(null)
  const [form, setForm] = useState<LoraFormState>(DEFAULT_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [busyDeleteId, setBusyDeleteId] = useState<string | null>(null)

  const { data: loras, isLoading, isError } = useQuery({
    queryKey: ['loras'],
    queryFn: () => getLoras(),
  })

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: getModels,
  })

  const groupedLoras = useMemo(() => {
    const byCategory: Record<LoraCategory, LoraProfile[]> = {
      style: [],
      eyes: [],
      material: [],
      fetish: [],
    }
    for (const lora of loras ?? []) {
      const category = CATEGORY_ORDER.includes(lora.category as LoraCategory)
        ? (lora.category as LoraCategory)
        : 'style'
      byCategory[category].push(lora)
    }
    for (const category of CATEGORY_ORDER) {
      byCategory[category].sort((a, b) => a.display_name.localeCompare(b.display_name))
    }
    return byCategory
  }, [loras])

  const createMutation = useMutation({
    mutationFn: (data: LoraProfileCreate) => createLora(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['loras'] })
      await queryClient.invalidateQueries({ queryKey: ['lora-guide'] })
      toast.success('LoRA profile created')
      closeModal()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to create LoRA profile'))
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: LoraProfileUpdate }) => updateLora(id, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['loras'] })
      await queryClient.invalidateQueries({ queryKey: ['lora-guide'] })
      await queryClient.invalidateQueries({ queryKey: ['moods'] })
      toast.success('LoRA profile updated')
      closeModal()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to update LoRA profile'))
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteLora(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['loras'] })
      await queryClient.invalidateQueries({ queryKey: ['lora-guide'] })
      await queryClient.invalidateQueries({ queryKey: ['moods'] })
      toast.success('LoRA profile deleted')
    },
    onError: (error) => {
      toast.error(getErrorMessage(error, 'Failed to delete LoRA profile'))
    },
    onSettled: () => {
      setBusyDeleteId(null)
    },
  })

  const openCreateModal = () => {
    setEditingLora(null)
    setForm({
      ...DEFAULT_FORM,
      filename: models?.lora_files?.[0] ?? '',
      compatible_checkpoints: [],
    })
    setFormError(null)
    setShowForm(true)
  }

  const openEditModal = (lora: LoraProfile) => {
    setEditingLora(lora)
    setForm({
      display_name: lora.display_name,
      filename: lora.filename,
      category: (CATEGORY_ORDER.includes(lora.category as LoraCategory)
        ? lora.category
        : 'style') as LoraCategory,
      default_strength: lora.default_strength,
      tags: lora.tags ?? '',
      notes: lora.notes ?? '',
      compatible_checkpoints: lora.compatible_checkpoints ?? [],
    })
    setFormError(null)
    setShowForm(true)
  }

  const closeModal = () => {
    setShowForm(false)
    setEditingLora(null)
    setForm(DEFAULT_FORM)
    setFormError(null)
  }

  const toggleCheckpoint = (checkpoint: string) => {
    setForm((prev) => {
      const has = prev.compatible_checkpoints.includes(checkpoint)
      return {
        ...prev,
        compatible_checkpoints: has
          ? prev.compatible_checkpoints.filter((item) => item !== checkpoint)
          : [...prev.compatible_checkpoints, checkpoint],
      }
    })
  }

  const handleDelete = (lora: LoraProfile) => {
    if (!window.confirm(`Delete LoRA profile "${lora.display_name}"?`)) {
      return
    }
    setBusyDeleteId(lora.id)
    deleteMutation.mutate(lora.id)
  }

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const displayName = form.display_name.trim()
    const filename = form.filename.trim()

    if (!displayName) {
      setFormError('Display name is required')
      return
    }
    if (!filename) {
      setFormError('Filename is required')
      return
    }
    if (form.default_strength < -2.0 || form.default_strength > 2.0) {
      setFormError('Default strength must be between -2.0 and 2.0')
      return
    }

    setFormError(null)
    if (editingLora) {
      const payload: LoraProfileUpdate = {
        display_name: displayName,
        category: form.category,
        default_strength: Number(form.default_strength.toFixed(2)),
        tags: form.tags.trim() || null,
        notes: form.notes.trim() || null,
        compatible_checkpoints:
          form.compatible_checkpoints.length > 0
            ? form.compatible_checkpoints
            : null,
      }
      updateMutation.mutate({ id: editingLora.id, data: payload })
      return
    }

    const payload: LoraProfileCreate = {
      display_name: displayName,
      filename,
      category: form.category,
      default_strength: Number(form.default_strength.toFixed(2)),
      tags: form.tags.trim() || null,
      notes: form.notes.trim() || null,
      compatible_checkpoints:
        form.compatible_checkpoints.length > 0
          ? form.compatible_checkpoints
          : null,
    }
    createMutation.mutate(payload)
  }

  const availableFiles = models?.lora_files ?? []
  const availableCheckpoints = models?.checkpoints ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">LoRA Manager</h2>
          <p className="text-sm text-gray-400 mt-1">Create and maintain LoRA profiles by category</p>
        </div>
        <button
          onClick={openCreateModal}
          className="bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Add LoRA
        </button>
      </div>

      {isLoading ? (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 text-sm text-gray-400">
          Loading LoRA profiles...
        </div>
      ) : isError ? (
        <div className="bg-gray-900 rounded-xl border border-red-800/50 p-6 text-sm text-red-400">
          Failed to load LoRA profiles
        </div>
      ) : !loras || loras.length === 0 ? (
        <EmptyState
          title="LoRA 프로필이 없습니다"
          description={'"Add LoRA"로 첫 프로필을 생성하세요.'}
        />
      ) : (
        <div className="space-y-4">
          {CATEGORY_ORDER.map((category) => {
            const items = groupedLoras[category]
            if (items.length === 0) return null

            return (
              <section key={category} className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-violet-300">
                    {CATEGORY_LABELS[category]}
                  </h3>
                  <span className="text-xs text-gray-500">{items.length} item(s)</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-950/70 border-b border-gray-800 text-gray-400">
                      <tr>
                        <th className="text-left px-4 py-3 font-medium">Display Name</th>
                        <th className="text-left px-4 py-3 font-medium">Filename</th>
                        <th className="text-left px-4 py-3 font-medium">Strength</th>
                        <th className="text-left px-4 py-3 font-medium">Checkpoints</th>
                        <th className="text-left px-4 py-3 font-medium">Notes</th>
                        <th className="text-left px-4 py-3 font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((lora) => (
                        <tr key={lora.id} className="border-b border-gray-800/60 last:border-b-0">
                          <td className="px-4 py-3 text-gray-200 font-medium">{lora.display_name}</td>
                          <td className="px-4 py-3 text-gray-300 font-mono break-all">{lora.filename}</td>
                          <td className="px-4 py-3 text-gray-300 font-mono">{lora.default_strength.toFixed(2)}</td>
                          <td className="px-4 py-3 text-gray-400">
                            {lora.compatible_checkpoints?.length
                              ? `${lora.compatible_checkpoints.length} selected`
                              : 'All'}
                          </td>
                          <td className="px-4 py-3 text-gray-400">
                            {lora.notes ? (
                              <span className="line-clamp-2">{lora.notes}</span>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => openEditModal(lora)}
                                className="bg-blue-600/80 hover:bg-blue-500 text-white rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors duration-200"
                              >
                                Edit
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDelete(lora)}
                                disabled={busyDeleteId === lora.id}
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
              </section>
            )
          })}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-gray-900 rounded-xl border border-gray-800 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-100">
                {editingLora ? 'Edit LoRA Profile' : 'Add LoRA Profile'}
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
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Display Name</label>
                  <input
                    type="text"
                    required
                    maxLength={120}
                    value={form.display_name}
                    onChange={(e) => setForm((prev) => ({ ...prev, display_name: e.target.value }))}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-1.5">Category</label>
                  <select
                    value={form.category}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, category: e.target.value as LoraCategory }))
                    }
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                  >
                    {CATEGORY_ORDER.map((category) => (
                      <option key={category} value={category}>
                        {CATEGORY_LABELS[category]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Filename</label>
                <select
                  value={form.filename}
                  onChange={(e) => setForm((prev) => ({ ...prev, filename: e.target.value }))}
                  disabled={Boolean(editingLora)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none disabled:opacity-60"
                >
                  {!editingLora && <option value="">-- Select LoRA file --</option>}
                  {editingLora && !availableFiles.includes(form.filename) && (
                    <option value={form.filename}>{form.filename} (current, unavailable)</option>
                  )}
                  {availableFiles.map((file) => (
                    <option key={file} value={file}>
                      {file}
                    </option>
                  ))}
                </select>
                {!editingLora && availableFiles.length === 0 && (
                  <p className="mt-1 text-xs text-amber-300">
                    No LoRA files discovered. Sync models from Settings first.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">
                  Default Strength
                  <span className="ml-2 text-violet-300 font-mono">{form.default_strength.toFixed(2)}</span>
                </label>
                <div className="grid grid-cols-[1fr_120px] gap-3">
                  <input
                    type="range"
                    min={-2}
                    max={2}
                    step={0.05}
                    value={form.default_strength}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, default_strength: Number(e.target.value) }))
                    }
                    className="accent-violet-500"
                  />
                  <input
                    type="number"
                    min={-2}
                    max={2}
                    step={0.05}
                    value={form.default_strength}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, default_strength: Number(e.target.value) }))
                    }
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Notes</label>
                <textarea
                  rows={3}
                  value={form.notes}
                  onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none resize-y"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Tags</label>
                <input
                  type="text"
                  value={form.tags}
                  onChange={(e) => setForm((prev) => ({ ...prev, tags: e.target.value }))}
                  placeholder="optional tags"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Compatible Checkpoints</label>
                <div className="max-h-40 overflow-y-auto rounded-lg border border-gray-800 bg-gray-950 p-3 space-y-2">
                  {availableCheckpoints.length > 0 ? (
                    availableCheckpoints.map((checkpoint) => {
                      const checked = form.compatible_checkpoints.includes(checkpoint)
                      return (
                        <label key={checkpoint} className="flex items-center gap-2 text-sm text-gray-300">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleCheckpoint(checkpoint)}
                            className="accent-violet-500"
                          />
                          <span className="break-all font-mono text-xs">{checkpoint}</span>
                        </label>
                      )
                    })
                  ) : (
                    <p className="text-xs text-gray-500">No checkpoints found</p>
                  )}
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Empty selection means this LoRA is considered compatible with all checkpoints.
                </p>
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
                  {editingLora ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
