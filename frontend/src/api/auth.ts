import type { TokenPair, User } from '../types/api'
import { apiFetch, tokenStore } from './client'

export function login(username: string, password: string): Promise<TokenPair> {
  return apiFetch<TokenPair>('/auth/login', {
    method: 'POST',
    body: { username, password },
    auth: false,
  })
}

export function getMe(): Promise<User> {
  return apiFetch<User>('/auth/me')
}

export function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<TokenPair> {
  return apiFetch<TokenPair>('/auth/me/password', {
    method: 'PATCH',
    body: { current_password: currentPassword, new_password: newPassword },
  })
}

export function updateEmail(email: string | null): Promise<User> {
  return apiFetch<User>('/auth/me/email', { method: 'PATCH', body: { email } })
}

export async function logout(): Promise<void> {
  const refreshToken = tokenStore.refresh
  if (refreshToken) {
    await apiFetch<void>('/auth/logout', {
      method: 'POST',
      body: { refresh_token: refreshToken },
      auth: false,
    }).catch(() => undefined)
  }
  tokenStore.clear()
}
