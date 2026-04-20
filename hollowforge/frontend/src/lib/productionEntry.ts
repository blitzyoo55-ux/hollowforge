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
  params.set('work_id', episode.work_id)
  if (episode.series_id) params.set('series_id', episode.series_id)
  params.set('content_mode', episode.content_mode)
  params.set('title', episode.title)

  if (track === 'comic' && episode.comic_track?.id) {
    params.set('comic_episode_id', episode.comic_track.id)
  }
  if (track === 'animation' && episode.animation_track?.id) {
    params.set('sequence_blueprint_id', episode.animation_track.id)
  }

  if (track === 'comic') return `/comic?${params.toString()}`
  return `/sequences?${params.toString()}`
}
