import { Navigate, createBrowserRouter } from 'react-router-dom'

import { ProtectedRoute } from './auth/ProtectedRoute'
import { RequireAdmin } from './auth/RequireAdmin'
import { Layout } from './components/Layout'
import { AccountPage } from './pages/Account'
import { ArtistDetailPage } from './pages/ArtistDetail'
import { ArtistsPage } from './pages/Artists'
import { CrateDetailPage } from './pages/CrateDetail'
import { CratesPage } from './pages/Crates'
import { LibraryPage } from './pages/Library'
import { MixerPage } from './pages/Mixer'
import { LoginPage } from './pages/Login'
import { NotFoundPage } from './pages/NotFound'
import { RecognizePage } from './pages/Recognize'
import { TagsPage } from './pages/Tags'
import { UsersPage } from './pages/Users'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <Layout />,
        children: [
          { path: '/', element: <Navigate to="/library" replace /> },
          { path: '/library', element: <LibraryPage /> },
          { path: '/recognize', element: <RecognizePage /> },
          { path: '/artists', element: <ArtistsPage /> },
          { path: '/artists/:artistId', element: <ArtistDetailPage /> },
          { path: '/mixer', element: <MixerPage /> },
          { path: '/crates', element: <CratesPage /> },
          { path: '/crates/:crateId', element: <CrateDetailPage /> },
          { path: '/tags', element: <TagsPage /> },
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
