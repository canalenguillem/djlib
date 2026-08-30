import type { Crate, CrateSummary } from '../types/api'
import { apiFetch } from './client'

export function listCrates(): Promise<CrateSummary[]> {
  return apiFetch<CrateSummary[]>('/crates')
}

export function getCrate(id: number): Promise<Crate> {
  return apiFetch<Crate>(`/crates/${id}`)
}

export function createCrate(
  name: string,
  trackIds: number[] = [],
  description?: string | null,
): Promise<Crate> {
  return apiFetch<Crate>('/crates', {
    method: 'POST',
    body: { name, track_ids: trackIds, description: description ?? null },
  })
}

export function updateCrate(
  id: number,
  payload: { name?: string; description?: string | null },
): Promise<Crate> {
  return apiFetch<Crate>(`/crates/${id}`, { method: 'PATCH', body: payload })
}

export function deleteCrate(id: number): Promise<void> {
  return apiFetch<void>(`/crates/${id}`, { method: 'DELETE' })
}

export function addTrackToCrate(id: number, trackId: number): Promise<Crate> {
  return apiFetch<Crate>(`/crates/${id}/tracks`, { method: 'POST', body: { track_id: trackId } })
}

export function removeTrackFromCrate(id: number, trackId: number): Promise<Crate> {
  return apiFetch<Crate>(`/crates/${id}/tracks/${trackId}`, { method: 'DELETE' })
}

/** Se manda la lista completa en su nuevo orden, no el movimiento suelto:
 *  asi el servidor no puede quedarse con un orden a medias. */
export function reorderCrate(id: number, trackIds: number[]): Promise<Crate> {
  return apiFetch<Crate>(`/crates/${id}/order`, { method: 'PUT', body: { track_ids: trackIds } })
}
