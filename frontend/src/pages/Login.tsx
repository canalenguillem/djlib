import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { Alert } from '../components/Alert'
import { GoogleButton } from '../components/GoogleButton'
import { Loading } from '../components/Loading'
import { useAuth } from '../auth/useAuth'

export function LoginPage() {
  const { user, loading, signIn, signInWithGoogle, sessionMessage, clearSessionMessage } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (loading) return <Loading />
  if (user) return <Navigate to="/" replace />

  async function entrar(intento: () => Promise<void>, error401: (err: ApiError) => string) {
    setError(null)
    clearSessionMessage()
    setSubmitting(true)
    try {
      await intento()
      const from = (location.state as { from?: string } | null)?.from
      navigate(from && from !== '/login' ? from : '/', { replace: true })
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError('Demasiados intentos fallidos. Espera unos minutos y vuelve a probar.')
      } else if (err instanceof ApiError && err.status === 401) {
        setError(error401(err))
      } else if (err instanceof ApiError && err.status === 403) {
        setError(err.message)
      } else {
        setError(err instanceof Error ? err.message : 'Error inesperado.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    void entrar(
      () => signIn(username.trim(), password),
      () => 'Usuario o contrasena incorrectos.',
    )
  }

  function handleGoogle(credential: string) {
    // El servidor dice por que: sin cuenta con ese correo, sin verificar...
    void entrar(() => signInWithGoogle(credential), (err) => err.message)
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
          <span>Usuario o correo</span>
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

        <GoogleButton onCredential={handleGoogle} />
      </form>
    </div>
  )
}
