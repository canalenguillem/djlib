import type { Batch, BatchSummary } from '../types/api'
import { apiFetch } from './client'

/** Deja en el servidor una tanda de canciones para buscar y descargar solo. */
export function createBatch(
  name: string,
  crateId: number | null,
  songs: Array<{ title: string; artist: string | null }>,
): Promise<Batch> {
  return apiFetch<Batch>('/batches', {
    method: 'POST',
    body: { name, crate_id: crateId, songs },
  })
}

export function listBatches(): Promise<BatchSummary[]> {
  return apiFetch<BatchSummary[]>('/batches')
}

export function getBatch(id: number): Promise<Batch> {
  return apiFetch<Batch>(`/batches/${id}`)
}

export function cancelBatch(id: number): Promise<Batch> {
  return apiFetch<Batch>(`/batches/${id}/cancel`, { method: 'POST' })
}
