import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import * as recognitionApi from '../api/recognition'
import * as spotifyApi from '../api/spotify'
import { useAuth } from '../auth/useAuth'
import { MENUS, puedeVer } from '../lib/menus'
import { useDownloadsCount } from '../lib/useDownloadsCount'

export function Layout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  // La mesa de mezclas necesita todo el ancho: dos platos y la mesa en medio
  const ancha = useLocation().pathname.startsWith('/mixer')
  const [recognitionEnabled, setRecognitionEnabled] = useState(false)
  const [spotifyEnabled, setSpotifyEnabled] = useState(false)
  // Canciones que faltan en las descargas del servidor, siempre a la vista
  const descargando = useDownloadsCount()

  // El enlace solo aparece si el servidor tiene clave de reconocimiento.
  useEffect(() => {
    recognitionApi
      .getRecognitionStatus()
      .then((estado) => setRecognitionEnabled(estado.enabled))
      .catch(() => setRecognitionEnabled(false))
    spotifyApi
      .getSpotifyStatus()
      .then((estado) => setSpotifyEnabled(estado.enabled))
      .catch(() => setSpotifyEnabled(false))
  }, [])

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
          {MENUS.filter(
            (m) =>
              puedeVer(user, m.key) &&
              // Sin clave en el servidor, el apartado no hace nada
              (m.key !== 'recognize' || recognitionEnabled) &&
              (m.key !== 'spotify' || spotifyEnabled),
          ).map((m) => (
            <NavLink key={m.key} to={m.to}>
              {m.label}
              {m.key === 'downloads' && descargando > 0 && (
                <span className="nav__count" aria-label={`${descargando} pendientes`}>
                  {descargando}
                </span>
              )}
            </NavLink>
          ))}
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
        <Outlet />
      </main>
    </div>
  )
}
