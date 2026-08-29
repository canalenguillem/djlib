import type { SearchResults, Track, TrackFilters, TrackPage } from '../types/api'
import { apiFetch, apiFetchBlob } from './client'

export function listTracks(filters: TrackFilters = {}): Promise<TrackPage> {
  const params = new URLSearchParams()
  if (filters.search?.trim()) params.set('search', filters.search.trim())
  if (filters.status) params.set('status', filters.status)
  for (const id of filters.tagIds ?? []) params.append('tag_id', String(id))
  const query = params.toString()
  return apiFetch<TrackPage>(`/tracks${query ? `?${query}` : ''}`)
}

export function addFromUrl(url: string): Promise<Track> {
  return apiFetch<Track>('/tracks/from-url', { method: 'POST', body: { url } })
}

export function previewSearch(
  title: string | null,
  artist: string | null,
): Promise<SearchResults> {
  return apiFetch<SearchResults>('/tracks/search/preview', {
    method: 'POST',
    body: { title, artist },
  })
}

export function addFromSearch(title: string | null, artist: string | null): Promise<Track> {
  return apiFetch<Track>('/tracks/search', { method: 'POST', body: { title, artist } })
}

export function updateTrack(
  id: number,
  payload: { title?: string; artist_text?: string | null },
): Promise<Track> {
  return apiFetch<Track>(`/tracks/${id}`, { method: 'PATCH', body: payload })
}

export function setTrackTags(id: number, tagIds: number[]): Promise<Track> {
  return apiFetch<Track>(`/tracks/${id}/tags`, { method: 'PUT', body: { tag_ids: tagIds } })
}

export function retryTrack(id: number): Promise<Track> {
  return apiFetch<Track>(`/tracks/${id}/retry`, { method: 'POST' })
}

export function deleteTrack(id: number): Promise<void> {
  return apiFetch<void>(`/tracks/${id}`, { method: 'DELETE' })
}

export function fetchTrackFile(id: number): Promise<Blob> {
  return apiFetchBlob(`/tracks/${id}/file`)
}
