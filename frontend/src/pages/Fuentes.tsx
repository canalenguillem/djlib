import { NavLink, Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'
import { useLayout } from '../components/Layout'
import { COLA, inicio } from '../lib/menus'

const pestana = ({ isActive }: { isActive: boolean }) => (isActive ? 'tab tab--active' : 'tab')

/** De donde sale la musica: un submenu por fuente y la cola de lo que el
 *  servidor esta bajando de todas ellas. */
export function FuentesLayout() {
  const { user } = useAuth()
  const { fuentes, cargado, descargando } = useLayout()
  const { pathname } = useLocation()

  if (!cargado) return null
  if (!fuentes.length) return <Navigate to={inicio(user)} replace />
  if (pathname.replace(/\/$/, '') === '/fuentes') return <Navigate to={fuentes[0].to} replace />

  return (
    <div className="stack">
      <nav className="tabs fuentes__tabs" aria-label="Fuentes">
        {fuentes.map((f) => (
          <NavLink key={f.key} to={f.to} className={pestana}>
            {f.label}
          </NavLink>
        ))}
        <NavLink to={COLA} className={pestana}>
          En cola
          {descargando > 0 && <span className="nav__count">{descargando}</span>}
        </NavLink>
      </nav>
      <Outlet />
    </div>
  )
}
