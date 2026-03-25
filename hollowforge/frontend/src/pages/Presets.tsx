import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getPresets, createPreset, updatePreset, deletePreset, getModels } from '../api/client'
import type { PresetResponse, PresetCreate, LoraInput } from '../api/client'
import EmptyState from '../components/EmptyState'
import PresetCard from '../components/PresetCard'
import { DEFAULT_NEGATIVE_PROMPT } from '../lib/defaultPrompts'

interface PresetFormData {
  name: string
  description: string
  checkpoint: string
  prompt_template: string
  negative_prompt: string
  tags: string
}

export default function Presets() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showForm, setShowForm] = useState(false)
  const [editingPreset, setEditingPreset] = useState<PresetResponse | null>(null)
  const [formData, setFormData] = useState<PresetFormData>({
    name: '',
    description: '',
    checkpoint: '',
    prompt_template: '',
    negative_prompt: DEFAULT_NEGATIVE_PROMPT,
    tags: '',
  })

  const { data: presets, isLoading, isError } = useQuery({
    queryKey: ['presets'],
    queryFn: getPresets,
  })

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: getModels,
  })

  const createMutation = useMutation({
    mutationFn: (data: PresetCreate) => createPreset(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['presets'] })
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: PresetCreate }) => updatePreset(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['presets'] })
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deletePreset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['presets'] })
    },
  })

  const resetForm = () => {
    setShowForm(false)
    setEditingPreset(null)
    setFormData({
      name: '',
      description: '',
      checkpoint: '',
      prompt_template: '',
      negative_prompt: DEFAULT_NEGATIVE_PROMPT,
      tags: '',
    })
  }

  const handleEdit = (preset: PresetResponse) => {
    setEditingPreset(preset)
    setFormData({
      name: preset.name,
      description: preset.description ?? '',
      checkpoint: preset.checkpoint,
      prompt_template: preset.prompt_template ?? '',
      negative_prompt: preset.negative_prompt ?? '',
      tags: preset.tags?.join(', ') ?? '',
    })
    setShowForm(true)
  }

  const handleDelete = (preset: PresetResponse) => {
    if (window.confirm(`Delete preset "${preset.name}"?`)) {
      deleteMutation.mutate(preset.id)
    }
  }

  const handleGenerate = (preset: PresetResponse) => {
    navigate(`/generate?preset=${preset.id}`)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data: PresetCreate = {
      name: formData.name,
      description: formData.description || undefined,
      checkpoint: formData.checkpoint,
      loras: editingPreset?.loras ?? ([] as LoraInput[]),
      prompt_template: formData.prompt_template || undefined,
      negative_prompt: formData.negative_prompt || undefined,
      tags: formData.tags ? formData.tags.split(',').map((t) => t.trim()).filter(Boolean) : undefined,
    }

    if (editingPreset) {
      updateMutation.mutate({ id: editingPreset.id, data })
    } else {
      createMutation.mutate(data)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Presets</h2>
          <p className="text-sm text-gray-400 mt-1">Manage your generation presets</p>
        </div>
        <button
          onClick={() => { resetForm(); setShowForm(true) }}
          className="bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
        >
          Create New Preset
        </button>
      </div>

      {/* Preset form modal */}
      {showForm && (
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-100">
              {editingPreset ? 'Edit Preset' : 'New Preset'}
            </h3>
            <button
              onClick={resetForm}
              className="text-gray-500 hover:text-gray-300 transition-colors duration-200"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Name</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1.5">Checkpoint</label>
                <select
                  required
                  value={formData.checkpoint}
                  onChange={(e) => setFormData({ ...formData, checkpoint: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                >
                  <option value="">-- Select checkpoint --</option>
                  {models?.checkpoints.map((cp) => (
                    <option key={cp} value={cp}>{cp}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Description</label>
              <input
                type="text"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Prompt Template</label>
              <textarea
                value={formData.prompt_template}
                onChange={(e) => setFormData({ ...formData, prompt_template: e.target.value })}
                rows={4}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none resize-y"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Negative Prompt</label>
              <textarea
                value={formData.negative_prompt}
                onChange={(e) => setFormData({ ...formData, negative_prompt: e.target.value })}
                rows={2}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm font-mono focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none resize-y"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">Tags</label>
              <input
                type="text"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg text-gray-100 px-3 py-2 text-sm focus:border-violet-500 focus:ring-1 focus:ring-violet-500 focus:outline-none"
                placeholder="tag1, tag2, tag3"
              />
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={resetForm}
                className="bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-4 py-2 text-sm transition-colors duration-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createMutation.isPending || updateMutation.isPending}
                className="bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
              >
                {editingPreset ? 'Update' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Presets grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-900 rounded-xl border border-gray-800 p-6 h-48 animate-pulse" />
          ))}
        </div>
      ) : isError ? (
        <div className="bg-gray-900 rounded-xl border border-red-800/50 p-8 text-center">
          <p className="text-red-400">Failed to load presets</p>
        </div>
      ) : !presets || presets.length === 0 ? (
        <EmptyState
          title="프리셋이 없습니다"
          description="첫 프리셋을 만들어 생성 설정을 재사용해보세요."
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {presets.map((preset) => (
            <PresetCard
              key={preset.id}
              preset={preset}
              onGenerate={handleGenerate}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  )
}
