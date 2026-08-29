import { Navigate, createBrowserRouter } from 'react-router-dom'

import { ProtectedRoute } from './auth/ProtectedRoute'
import { RequireAdmin } from './auth/RequireAdmin'
import { Layout } from './components/Layout'
import { AccountPage } from './pages/Account'
import { LibraryPage } from './pages/Library'
import { LoginPage } from './pages/Login'
import { NotFoundPage } from './pages/NotFound'
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
