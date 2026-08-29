import { createContext, useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import * as authApi from '../api/auth'
import { SESSION_EXPIRED_EVENT, tokenStore } from '../api/client'
import type { TokenPair, User } from '../types/api'

export interface AuthContextValue {
  user: User | null
  loading: boolean
  sessionMessage: string | null
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  applyTokens: (tokens: TokenPair) => void
  setUser: (user: User) => void
  clearSessionMessage: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [sessionMessage, setSessionMessage] = useState<string | null>(null)

  // Al arrancar, si hay tokens guardados intentamos recuperar la sesion.
  useEffect(() => {
    let cancelled = false
    async function restore() {
      if (!tokenStore.access && !tokenStore.refresh) {
        setLoading(false)
        return
      }
      try {
        const me = await authApi.getMe()
        if (!cancelled) setUser(me)
      } catch {
        tokenStore.clear()
        if (!cancelled) setUser(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  // El cliente HTTP avisa cuando el refresh token deja de valer.
  useEffect(() => {
    function handleExpired() {
      setUser((current) => {
        if (current) setSessionMessage('Tu sesion ha expirado. Vuelve a iniciar sesion.')
        return null
      })
    }
    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpired)
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpired)
  }, [])

  const signIn = useCallback(async (username: string, password: string) => {
    const tokens = await authApi.login(username, password)
    tokenStore.save(tokens)
    const me = await authApi.getMe()
    setUser(me)
    setSessionMessage(null)
  }, [])

  const signOut = useCallback(async () => {
    await authApi.logout()
    setUser(null)
    setSessionMessage(null)
  }, [])

  const applyTokens = useCallback((tokens: TokenPair) => {
    tokenStore.save(tokens)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      sessionMessage,
      signIn,
      signOut,
      applyTokens,
      setUser,
      clearSessionMessage: () => setSessionMessage(null),
    }),
    [user, loading, sessionMessage, signIn, signOut, applyTokens],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
