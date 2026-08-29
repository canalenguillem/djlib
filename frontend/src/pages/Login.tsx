import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { useAuth } from '../auth/useAuth'

export function LoginPage() {
  const { user, loading, signIn, sessionMessage, clearSessionMessage } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (loading) return <Loading />
  if (user) return <Navigate to="/account" replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    clearSessionMessage()
    setSubmitting(true)
    try {
      await signIn(username.trim(), password)
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from !== '/login' ? from : '/account', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError('Demasiados intentos fallidos. Espera unos minutos y vuelve a probar.')
      } else if (err instanceof ApiError && err.status === 401) {
        setError('Usuario o contrasena incorrectos.')
      } else {
        setError(err instanceof Error ? err.message : 'Error inesperado.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login">
      <form className="card login__card" onSubmit={handleSubmit}>
        <h1 className="login__title">
          <span className="topbar__logo" aria-hidden="true" />
          DJ Library
        </h1>
        <p className="muted">Introduce tus credenciales para acceder.</p>

        {sessionMessage && <Alert kind="info">{sessionMessage}</Alert>}
        {error && <Alert kind="error">{error}</Alert>}

        <label className="field">
          <span>Usuario</span>
          <input
            type="text"
            value={username}
            autoComplete="username"
            autoFocus
            required
            onChange={(e) => setUsername(e.target.value)}
          />
        </label>

        <label className="field">
          <span>Contrasena</span>
          <input
            type="password"
            value={password}
            autoComplete="current-password"
            required
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>

        <button type="submit" className="btn btn--primary" disabled={submitting}>
          {submitting ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
