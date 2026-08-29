import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

import * as usersApi from '../api/users'
import { Alert } from '../components/Alert'
import { Loading } from '../components/Loading'
import { useAuth } from '../auth/useAuth'
import type { UpdateUserPayload, User, UserRole } from '../types/api'

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(`${value}Z`).toLocaleString('es-ES')
}

export function UsersPage() {
  const { user: currentUser } = useAuth()

  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('user')
  const [createError, setCreateError] = useState<string | null>(null)
  const [createOk, setCreateOk] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  async function loadUsers() {
    setListError(null)
    try {
      setUsers(await usersApi.listUsers())
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'No se pudo cargar el listado.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadUsers()
  }, [])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setCreateError(null)
    setCreateOk(null)
    setCreating(true)
    try {
      const created = await usersApi.createUser({
        username: username.trim(),
        email: email.trim() || null,
        password,
        role,
      })
      setCreateOk(`Usuario "${created.username}" creado.`)
      setUsername('')
      setEmail('')
      setPassword('')
      setRole('user')
      await loadUsers()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'No se pudo crear el usuario.')
    } finally {
      setCreating(false)
    }
  }

  async function patchUser(id: number, payload: UpdateUserPayload) {
    setActionError(null)
    setBusyId(id)
    try {
      const updated = await usersApi.updateUser(id, payload)
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)))
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'No se pudo actualizar.')
    } finally {
      setBusyId(null)
    }
  }

  if (loading) return <Loading />

  return (
    <div className="stack">
      <h1>Usuarios</h1>

      <section className="card">
        <h2>Alta de usuario</h2>
        {createError && <Alert kind="error">{createError}</Alert>}
        {createOk && <Alert kind="success">{createOk}</Alert>}
        <form className="grid-form" onSubmit={handleCreate}>
          <label className="field">
            <span>Usuario</span>
            <input
              type="text"
              value={username}
              required
              minLength={3}
              pattern="[A-Za-z0-9._\-]+"
              title="Letras, numeros, punto, guion y guion bajo"
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Email (opcional)</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="field">
            <span>Contrasena inicial</span>
            <input
              type="password"
              value={password}
              required
              autoComplete="new-password"
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Rol</span>
            <select value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
              <option value="user">user</option>
              <option value="admin">admin</option>
            </select>
          </label>
          <div className="grid-form__actions">
            <button type="submit" className="btn btn--primary" disabled={creating}>
              {creating ? 'Creando...' : 'Crear usuario'}
            </button>
          </div>
        </form>
      </section>

      <section className="card">
        <h2>Listado</h2>
        {listError && <Alert kind="error">{listError}</Alert>}
        {actionError && <Alert kind="error">{actionError}</Alert>}
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Usuario</th>
                <th>Email</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Ultimo acceso</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id
                return (
                  <tr key={u.id} className={u.is_active ? '' : 'row--inactive'}>
                    <td>
                      {u.username}
                      {isSelf && <span className="muted"> (tu)</span>}
                    </td>
                    <td>{u.email ?? '—'}</td>
                    <td>
                      <select
                        value={u.role}
                        disabled={isSelf || busyId === u.id}
                        onChange={(e) => patchUser(u.id, { role: e.target.value as UserRole })}
                      >
                        <option value="user">user</option>
                        <option value="admin">admin</option>
                      </select>
                    </td>
                    <td>
                      <span className={u.is_active ? 'badge badge--ok' : 'badge badge--off'}>
                        {u.is_active ? 'activo' : 'desactivado'}
                      </span>
                    </td>
                    <td className="muted">{formatDate(u.last_login_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="btn btn--ghost"
                        disabled={isSelf || busyId === u.id}
                        onClick={() => patchUser(u.id, { is_active: !u.is_active })}
                      >
                        {u.is_active ? 'Desactivar' : 'Activar'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
