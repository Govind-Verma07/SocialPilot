/**
 * src/components/ProtectedRoute.jsx
 * -----------------------------------
 * Redirects unauthenticated users to /login, passing the intended
 * destination so the login page can redirect back after a successful auth.
 */

import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}
