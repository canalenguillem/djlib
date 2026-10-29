import { Navigate, createBrowserRouter, useLocation } from 'react-router-dom'

import { ProtectedRoute } from './auth/ProtectedRoute'
import { RequireAdmin } from './auth/RequireAdmin'
import { RequireMenu } from './auth/RequireMenu'
import { useAuth } from './auth/useAuth'
import { Layout } from './components/Layout'
import { inicio } from './lib/menus'
import { AccountPage } from './pages/Account'
import { ArtistDetailPage } from './pages/ArtistDetail'
import { ArtistsPage } from './pages/Artists'
import { BeatportPage } from './pages/Beatport'
import { ColaPage } from './pages/Cola'
import { CrateDetailPage } from './pages/CrateDetail'
import { CratesPage } from './pages/Crates'
import { DownloadsPage } from './pages/Downloads'
import { FuentesLayout } from './pages/Fuentes'
import { LibraryPage } from './pages/Library'
import { ListenPage } from './pages/Listen'
import { MixerPage } from './pages/Mixer'
import { SpotifyPage } from './pages/Spotify'
import { LoginPage } from './pages/Login'
import { NotFoundPage } from './pages/NotFound'
import { RecognizePage } from './pages/Recognize'
import { TagsPage } from './pages/Tags'
import { UsersPage } from './pages/Users'
import { YoutubePage } from './pages/Youtube'

/** La portada es el primer apartado que tenga cada uno. */
function Inicio() {
  const { user } = useAuth()
  return <Navigate to={inicio(user)} replace />
}

/** Las fuentes vivian sueltas en el menu: los enlaces viejos siguen valiendo. */
function Movida({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={`${to}${search}`} replace />
}

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: '/', element: <Inicio /> },
          { element: <RequireMenu menu="library" />, children: [{ path: '/library', element: <LibraryPage /> }] },
          { element: <RequireMenu menu="recognize" />, children: [{ path: '/recognize', element: <RecognizePage /> }] },
          {
            element: <RequireMenu menu="artists" />,
            children: [
              { path: '/artists', element: <ArtistsPage /> },
              { path: '/artists/:artistId', element: <ArtistDetailPage /> },
            ],
          },
          { element: <RequireMenu menu="mixer" />, children: [{ path: '/mixer', element: <MixerPage /> }] },
          {
            path: '/fuentes',
            element: <FuentesLayout />,
            children: [
              { element: <RequireMenu menu="spotify" />, children: [{ path: 'spotify', element: <SpotifyPage /> }] },
              { element: <RequireMenu menu="beatport" />, children: [{ path: 'beatport', element: <BeatportPage /> }] },
              { element: <RequireMenu menu="youtube" />, children: [{ path: 'youtube', element: <YoutubePage /> }] },
              { path: 'cola', element: <ColaPage /> },
            ],
          },
          { path: '/spotify', element: <Movida to="/fuentes/spotify" /> },
          { path: '/beatport', element: <Movida to="/fuentes/beatport" /> },
          {
            element: <RequireMenu menu="crates" />,
            children: [
              { path: '/crates', element: <CratesPage /> },
              { path: '/crates/:crateId', element: <CrateDetailPage /> },
            ],
          },
          { element: <RequireMenu menu="listen" />, children: [{ path: '/listen', element: <ListenPage /> }] },
          { element: <RequireMenu menu="downloads" />, children: [{ path: '/downloads', element: <DownloadsPage /> }] },
          { element: <RequireMenu menu="tags" />, children: [{ path: '/tags', element: <TagsPage /> }] },
          { path: '/account', element: <AccountPage /> },
          {
            element: <RequireAdmin />,
            children: [{ path: '/users', element: <UsersPage /> }],
          },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
    ],
  },
])
