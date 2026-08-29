import type { Tag, TagKind } from '../types/api'
import { apiFetch } from './client'

export function listTags(): Promise<Tag[]> {
  return apiFetch<Tag[]>('/tags')
}

export function createTag(kind: TagKind, name: string): Promise<Tag> {
  return apiFetch<Tag>('/tags', { method: 'POST', body: { kind, name } })
}

export function renameTag(id: number, name: string): Promise<Tag> {
  return apiFetch<Tag>(`/tags/${id}`, { method: 'PATCH', body: { name } })
}

export function deleteTag(id: number): Promise<void> {
  return apiFetch<void>(`/tags/${id}`, { method: 'DELETE' })
}
