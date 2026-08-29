import type { Artist, ArtistPage, Track } from '../types/api'
import { apiFetch } from './client'

export function listArtists(search?: string): Promise<ArtistPage> {
  const query = search?.trim() ? `?search=${encodeURIComponent(search.trim())}` : ''
  return apiFetch<ArtistPage>(`/artists${query}`)
}

export function getArtist(id: number): Promise<Artist> {
  return apiFetch<Artist>(`/artists/${id}`)
}

export function getArtistTracks(id: number): Promise<Track[]> {
  return apiFetch<Track[]>(`/artists/${id}/tracks`)
}

export function createArtist(name: string): Promise<Artist> {
  return apiFetch<Artist>('/artists', { method: 'POST', body: { name } })
}

export interface ArtistEdit {
  name?: string
  bio?: string | null
  country?: string | null
  begin_year?: number | null
  end_year?: number | null
  wikipedia_url?: string | null
}

export function updateArtist(id: number, payload: ArtistEdit): Promise<Artist> {
  return apiFetch<Artist>(`/artists/${id}`, { method: 'PATCH', body: payload })
}

export function enrichArtist(id: number, force = false): Promise<Artist> {
  return apiFetch<Artist>(`/artists/${id}/enrich${force ? '?force=true' : ''}`, {
    method: 'POST',
  })
}

export function deleteArtist(id: number): Promise<void> {
  return apiFetch<void>(`/artists/${id}`, { method: 'DELETE' })
}
