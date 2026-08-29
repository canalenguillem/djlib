export type UserRole = 'admin' | 'user'

export interface User {
  id: number
  username: string
  email: string | null
  role: UserRole
  is_active: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface CreateUserPayload {
  username: string
  email?: string | null
  password: string
  role: UserRole
}

export interface UpdateUserPayload {
  is_active?: boolean
  role?: UserRole
}
