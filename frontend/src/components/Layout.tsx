import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate, useOutletContext } from 'react-router-dom'

import * as recognitionApi from '../api/recognition'
import * as spotifyApi from '../api/spotify'
import { useAuth } from '../auth/useAuth'
import { MENUS, puedeVer } from '../lib/menus'
import type { MenuDef } from '../lib/menus'
import { useDownloadsCount } from '../lib/useDownloadsCount'

interface LayoutContext {
  /** Las fuentes que puede usar, para el submenu. */
  fuentes: MenuDef[]
  /** Hasta saber que claves tiene el servidor no se sabe cual es la primera. */
  cargado: boolean
  descargando: number
}

export function useLayout(): LayoutContext {
  return useOutletContext<LayoutContext>()
}

export function Layout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  // La mesa de mezclas necesita todo el ancho: dos platos y la mesa en medio
  const ancha = useLocation().pathname.startsWith('/mixer')
  const [recognitionEnabled, setRecognitionEnabled] = useState(false)
  const [spotifyEnabled, setSpotifyEnabled] = useState(false)
  const [cargado, setCargado] = useState(false)
  // Canciones que faltan en las descargas del servidor, siempre a la vista
  const descargando = useDownloadsCount()

  // El enlace solo aparece si el servidor tiene clave de reconocimiento.
  useEffect(() => {
    void Promise.all([
      recognitionApi
        .getRecognitionStatus()
        .then((estado) => setRecognitionEnabled(estado.enabled))
        .catch(() => setRecognitionEnabled(false)),
      spotifyApi
        .getSpotifyStatus()
        .then((estado) => setSpotifyEnabled(estado.enabled))
        .catch(() => setSpotifyEnabled(false)),
    ]).then(() => setCargado(true))
  }, [])

  const visibles = MENUS.filter(
    (m) =>
      puedeVer(user, m.key) &&
      // Sin clave en el servidor, el apartado no hace nada
      (m.key !== 'recognize' || recognitionEnabled) &&
      (m.key !== 'spotify' || spotifyEnabled),
  )
  const fuentes = visibles.filter((m) => m.fuente)

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__logo" aria-hidden="true" />
          DJ Library
        </div>
        <nav className="topbar__nav">
          {visibles.map((m) => {
            if (!m.fuente) return <NavLink key={m.key} to={m.to}>{m.label}</NavLink>
            // Las fuentes van todas en una entrada, donde estaba la primera
            if (m !== fuentes[0]) return null
            return (
              <NavLink key="fuentes" to="/fuentes">
                Fuentes
                {descargando > 0 && (
                  <span className="nav__count" aria-label={`${descargando} pendientes`}>
                    {descargando}
                  </span>
                )}
              </NavLink>
            )
          })}
          <NavLink to="/account">Mi cuenta</NavLink>
          {user?.role === 'admin' && <NavLink to="/users">Usuarios</NavLink>}
        </nav>
        <div className="topbar__user">
          {user && (
            <>
              <span className="muted">
                {user.username} <span className="badge">{user.role}</span>
              </span>
              <button type="button" className="btn btn--ghost" onClick={handleSignOut}>
                Cerrar sesion
              </button>
            </>
          )}
        </div>
      </header>
      <main className={ancha ? 'content content--wide' : 'content'}>
        <Outlet context={{ fuentes, cargado, descargando } satisfies LayoutContext} />
      </main>
    </div>
  )
}
