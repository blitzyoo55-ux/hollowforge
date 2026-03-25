import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getSystemHealth, getComfyUIStatus, getGallery } from '../api/client'
import GalleryGrid from '../components/GalleryGrid'
import { useNavigate } from 'react-router-dom'

export default function Dashboard() {
  const navigate = useNavigate()

  const { data: health, isLoading: healthLoading, isError: healthError } = useQuery({
    queryKey: ['system-health'],
    queryFn: getSystemHealth,
    refetchInterval: 30_000,
  })

  const { data: comfyStatus } = useQuery({
    queryKey: ['comfyui-status'],
    queryFn: getComfyUIStatus,
    refetchInterval: 10_000,
  })

  const { data: recentGallery, isLoading: galleryLoading } = useQuery({
    queryKey: ['gallery-recent'],
    queryFn: () => getGallery({ page: 1, per_page: 20, sort_order: 'desc' }),
  })

  const connected = comfyStatus?.connected ?? false

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-100">Dashboard</h2>
          <p className="text-sm text-gray-400 mt-1">Overview of your generation pipeline</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-gray-900 rounded-lg border border-gray-800 px-3 py-2">
            <div className={`w-2.5 h-2.5 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-300">
              ComfyUI {connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <Link
            to="/generate"
            className="bg-violet-600 hover:bg-violet-500 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors duration-200"
          >
            Quick Generate
          </Link>
        </div>
      </div>

      {/* Stats row */}
      {healthLoading ? (
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-900 rounded-xl border border-gray-800 p-6 animate-pulse">
              <div className="h-4 bg-gray-800 rounded w-24 mb-3" />
              <div className="h-8 bg-gray-800 rounded w-16" />
            </div>
          ))}
        </div>
      ) : healthError ? (
        <div className="bg-gray-900 rounded-xl border border-red-800/50 p-6 text-center">
          <p className="text-red-400 text-sm">Unable to connect to backend. Is the server running?</p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <p className="text-sm text-gray-400">Total Generations</p>
            <p className="text-3xl font-bold text-gray-100 mt-1">{health?.total_generations ?? 0}</p>
          </div>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <p className="text-sm text-gray-400">Database</p>
            <p className="text-3xl font-bold text-gray-100 mt-1">
              {health?.db_ok ? (
                <span className="text-green-400">OK</span>
              ) : (
                <span className="text-red-400">Error</span>
              )}
            </p>
          </div>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-6">
            <p className="text-sm text-gray-400">System Status</p>
            <p className="text-3xl font-bold text-gray-100 mt-1 capitalize">{health?.status ?? 'unknown'}</p>
          </div>
        </div>
      )}

      {/* Recent generations */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-100">Recent Generations</h3>
          <Link to="/gallery" className="text-sm text-violet-400 hover:text-violet-300 transition-colors duration-200">
            View all
          </Link>
        </div>

        {galleryLoading ? (
          <div className="grid grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] bg-gray-900 rounded-xl border border-gray-800 animate-pulse" />
            ))}
          </div>
        ) : (
          <GalleryGrid
            items={recentGallery?.items ?? []}
            onItemClick={(item) => navigate(`/gallery/${item.id}`)}
            onRegenerateClick={(item) => navigate(`/generate?from=${item.id}`)}
          />
        )}
      </div>
    </div>
  )
}
