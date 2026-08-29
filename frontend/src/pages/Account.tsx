import { useState } from 'react'
import type { FormEvent } from 'react'

import * as authApi from '../api/auth'
import { Alert } from '../components/Alert'
import { useAuth } from '../auth/useAuth'

export function AccountPage() {
  const { user, setUser, applyTokens } = useAuth()

  const [email, setEmail] = useState(user?.email ?? '')
  const [emailError, setEmailError] = useState<string | null>(null)
  const [emailOk, setEmailOk] = useState<string | null>(null)
  const [savingEmail, setSavingEmail] = useState(false)

  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [repeatPassword, setRepeatPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordOk, setPasswordOk] = useState<string | null>(null)
  const [savingPassword, setSavingPassword] = useState(false)

  if (!user) return null

  async function handleEmailSubmit(event: FormEvent) {
    event.preventDefault()
    setEmailError(null)
    setEmailOk(null)
    setSavingEmail(true)
    try {
      const updated = await authApi.updateEmail(email.trim() || null)
      setUser(updated)
      setEmail(updated.email ?? '')
      setEmailOk('Email actualizado.')
    } catch (err) {
      setEmailError(err instanceof Error ? err.message : 'No se pudo guardar el email.')
    } finally {
      setSavingEmail(false)
    }
  }

  async function handlePasswordSubmit(event: FormEvent) {
    event.preventDefault()
    setPasswordError(null)
    setPasswordOk(null)

    if (newPassword !== repeatPassword) {
      setPasswordError('La nueva contrasena y su repeticion no coinciden.')
      return
    }

    setSavingPassword(true)
    try {
      // El backend revoca las sesiones anteriores y devuelve un par nuevo:
      // lo guardamos para no echar al usuario de la aplicacion.
      const tokens = await authApi.changePassword(currentPassword, newPassword)
      applyTokens(tokens)
      setCurrentPassword('')
      setNewPassword('')
      setRepeatPassword('')
      setPasswordOk('Contrasena actualizada. Las demas sesiones se han cerrado.')
    } catch (err) {
      setPasswordError(
        err instanceof Error ? err.message : 'No se pudo cambiar la contrasena.',
      )
    } finally {
      setSavingPassword(false)
    }
  }

  return (
    <div className="stack">
      <h1>Mi cuenta</h1>

      <section className="card">
        <h2>Datos</h2>
        <dl className="datalist">
          <div>
            <dt>Usuario</dt>
            <dd>{user.username}</dd>
          </div>
          <div>
            <dt>Rol</dt>
            <dd>
              <span className="badge">{user.role}</span>
            </dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd>{user.is_active ? 'Activo' : 'Desactivado'}</dd>
          </div>
        </dl>
      </section>

      <section className="card">
        <h2>Email</h2>
        <p className="muted">Opcional. Dejalo vacio para eliminarlo.</p>
        {emailError && <Alert kind="error">{emailError}</Alert>}
        {emailOk && <Alert kind="success">{emailOk}</Alert>}
        <form onSubmit={handleEmailSubmit} className="stack">
          <label className="field">
            <span>Correo electronico</span>
            <input
              type="email"
              value={email}
              autoComplete="email"
              placeholder="tu@correo.com"
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <div>
            <button type="submit" className="btn btn--primary" disabled={savingEmail}>
              {savingEmail ? 'Guardando...' : 'Guardar email'}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2>Cambiar contrasena</h2>
        {passwordError && <Alert kind="error">{passwordError}</Alert>}
        {passwordOk && <Alert kind="success">{passwordOk}</Alert>}
        <form onSubmit={handlePasswordSubmit} className="stack">
          <label className="field">
            <span>Contrasena actual</span>
            <input
              type="password"
              value={currentPassword}
              autoComplete="current-password"
              required
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Nueva contrasena</span>
            <input
              type="password"
              value={newPassword}
              autoComplete="new-password"
              required
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Repite la nueva contrasena</span>
            <input
              type="password"
              value={repeatPassword}
              autoComplete="new-password"
              required
              onChange={(e) => setRepeatPassword(e.target.value)}
            />
          </label>
          <div>
            <button type="submit" className="btn btn--primary" disabled={savingPassword}>
              {savingPassword ? 'Guardando...' : 'Cambiar contrasena'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
