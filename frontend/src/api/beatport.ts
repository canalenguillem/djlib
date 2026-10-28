import type { BeatportGenre, BeatportTop } from '../types/api'
import { apiFetch } from './client'

export function listGenres(): Promise<BeatportGenre[]> {
  return apiFetch<BeatportGenre[]>('/beatport/genres')
}

/** Sin genero, el top 100 general. */
export function top100(genre: number | null): Promise<BeatportTop> {
  return apiFetch<BeatportTop>(`/beatport/top-100${genre ? `?genre=${genre}` : ''}`)
}
