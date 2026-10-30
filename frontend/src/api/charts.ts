import type { ChartCombined, ChartSource } from '../types/api'
import { apiFetch } from './client'

export function listSources(): Promise<ChartSource[]> {
  return apiFetch<ChartSource[]>('/charts/sources')
}

/** Las listas elegidas cruzadas en una, sin repetir. */
export function combined(sources: string[], limit: number): Promise<ChartCombined> {
  const params = new URLSearchParams({ limit: String(limit) })
  for (const s of sources) params.append('source', s)
  return apiFetch<ChartCombined>(`/charts/combined?${params}`)
}
