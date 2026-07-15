import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import type { Role } from '../api/types'

interface RequireAuthProps {
  /** Restrict to specific roles; omit to allow any authenticated role. */
  roles?: Role[]
}

export function RequireAuth({ roles }: RequireAuthProps) {
  const { principal, isLoading } = useAuth()

  if (isLoading) return null

  if (!principal) return <Navigate to="/login" replace />

  if (roles && !roles.includes(principal.role)) return <Navigate to="/appointments" replace />

  return <Outlet />
}
