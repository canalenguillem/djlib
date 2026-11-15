import type { AiProvider, AiSettings, AiTestResult } from '../types/api'
import { apiFetch } from './client'

export function getAiSettings(): Promise<AiSettings> {
  return apiFetch<AiSettings>('/me/ai')
}

/** Sin clave, solo cambia el modelo de una que ya estaba. */
export function saveAiKey(provider: AiProvider['id'], apiKey: string | null, model: string | null): Promise<AiSettings> {
  return apiFetch<AiSettings>(`/me/ai/${provider}`, { method: 'PUT', body: { api_key: apiKey, model } })
}

export function deleteAiKey(provider: AiProvider['id']): Promise<AiSettings> {
  return apiFetch<AiSettings>(`/me/ai/${provider}`, { method: 'DELETE' })
}

export function selectAiProvider(provider: AiProvider['id']): Promise<AiSettings> {
  return apiFetch<AiSettings>('/me/ai/selected', { method: 'PUT', body: { provider } })
}

export function testAiKey(provider: AiProvider['id']): Promise<AiTestResult> {
  return apiFetch<AiTestResult>(`/me/ai/${provider}/test`, { method: 'POST' })
}
