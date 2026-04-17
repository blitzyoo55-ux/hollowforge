import type { ProductionEpisodeDetailResponse } from '../api/client'

export function buildProductionTrackHref(
  track: 'comic' | 'animation',
  episode: ProductionEpisodeDetailResponse,
): string {
  const linkedCount = track === 'comic'
    ? episode.comic_track_count
    : episode.animation_track_count
  const mode = linkedCount === 0 ? 'create_from_production' : 'open_current'

  const params = new URLSearchParams()
  params.set('production_episode_id', episode.id)
  params.set('mode', mode)

  if (track === 'comic') return `/comic?${params.toString()}`
  return `/sequences?${params.toString()}`
}
