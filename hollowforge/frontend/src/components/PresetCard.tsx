import type { PresetResponse } from '../api/client'

interface PresetCardProps {
  preset: PresetResponse
  onGenerate: (preset: PresetResponse) => void
  onEdit: (preset: PresetResponse) => void
  onDelete: (preset: PresetResponse) => void
}

export default function PresetCard({ preset, onGenerate, onEdit, onDelete }: PresetCardProps) {
  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 p-6 flex flex-col">
      <div className="flex-1">
        <h3 className="text-lg font-semibold text-gray-100">{preset.name}</h3>
        {preset.description && (
          <p className="text-sm text-gray-400 mt-1 line-clamp-2">{preset.description}</p>
        )}

        <div className="mt-4 space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs bg-violet-600/20 text-violet-400 px-2 py-0.5 rounded">
              {preset.checkpoint}
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span>{preset.loras.length} LoRA{preset.loras.length !== 1 ? 's' : ''}</span>
          </div>
        </div>

        {preset.tags && preset.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-3">
            {preset.tags.map((tag) => (
              <span key={tag} className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-gray-800">
        <button
          onClick={() => onGenerate(preset)}
          className="flex-1 bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-3 py-2 text-sm transition-colors duration-200"
        >
          Generate
        </button>
        <button
          onClick={() => onEdit(preset)}
          className="bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg px-3 py-2 text-sm transition-colors duration-200"
        >
          Edit
        </button>
        <button
          onClick={() => onDelete(preset)}
          className="bg-gray-800 hover:bg-red-600 text-gray-400 hover:text-white rounded-lg px-3 py-2 text-sm transition-colors duration-200"
        >
          Delete
        </button>
      </div>
    </div>
  )
}
