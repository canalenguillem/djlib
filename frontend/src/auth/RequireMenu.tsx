import { Navigate, Outlet } from 'react-router-dom'

import { inicio, puedeVer } from '../lib/menus'
import type { Menu } from '../types/api'
import { useAuth } from './useAuth'

/** Si alguien escribe a mano la direccion de un apartado que no tiene, va al
 *  primero que si. */
export function RequireMenu({ menu }: { menu: Menu }) {
  const { user } = useAuth()
  if (!puedeVer(user, menu)) return <Navigate to={inicio(user)} replace />
  return <Outlet />
}
