import { useEffect, useState } from 'react'

interface ManifestImage {
  label: string
  imageUrl: string
  capturedAt: string
}

interface PairCard {
  id: string
  label: string
  original: ManifestImage
  upscaled: ManifestImage
}

interface SingleCard {
  id: string
  label: string
  imageUrl: string
  capturedAt: string
}

interface BoardManifest {
  title: string
  generatedAt: string
  sourceDir: string
  totals: {
    favorites: number
    upscaledFavorites: number
    pendingUpscaleFavorites: number
  }
  pairs: PairCard[]
  latestOriginals: SingleCard[]
}

function StatCard({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
      <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${tone}`}>{label}</p>
      <p className="mt-3 text-3xl font-semibold text-white">{value}</p>
    </div>
  )
}

function BoardImage({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/40 shadow-[0_20px_60px_rgba(0,0,0,0.35)]">
      <img src={src} alt={alt} className="h-full w-full object-cover" />
    </div>
  )
}

export default function FigmaCharacterBoard() {
  const [manifest, setManifest] = useState<BoardManifest | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function loadManifest() {
      try {
        setError(null)
        const response = await fetch('/figma-character-board.json', { cache: 'no-store' })
        if (!response.ok) {
          throw new Error(`manifest ${response.status}`)
        }

        const data = (await response.json()) as BoardManifest
        if (!cancelled) {
          setManifest(data)
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'unknown error')
        }
      }
    }

    loadManifest()

    return () => {
      cancelled = true
    }
  }, [])

  if (error) {
    return (
      <div className="rounded-3xl border border-red-500/30 bg-red-500/10 p-6 text-red-200">
        <h2 className="text-xl font-semibold">Character board manifest load failed</h2>
        <p className="mt-2 text-sm text-red-100/80">{error}</p>
        <p className="mt-4 text-xs text-red-100/60">Run `npm run build:figma-board` and reload this page.</p>
      </div>
    )
  }

  if (!manifest) {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/5 p-12 text-center text-sm text-gray-300">
        Character board를 불러오는 중입니다...
      </div>
    )
  }

  return (
    <div className="space-y-8 pb-24">
      <section className="overflow-hidden rounded-[32px] border border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(124,58,237,0.28),_transparent_36%),radial-gradient(circle_at_top_right,_rgba(16,185,129,0.16),_transparent_28%),linear-gradient(180deg,_rgba(17,24,39,0.98),_rgba(3,7,18,0.98))] px-6 py-8 md:px-8 md:py-10">
        <div className="max-w-4xl space-y-4">
          <p className="text-xs font-semibold uppercase tracking-[0.32em] text-violet-300">Figma Capture Board</p>
          <h1 className="text-3xl font-semibold tracking-tight text-white md:text-5xl">{manifest.title}</h1>
          <p className="max-w-3xl text-sm leading-6 text-gray-300 md:text-base">
            즐겨찾기된 캐릭터만 대상으로, 업스케일 완료본과 대기 중인 후보를 분리한 전용 보드입니다. 카드 이름,
            섹션 구분, 배지 라벨을 고정해서 Figma 안에서도 favorite 묶음이 읽히도록 구성했습니다.
          </p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-4">
          <StatCard label="Favorites" value={manifest.totals.favorites.toLocaleString()} tone="text-rose-300" />
          <StatCard
            label="Upscaled Favorites"
            value={manifest.totals.upscaledFavorites.toLocaleString()}
            tone="text-sky-300"
          />
          <StatCard
            label="Pending Upscale"
            value={manifest.totals.pendingUpscaleFavorites.toLocaleString()}
            tone="text-amber-300"
          />
          <StatCard
            label="Board Updated"
            value={new Date(manifest.generatedAt).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
            tone="text-violet-300"
          />
        </div>
      </section>

      <section className="rounded-[28px] border border-white/10 bg-gray-900/80 p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-emerald-300">Section A</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Upscaled Favorite Sets</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-400">
              favorite 중에서도 업스케일까지 완료된 캐릭터만 모았습니다. 각 카드는 원본 favorite와 업스케일
              결과를 한 쌍으로 보여주기 때문에, 최종 후보를 리뷰하거나 정리하기에 적합합니다.
            </p>
          </div>
          <div className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-xs font-medium text-emerald-200">
            Pair cards: {manifest.pairs.length}
          </div>
        </div>

        <div className="mt-6 grid gap-5 xl:grid-cols-2">
          {manifest.pairs.map((pair, index) => (
            <article key={pair.id} className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
              <header className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-violet-300">Favorite Pair {String(index + 1).padStart(2, '0')}</p>
                  <h3 className="mt-2 text-xl font-semibold text-white">{pair.label}</h3>
                  <p className="mt-1 text-xs text-gray-500">Layer group: favorite/pair/{pair.id}</p>
                </div>
                <div className="rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs text-gray-300">
                  id {pair.id.slice(0, 8)}
                </div>
              </header>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <figure className="space-y-3">
                  <figcaption className="flex items-center justify-between text-xs uppercase tracking-[0.24em] text-amber-200">
                    <span>{pair.original.label}</span>
                    <span className="text-gray-500 normal-case tracking-normal">{pair.original.capturedAt}</span>
                  </figcaption>
                  <BoardImage src={pair.original.imageUrl} alt={`${pair.label} original`} />
                </figure>

                <figure className="space-y-3">
                  <figcaption className="flex items-center justify-between text-xs uppercase tracking-[0.24em] text-sky-200">
                    <span>{pair.upscaled.label}</span>
                    <span className="text-gray-500 normal-case tracking-normal">{pair.upscaled.capturedAt}</span>
                  </figcaption>
                  <BoardImage src={pair.upscaled.imageUrl} alt={`${pair.label} upscaled`} />
                </figure>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-[28px] border border-white/10 bg-gray-900/80 p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-amber-300">Section B</p>
            <h2 className="mt-2 text-2xl font-semibold text-white">Favorite Queue Candidates</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-400">
              아직 업스케일이 없는 favorite만 따로 묶었습니다. 지금 당장 추가 업스케일을 걸거나, 다음 검토
              라운드 후보를 선별하기 좋은 큐 섹션입니다.
            </p>
          </div>
          <div className="rounded-full border border-amber-400/20 bg-amber-400/10 px-4 py-2 text-xs font-medium text-amber-200">
            Solo cards: {manifest.latestOriginals.length}
          </div>
        </div>

        <div className="mt-6 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {manifest.latestOriginals.map((item, index) => (
            <article key={item.id} className="rounded-[28px] border border-white/10 bg-white/[0.03] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
              <header className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-300">Favorite Queue {String(index + 1).padStart(2, '0')}</p>
                  <h3 className="mt-2 text-lg font-semibold text-white">{item.label}</h3>
                  <p className="mt-1 text-xs text-gray-500">Layer group: favorite/queue/{item.id}</p>
                </div>
                <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1 text-xs text-gray-300">
                  {item.capturedAt}
                </span>
              </header>

              <div className="mt-5">
                <BoardImage src={item.imageUrl} alt={item.label} />
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
