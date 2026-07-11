import { useAuth } from './AuthContext'

/** Only safe to use inside a page rendered under <RequireAuth>. */
export function useAuthToken(): string {
  const { principal } = useAuth()
  if (!principal) {
    throw new Error('useAuthToken called without an authenticated principal')
  }
  return principal.token
}
