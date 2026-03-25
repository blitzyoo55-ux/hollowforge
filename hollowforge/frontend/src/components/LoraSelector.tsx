import { useQuery } from '@tanstack/react-query'
import { getLoras, selectLoras } from '../api/client'
import type { LoraInput } from '../api/client'

interface LoraSelectorProps {
  selected: LoraInput[]
  onChange: (loras: LoraInput[]) => void
  moods: string[]
  checkpoint: string
}

const CATEGORY_COLORS: Record<string, string> = {
  style: 'bg-blue-600/20 text-blue-400',
  eyes: 'bg-green-600/20 text-green-400',
  material: 'bg-amber-600/20 text-amber-400',
  fetish: 'bg-pink-600/20 text-pink-400',
}

const MAX_TOTAL_STRENGTH = 2.4

export default function LoraSelector({ selected, onChange, moods, checkpoint }: LoraSelectorProps) {
  const { data: allLoras, isLoading } = useQuery({
    queryKey: ['loras'],
    queryFn: getLoras,
  })

  const totalStrength = selected.reduce((sum, l) => sum + l.strength, 0)
  const strengthPercent = Math.min((totalStrength / MAX_TOTAL_STRENGTH) * 100, 100)
  const isOverLimit = totalStrength > MAX_TOTAL_STRENGTH

  const toggleLora = (filename: string, defaultStrength: number, category: string) => {
    const exists = selected.find((l) => l.filename === filename)
    if (exists) {
      onChange(selected.filter((l) => l.filename !== filename))
    } else {
      onChange([...selected, { filename, strength: defaultStrength, category }])
    }
  }

  const updateStrength = (filename: string, strength: number) => {
    onChange(selected.map((l) => (l.filename === filename ? { ...l, strength } : l)))
  }

  const handleAutoSelect = async () => {
    if (moods.length === 0) return
    try {
      const result = await selectLoras({ moods, checkpoint: checkpoint || undefined })
      onChange(result.loras)
    } catch {
      // Mood selection failed silently
    }
  }

  const grouped = (allLoras ?? []).reduce<Record<string, typeof allLoras>>((acc, lora) => {
    const cat = lora.category || 'other'
    if (!acc[cat]) acc[cat] = []
    acc[cat]!.push(lora)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-gray-300">LoRAs</label>
        {moods.length > 0 && (
          <button
            type="button"
            onClick={handleAutoSelect}
            className="text-xs text-violet-400 hover:text-violet-300 transition-colors duration-200"
          >
            Auto-select from moods
          </button>
        )}
      </div>

      {/* Strength indicator bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-gray-500">Total strength</span>
          <span className={isOverLimit ? 'text-red-400' : 'text-gray-400'}>
            {totalStrength.toFixed(2)} / {MAX_TOTAL_STRENGTH}
          </span>
        </div>
        <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              isOverLimit ? 'bg-red-500' : 'bg-violet-500'
            }`}
            style={{ width: `${strengthPercent}%` }}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="text-sm text-gray-500 py-4">Loading LoRAs...</div>
      ) : !allLoras || allLoras.length === 0 ? (
        <div className="text-sm text-gray-500 py-4">No LoRAs available</div>
      ) : (
        <div className="space-y-4 max-h-80 overflow-y-auto pr-1">
          {Object.entries(grouped).map(([category, loras]) => (
            <div key={category}>
              <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                {category}
              </h4>
              <div className="space-y-2">
                {loras!.map((lora) => {
                  const isSelected = selected.some((l) => l.filename === lora.filename)
                  const selectedLora = selected.find((l) => l.filename === lora.filename)
                  return (
                    <div
                      key={lora.id}
                      className={`flex items-center gap-3 p-2 rounded-lg border transition-colors duration-200 ${
                        isSelected
                          ? 'border-violet-500/50 bg-violet-600/10'
                          : 'border-gray-800 bg-gray-800/50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleLora(lora.filename, lora.default_strength, lora.category)}
                        className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-violet-500 focus:ring-violet-500 focus:ring-offset-0"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-gray-200 truncate">{lora.display_name}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded ${CATEGORY_COLORS[lora.category] ?? 'bg-gray-700 text-gray-400'}`}>
                            {lora.category}
                          </span>
                        </div>
                      </div>
                      {isSelected && selectedLora && (
                        <input
                          type="range"
                          min={0}
                          max={1}
                          step={0.05}
                          value={selectedLora.strength}
                          onChange={(e) => updateStrength(lora.filename, parseFloat(e.target.value))}
                          className="w-20 accent-violet-500"
                        />
                      )}
                      {isSelected && selectedLora && (
                        <span className="text-xs text-gray-400 font-mono w-10 text-right">
                          {selectedLora.strength.toFixed(2)}
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
