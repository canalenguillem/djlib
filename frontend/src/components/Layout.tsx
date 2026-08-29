import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/useAuth'

export function Layout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

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
