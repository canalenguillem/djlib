import type { PlayedTrack, ShazamTracks, SpotifyStatus } from '../types/api'
import { apiFetch } from './client'

export function getSpotifyStatus(): Promise<SpotifyStatus> {
  return apiFetch<SpotifyStatus>('/spotify/status')
}

/** Devuelve la URL de Spotify a la que hay que mandar al usuario. */
export function startAuthorization(): Promise<{ url: string }> {
  return apiFetch<{ url: string }>('/spotify/authorize', { method: 'POST' })
}

export function disconnectSpotify(): Promise<void> {
  return apiFetch<void>('/spotify/connection', { method: 'DELETE' })
}

/** Lo que Shazam guarda en la playlist "My Shazam Tracks" de Spotify. */
export function shazamTracks(): Promise<ShazamTracks> {
  return apiFetch<ShazamTracks>('/spotify/shazam')
}

export function recentlyPlayed(): Promise<{ items: PlayedTrack[] }> {
  return apiFetch<{ items: PlayedTrack[] }>('/spotify/recently-played')
}
