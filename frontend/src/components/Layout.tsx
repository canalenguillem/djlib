import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import * as recognitionApi from '../api/recognition'
import * as spotifyApi from '../api/spotify'
import { useAuth } from '../auth/useAuth'

export function Layout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [recognitionEnabled, setRecognitionEnabled] = useState(false)
  const [spotifyEnabled, setSpotifyEnabled] = useState(false)

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
          <NavLink to="/library">Biblioteca</NavLink>
          {recognitionEnabled && <NavLink to="/recognize">Reconocer</NavLink>}
          <NavLink to="/mixer">Mezclar</NavLink>
          {spotifyEnabled && <NavLink to="/spotify">Spotify</NavLink>}
          <NavLink to="/crates">Crates</NavLink>
          <NavLink to="/artists">Artistas</NavLink>
          <NavLink to="/tags">Etiquetas</NavLink>
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
      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
