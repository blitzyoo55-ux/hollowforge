import { Suspense, lazy, useState } from 'react'
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import GlobalGenerationIndicator from './components/GlobalGenerationIndicator'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Generate = lazy(() => import('./pages/Generate'))
const PromptFactory = lazy(() => import('./pages/PromptFactory'))
const Gallery = lazy(() => import('./pages/Gallery'))
const ImageDetail = lazy(() => import('./pages/ImageDetail'))
const Collections = lazy(() => import('./pages/Collections'))
const Presets = lazy(() => import('./pages/Presets'))
const Timeline = lazy(() => import('./pages/Timeline'))
const Benchmark = lazy(() => import('./pages/Benchmark'))
const LoraGuide = lazy(() => import('./pages/LoraGuide'))
const LoraManager = lazy(() => import('./pages/LoraManager'))
const MoodManager = lazy(() => import('./pages/MoodManager'))
const Settings = lazy(() => import('./pages/Settings'))
const Scheduler = lazy(() => import('./pages/Scheduler'))
const SeedanceStudio = lazy(() => import('./pages/SeedanceStudio'))
const QueuePage = lazy(() => import('./pages/QueuePage'))
const BatchImportPage = lazy(() => import('./pages/BatchImportPage'))
const CurationPage = lazy(() => import('./pages/CurationPage'))
const DirectionBoard = lazy(() => import('./pages/DirectionBoard'))
const Marketing = lazy(() => import('./pages/Marketing'))
const Favorites = lazy(() => import('./pages/Favorites'))
const ReadyToGo = lazy(() => import('./pages/ReadyToGo'))
const QualityPage = lazy(() => import('./pages/QualityPage'))
const FigmaCharacterBoard = lazy(() => import('./pages/FigmaCharacterBoard'))

const LEAN_MODE = import.meta.env.VITE_HF_LEAN_MODE === '1'

interface NavItem {
  to: string
  label: string
  icon: string
  leanHidden?: boolean
}

interface NavGroup {
  label: string
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    label: 'HOME',
    items: [
      { to: '/', label: 'Dashboard', icon: 'grid' },
      { to: '/gallery', label: 'Gallery', icon: 'image' },
      { to: '/batch-import', label: 'Batch Import', icon: 'upload' },
    ],
  },
  {
    label: 'CREATE',
    items: [
      { to: '/generate', label: 'Generate', icon: 'sparkles' },
      { to: '/prompt-factory', label: 'Prompt Factory', icon: 'wand-sparkles' },
      { to: '/presets', label: 'Presets', icon: 'bookmark' },
      { to: '/scheduler', label: 'Scheduler', icon: 'clock', leanHidden: true },
    ],
  },
  {
    label: 'LIBRARY',
    items: [
      { to: '/favorites', label: 'Favorites', icon: 'heart' },
      { to: '/ready', label: 'Ready to Go', icon: 'check-square' },
      { to: '/quality', label: 'Quality AI', icon: 'shield' },
      { to: '/collections', label: 'Collections', icon: 'folder' },
      { to: '/curation', label: 'Curation', icon: 'check-square', leanHidden: true },
    ],
  },
  {
    label: 'TOOLS',
    items: [
      { to: '/lora-guide', label: 'LoRA Guide', icon: 'book' },
      { to: '/direction', label: 'Direction Board', icon: 'compass', leanHidden: true },
      { to: '/seedance', label: 'Seedance', icon: 'video-sparkles' },
      { to: '/marketing', label: 'Caption AI', icon: 'wand-sparkles', leanHidden: true },
      { to: '/timeline', label: 'Timeline', icon: 'timeline', leanHidden: true },
      { to: '/settings', label: 'Settings', icon: 'cog' },
    ],
  },
]

const advancedItems: NavItem[] = [
  { to: '/benchmark', label: 'Benchmark', icon: 'layers', leanHidden: true },
  { to: '/lora-manager', label: 'LoRA Manager', icon: 'cpu', leanHidden: true },
  { to: '/mood-manager', label: 'Mood Manager', icon: 'tag', leanHidden: true },
  { to: '/queue', label: 'Queue', icon: 'queue' },
] 

function NavIcon({ icon }: { icon: string }) {
  switch (icon) {
    case 'grid':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
        </svg>
      )
    case 'sparkles':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" />
        </svg>
      )
    case 'wand-sparkles':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 19.5L19.5 4.5m-6.75 3.75l3-3m-2.25 8.25l1.5-1.5" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 2.25l.375 1.125c.113.34.381.608.721.721L18 4.5l-1.154.404a1.125 1.125 0 00-.721.721L15.75 6.75l-.375-1.125a1.125 1.125 0 00-.721-.721L13.5 4.5l1.154-.404c.34-.113.608-.381.721-.721L15.75 2.25zM20.25 8.25l.274.824c.082.245.275.438.52.52l.824.274-.824.274a.813.813 0 00-.52.52l-.274.824-.274-.824a.813.813 0 00-.52-.52l-.824-.274.824-.274a.813.813 0 00.52-.52l.274-.824zM8.25 14.25l.43 1.289c.129.386.432.689.818.818l1.289.43-1.289.43a1.277 1.277 0 00-.818.818l-.43 1.289-.43-1.289a1.277 1.277 0 00-.818-.818l-1.289-.43 1.289-.43c.386-.129.689-.432.818-.818l.43-1.289z" />
        </svg>
      )
    case 'image':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z" />
        </svg>
      )
    case 'heart':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0 5.227-9 11.25-9 11.25S3 13.477 3 8.25A5.25 5.25 0 018.25 3c1.902 0 3.55.99 4.5 2.486A5.246 5.246 0 0117.25 3A5.25 5.25 0 0122.5 8.25z" />
        </svg>
      )
    case 'video-sparkles':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 10.5l4.5-2.25v7.5l-4.5-2.25m-9 2.25h7.5A2.25 2.25 0 0016.5 13.5v-3A2.25 2.25 0 0014.25 8.25h-7.5A2.25 2.25 0 004.5 10.5v3a2.25 2.25 0 002.25 2.25z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 5.25l.375 1.125a1.5 1.5 0 00.95.95L8.25 7.5l-.925.175a1.5 1.5 0 00-.95.95L6 9.75l-.375-1.125a1.5 1.5 0 00-.95-.95L3.75 7.5l.925-.175a1.5 1.5 0 00.95-.95L6 5.25z" />
        </svg>
      )
    case 'timeline':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 19.5h16.5M6.75 16.5v-3m4.5 3v-7.5m4.5 7.5v-5.25m4.5 5.25v-10.5" />
        </svg>
      )
    case 'layers':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5l8.25 4.125L12 12.75 3.75 8.625 12 4.5z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12l8.25 4.125L20.25 12" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 15.375L12 19.5l8.25-4.125" />
        </svg>
      )
    case 'folder':
      return <span className="text-base leading-none">📁</span>
    case 'bookmark':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
        </svg>
      )
    case 'cog':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      )
    case 'clock':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2m5-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    case 'book':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.483 9.246 5 7.5 5A4.5 4.5 0 003 9.5v9A4.5 4.5 0 017.5 14c1.746 0 3.332.483 4.5 1.253m0-9C13.168 5.483 14.754 5 16.5 5A4.5 4.5 0 0121 9.5v9a4.5 4.5 0 00-4.5-4.5c-1.746 0-3.332.483-4.5 1.253" />
        </svg>
      )
    case 'cpu':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2m3 4h2m-2 6h2m-4 6v-2m-6 2v-2m-7-4h2m-2-6h2m3-4h6a2 2 0 012 2v6a2 2 0 01-2 2H9a2 2 0 01-2-2V9a2 2 0 012-2z" />
        </svg>
      )
    case 'tag':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.568 3.114a2.25 2.25 0 011.59-.659h5.842A2.25 2.25 0 0119.25 4.705v5.842a2.25 2.25 0 01-.659 1.59l-6.78 6.78a2.25 2.25 0 01-3.182 0L3.083 13.37a2.25 2.25 0 010-3.182l6.485-6.485z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 8.25h.008v.008h-.008V8.25z" />
        </svg>
      )
    case 'queue':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
        </svg>
      )
    case 'upload':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      )
    case 'check-square':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      )
    case 'compass':
      return (
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
        </svg>
      )
    case 'shield':
      return (
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
      )
    default:
      return null
  }
}

function RouteFallback() {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 px-6 py-8 text-sm text-gray-400">
      화면을 불러오는 중입니다...
    </div>
  )
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const visibleNavGroups = navGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => !LEAN_MODE || !item.leanHidden),
    }))
    .filter((group) => group.items.length > 0)
  const visibleAdvancedItems = advancedItems.filter((item) => !LEAN_MODE || !item.leanHidden)

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Mobile top bar */}
      <header className="md:hidden sticky top-0 z-20 bg-gray-900/95 backdrop-blur border-b border-gray-800 px-4 py-3 flex items-center justify-between">
        <NavLink to="/" className="text-lg font-bold text-violet-400 tracking-tight hover:text-violet-300 transition-colors">HollowForge</NavLink>
        <button
          type="button"
          onClick={() => setSidebarOpen((v) => !v)}
          className="p-2 rounded-lg border border-gray-700 text-gray-300 hover:bg-gray-800"
          aria-label="Toggle navigation"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      </header>

      {/* Sidebar */}
      <aside className={`fixed top-0 left-0 h-full w-60 bg-gray-900 border-r border-gray-800 flex flex-col z-30 transform transition-transform duration-200 md:translate-x-0 ${
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      }`}>
        <div className="px-6 py-5 border-b border-gray-800">
          <NavLink to="/" onClick={() => setSidebarOpen(false)} className="block">
            <h1 className="text-xl font-bold text-violet-400 tracking-tight hover:text-violet-300 transition-colors">HollowForge</h1>
            <p className="text-xs text-gray-500 mt-0.5">ComfyUI Generation Manager</p>
          </NavLink>
        </div>
        <nav className="flex-1 px-3 py-4 overflow-y-auto space-y-4">
          {visibleNavGroups.map((group) => (
            <div key={group.label}>
              <p className="px-3 mb-1 text-[10px] font-semibold tracking-widest text-gray-600 uppercase">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.to === '/'}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 ${
                        isActive
                          ? 'bg-violet-600/20 text-violet-400'
                          : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800/60'
                      }`
                    }
                    onClick={() => setSidebarOpen(false)}
                  >
                    <NavIcon icon={item.icon} />
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}

          {visibleAdvancedItems.length > 0 && (
          <div>
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              className="w-full flex items-center justify-between px-3 mb-1 text-[10px] font-semibold tracking-widest text-gray-600 uppercase hover:text-gray-400 transition-colors"
            >
              <span>ADVANCED</span>
              <svg
                className={`w-3 h-3 transition-transform duration-200 ${advancedOpen ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {advancedOpen && (
              <div className="space-y-0.5">
                {visibleAdvancedItems.map((item) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-150 ${
                        isActive
                          ? 'bg-violet-600/20 text-violet-400'
                          : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800/60'
                      }`
                    }
                    onClick={() => setSidebarOpen(false)}
                  >
                    <NavIcon icon={item.icon} />
                    {item.label}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
          )}
        </nav>
        <div className="px-6 py-4 border-t border-gray-800 space-y-3">
          <GlobalGenerationIndicator />
          <div className="text-xs text-gray-600">v0.1.0</div>
        </div>
      </aside>

      {/* Mobile drawer backdrop */}
      {sidebarOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
          className="md:hidden fixed inset-0 z-20 bg-black/40"
        />
      )}

      {/* Main content */}
      <main className="md:ml-60 overflow-y-auto">
        <div className="max-w-7xl mx-auto px-4 md:px-6 py-6 md:py-8">
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/generate" element={<Generate />} />
              <Route path="/prompt-factory" element={<PromptFactory />} />
              <Route path="/gallery" element={<Gallery />} />
              <Route path="/gallery/:id" element={<ImageDetail />} />
              <Route path="/favorites" element={<Favorites />} />
              <Route path="/ready" element={<ReadyToGo />} />
              <Route path="/collections" element={<Collections />} />
              <Route path="/collections/:id" element={<Collections />} />
              <Route path="/presets" element={<Presets />} />
              <Route path="/lora-guide" element={<LoraGuide />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/seedance" element={<SeedanceStudio />} />
              <Route path="/quality" element={<QualityPage />} />
              <Route path="/figma-character-board" element={<FigmaCharacterBoard />} />
              {!LEAN_MODE && <Route path="/marketing" element={<Marketing />} />}
              {!LEAN_MODE && <Route path="/timeline" element={<Timeline />} />}
              {!LEAN_MODE && <Route path="/benchmark" element={<Benchmark />} />}
              <Route path="/queue" element={<QueuePage />} />
              <Route path="/batch-import" element={<BatchImportPage />} />
              {!LEAN_MODE && <Route path="/scheduler" element={<Scheduler />} />}
              {!LEAN_MODE && <Route path="/lora-manager" element={<LoraManager />} />}
              {!LEAN_MODE && <Route path="/mood-manager" element={<MoodManager />} />}
              {!LEAN_MODE && <Route path="/curation" element={<CurationPage />} />}
              {!LEAN_MODE && <Route path="/direction" element={<DirectionBoard />} />}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </div>
      </main>
    </div>
  )
}
