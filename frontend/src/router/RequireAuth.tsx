import { Navigate, Outlet } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { RouteFallback } from '../components/RouteFallback'

interface RequireAuthProps {
  /** Restrict to specific roles; omit to allow any authenticated role. */
  roles?: Role[]
}

export function RequireAuth({ roles }: RequireAuthProps) {
  const { principal, isLoading } = useAuth()

  // A hard refresh of any protected route used to show a blank flash here
  // instead of the same loading fallback every lazy-loaded page chunk uses.
  if (isLoading) return <RouteFallback />

  if (!principal) return <Navigate to="/login" replace />

  if (roles && !roles.includes(principal.role)) return <Navigate to="/appointments" replace />

  return <Outlet />
}
