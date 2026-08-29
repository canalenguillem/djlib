import type { TokenPair } from '../types/api'

// Por defecto relativa: el dev server (o nginx en produccion) reenvia /api al
// backend, que no esta publicado en el host.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')

const ACCESS_KEY = 'djlib.access_token'
const REFRESH_KEY = 'djlib.refresh_token'

export const SESSION_EXPIRED_EVENT = 'djlib:session-expired'

export const tokenStore = {
  get access(): string | null {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh(): string | null {
    return localStorage.getItem(REFRESH_KEY)
  },
  save(tokens: TokenPair): void {
    localStorage.setItem(ACCESS_KEY, tokens.access_token)
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token)
  },
  clear(): void {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** FastAPI devuelve `detail` como texto o como lista de errores de validacion. */
function extractMessage(status: number, body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string }
      if (first?.msg) return first.msg
    }
  }
  if (status === 0) return 'No se puede contactar con el servidor.'
  return `Error inesperado (${status}).`
}

function notifySessionExpired(): void {
  tokenStore.clear()
  window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
}

// Si varias peticiones caducan a la vez, todas esperan al mismo refresh.
let refreshInFlight: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refreshToken = tokenStore.refresh
  if (!refreshToken) throw new ApiError(401, 'Sesion expirada.')

  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!response.ok) throw new ApiError(401, 'Sesion expirada.')
      const tokens = (await response.json()) as TokenPair
      tokenStore.save(tokens)
      return tokens.access_token
    })().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

interface RequestOptions {
  method?: string
  body?: unknown
  auth?: boolean
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true } = options

  const send = async (token: string | null): Promise<Response> => {
    const headers: Record<string, string> = {}
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (token) headers.Authorization = `Bearer ${token}`
    try {
      return await fetch(`${API_BASE}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch {
      throw new ApiError(0, 'No se puede contactar con el servidor.')
    }
  }

  let response = await send(auth ? tokenStore.access : null)

  // Access token caducado: lo renovamos una vez y reintentamos.
  if (response.status === 401 && auth && tokenStore.refresh) {
    try {
      const newAccess = await refreshAccessToken()
      response = await send(newAccess)
    } catch {
      notifySessionExpired()
      throw new ApiError(401, 'Tu sesion ha expirado. Vuelve a iniciar sesion.')
    }
  }

  if (response.status === 401 && auth) {
    notifySessionExpired()
    throw new ApiError(401, 'Tu sesion ha expirado. Vuelve a iniciar sesion.')
  }

  if (response.status === 204) return undefined as T

  const payload = await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(response.status, extractMessage(response.status, payload))
  return payload as T
}
