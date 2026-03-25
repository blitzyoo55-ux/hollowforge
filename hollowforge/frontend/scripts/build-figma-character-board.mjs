import { mkdir, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.dirname(fileURLToPath(import.meta.url))
const projectDir = path.resolve(rootDir, '..')
const dataDir = path.resolve(projectDir, '../data')
const dbPath = path.join(dataDir, 'hollowforge.db')
const assetDirName = 'figma-board-assets'
const assetDir = path.join(projectDir, 'public', assetDirName)
const manifestPath = path.join(projectDir, 'public', 'figma-character-board.json')
const pairLimit = 6
const singleLimit = 6

function queryJson(sql) {
  const output = execFileSync('sqlite3', ['-json', dbPath, sql], { encoding: 'utf8' }).trim()
  return output ? JSON.parse(output) : []
}

function toBoardAssetUrl(fileName) {
  return `/${assetDirName}/${fileName}`
}

function formatTimestamp(isoString) {
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'Asia/Seoul',
  }).format(new Date(isoString))
}

function ensureAsset(sourceRelativePath, id, role) {
  const sourcePath = path.join(dataDir, sourceRelativePath)
  const assetFileName = `${id}-${role}.png`
  const assetPath = path.join(assetDir, assetFileName)

  execFileSync('sips', ['-Z', '768', sourcePath, '--out', assetPath], { stdio: 'ignore' })

  return toBoardAssetUrl(assetFileName)
}

const [{ favorites_total: favoritesTotal = 0, upscaled_total: upscaledTotal = 0 } = {}] = queryJson(`
  SELECT
    COUNT(*) AS favorites_total,
    SUM(CASE WHEN upscaled_preview_path IS NOT NULL THEN 1 ELSE 0 END) AS upscaled_total
  FROM generations
  WHERE is_favorite = 1
`)

const pairedRows = queryJson(`
  SELECT
    id,
    COALESCE(favorited_at, created_at) AS ranked_at,
    thumbnail_path,
    upscaled_preview_path
  FROM generations
  WHERE is_favorite = 1
    AND thumbnail_path IS NOT NULL
    AND upscaled_preview_path IS NOT NULL
  ORDER BY COALESCE(favorited_at, created_at) DESC
  LIMIT ${pairLimit}
`)

const soloRows = queryJson(`
  SELECT
    id,
    COALESCE(favorited_at, created_at) AS ranked_at,
    thumbnail_path
  FROM generations
  WHERE is_favorite = 1
    AND thumbnail_path IS NOT NULL
    AND upscaled_preview_path IS NULL
  ORDER BY COALESCE(favorited_at, created_at) DESC
  LIMIT ${singleLimit}
`)

await mkdir(assetDir, { recursive: true })

const pairs = pairedRows.map((row) => ({
  id: row.id,
  label: `Favorite Pair ${row.id.slice(0, 8).toUpperCase()}`,
  original: {
    label: 'Favorite Original',
    imageUrl: ensureAsset(row.thumbnail_path, row.id, 'favorite-original'),
    capturedAt: formatTimestamp(row.ranked_at),
  },
  upscaled: {
    label: 'Favorite Upscaled',
    imageUrl: ensureAsset(row.upscaled_preview_path, row.id, 'favorite-upscaled'),
    capturedAt: formatTimestamp(row.ranked_at),
  },
}))

const latestOriginals = soloRows.map((row) => ({
  id: row.id,
  label: `Favorite ${row.id.slice(0, 8).toUpperCase()}`,
  imageUrl: ensureAsset(row.thumbnail_path, row.id, 'favorite-solo'),
  capturedAt: formatTimestamp(row.ranked_at),
}))

const manifest = {
  title: 'HollowForge Favorite Character Board',
  generatedAt: new Date().toISOString(),
  sourceDir: dataDir,
  totals: {
    favorites: Number(favoritesTotal),
    upscaledFavorites: Number(upscaledTotal),
    pendingUpscaleFavorites: Math.max(0, Number(favoritesTotal) - Number(upscaledTotal)),
  },
  pairs,
  latestOriginals,
}

await mkdir(path.dirname(manifestPath), { recursive: true })
await writeFile(manifestPath, JSON.stringify(manifest, null, 2))

console.log(`Wrote ${manifestPath}`)
console.log(`pairs=${pairs.length} latestOriginals=${latestOriginals.length}`)
