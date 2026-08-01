import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { Role } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { RouteFallback } from '../components/RouteFallback'

interface RequireAuthProps {
  /** Restrict to specific roles; omit to allow any authenticated role. */
  roles?: Role[]
}

export function RequireAuth({ roles }: RequireAuthProps) {
  const { principal, isLoading } = useAuth()
  const location = useLocation()

  // A hard refresh of any protected route used to show a blank flash here
  // instead of the same loading fallback every lazy-loaded page chunk uses.
  if (isLoading) return <RouteFallback />

  // The attempted destination rides along as router state (not a query
  // param -- never put in the URL, and this way it survives even if the
  // path itself contains its own query params) so LoginPage can send the
  // user back to it instead of always landing on /appointments -- most
  // relevant for a mid-session token expiry, which lands here too.
  if (!principal) return <Navigate to="/login" replace state={{ from: location }} />

  if (roles && !roles.includes(principal.role)) return <Navigate to="/appointments" replace />

  return <Outlet />
}
