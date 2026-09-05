import type { SearchResults, Track, TrackFilters, TrackPage } from '../types/api'
import { apiFetch, apiFetchBlob, apiFetchForm } from './client'

export function listTracks(filters: TrackFilters = {}): Promise<TrackPage> {
  const params = new URLSearchParams()
  if (filters.search?.trim()) params.set('search', filters.search.trim())
  if (filters.status) params.set('status', filters.status)
  for (const id of filters.tagIds ?? []) params.append('tag_id', String(id))
  if (filters.energyMin) params.set('energy_min', String(filters.energyMin))
  if (filters.bpmMin) params.set('bpm_min', String(filters.bpmMin))
  if (filters.bpmMax) params.set('bpm_max', String(filters.bpmMax))
  if (filters.sort && filters.sort !== 'recent') params.set('sort', filters.sort)
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

/** Sube un fichero propio: una compra, una descarga de un record pool. */
export function uploadTrack(
  file: File,
  title?: string,
  artist?: string,
): Promise<Track> {
  const form = new FormData()
  form.append('audio', file, file.name)
  if (title?.trim()) form.append('title', title.trim())
  if (artist?.trim()) form.append('artist', artist.trim())
  return apiFetchForm<Track>('/tracks/upload', form)
}

export function updateTrack(
  id: number,
  payload: { title?: string; artist_text?: string | null; energy?: number; bpm?: number },
): Promise<Track> {
  return apiFetch<Track>(`/tracks/${id}`, { method: 'PATCH', body: payload })
}

export function setTrackTags(id: number, tagIds: number[]): Promise<Track> {
  return apiFetch<Track>(`/tracks/${id}/tags`, { method: 'PUT', body: { tag_ids: tagIds } })
}

/** Vuelve a medir el tempo, pisando el que hubiera. */
export function analyzeTrack(id: number): Promise<Track> {
  return apiFetch<Track>(`/tracks/${id}/analyze`, { method: 'POST' })
}

export function retryTrack(id: number): Promise<Track> {
  return apiFetch<Track>(`/tracks/${id}/retry`, { method: 'POST' })
}

export function deleteTrack(id: number): Promise<void> {
  return apiFetch<void>(`/tracks/${id}`, { method: 'DELETE' })
}

/** Fragmento de 30 s de un candidato, para saber si es la version buena. */
export function previewCandidate(url: string): Promise<Blob> {
  return apiFetchBlob(`/tracks/preview?url=${encodeURIComponent(url)}`)
}

export function fetchTrackFile(id: number): Promise<Blob> {
  return apiFetchBlob(`/tracks/${id}/file`)
}
