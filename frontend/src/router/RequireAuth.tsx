import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import type { Role } from '../api/types'

interface RequireAuthProps {
  /** Restrict to one or both principal kinds; omit to allow either. */
  allow?: ('user' | 'patient')[]
  /** Restrict to specific User roles; only meaningful for kind: 'user'. */
  roles?: Role[]
}

export function RequireAuth({ allow, roles }: RequireAuthProps) {
  const { principal, isLoading } = useAuth()

  if (isLoading) return null

  if (!principal) return <Navigate to="/login" replace />

  if (allow && !allow.includes(principal.kind)) return <Navigate to="/" replace />

  if (roles && principal.kind === 'user' && !roles.includes(principal.role)) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
