import { Outlet } from 'react-router-dom'

import { Loading } from '../components/Loading'
import { useAuth } from './useAuth'

export function RequireAdmin() {
  const { user, loading } = useAuth()

  if (loading) return <Loading />
  if (!user || user.role !== 'admin') {
    return (
      <div className="card">
        <h2>Sin permisos</h2>
        <p className="muted">
          Esta seccion solo esta disponible para administradores.
        </p>
      </div>
    )
  }
  return <Outlet />
}
