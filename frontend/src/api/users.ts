import type { CreateUserPayload, UpdateUserPayload, User } from '../types/api'
import { apiFetch } from './client'

export function listUsers(): Promise<User[]> {
  return apiFetch<User[]>('/users')
}

export function createUser(payload: CreateUserPayload): Promise<User> {
  return apiFetch<User>('/users', { method: 'POST', body: payload })
}

export function updateUser(id: number, payload: UpdateUserPayload): Promise<User> {
  return apiFetch<User>(`/users/${id}`, { method: 'PATCH', body: payload })
}
