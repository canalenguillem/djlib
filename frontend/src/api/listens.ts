import type { ListenSource, ListenStats } from '../types/api'
import { apiFetch } from './client'

export function registerListen(trackId: number, source: ListenSource): Promise<void> {
  return apiFetch<void>('/listens', { method: 'POST', body: { track_id: trackId, source } })
}

export function getListenStats(): Promise<ListenStats> {
  return apiFetch<ListenStats>('/listens/stats')
}
