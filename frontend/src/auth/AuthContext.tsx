import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { getCurrentUser, login as apiLogin, registerUser as apiRegisterUser } from '../api/auth'
import { setUnauthorizedHandler } from '../api/httpClient'
import type { Role } from '../api/types'

export interface Principal {
  token: string
  id: string
  role: Role
  fullName: string
  email: string
  ownerStudentId: string | null
  ownerStudentName: string | null
  ownerConfirmedAt: string | null
}

interface StoredAuth {
  token: string
}

const STORAGE_KEY = 'stu_dent_auth'

interface AuthContextValue {
  principal: Principal | null
  isLoading: boolean
  // True from the moment an authenticated request comes back 401 until the
  // next successful login -- LoginPage reads this to show an explicit
  // "your session expired" message instead of a silent bounce back to it.
  sessionExpired: boolean
  clearSessionExpired: () => void
  // Same "logout + flag it as an expiry, not a manual click" behavior the
  // httpClient 401 handler below triggers, exposed so RealtimeContext can
  // route its own distinct expiry signal (the WebSocket's auth-failure
  // close code) through the identical flow instead of reimplementing it.
  handleSessionExpired: () => void
  login: (email: string, password: string, role?: Role) => Promise<void>
  registerUser: (
    email: string,
    password: string,
    fullName: string,
    role: Role,
    ownerStudentId?: string,
  ) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function persist(token: string): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ token } satisfies StoredAuth))
}

function toPrincipal(token: string, user: Awaited<ReturnType<typeof getCurrentUser>>): Principal {
  return {
    token,
    id: user.id,
    role: user.role,
    fullName: user.full_name,
    email: user.email,
    ownerStudentId: user.owner_student_id,
    ownerStudentName: user.owner_student_name,
    ownerConfirmedAt: user.owner_confirmed_at,
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [principal, setPrincipal] = useState<Principal | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [sessionExpired, setSessionExpired] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) {
      setIsLoading(false)
      return
    }

    ;(async () => {
      try {
        // Parsing lives inside the same try/catch as the network call
        // below -- malformed JSON here (corrupted write, a future format
        // migration, some browser storage quirk) used to throw straight
        // out of this effect with nothing catching it, and with no
        // top-level ErrorBoundary in the app that was an unrecoverable
        // white screen with no way back to even /login.
        const { token } = JSON.parse(stored) as StoredAuth
        const user = await getCurrentUser(token)
        setPrincipal(toPrincipal(token, user))
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      } finally {
        setIsLoading(false)
      }
    })()
  }, [])

  const login = useCallback(async (email: string, password: string, role?: Role): Promise<void> => {
    const { access_token: token } = await apiLogin(email, password, role)
    const user = await getCurrentUser(token)
    persist(token)
    setPrincipal(toPrincipal(token, user))
    setSessionExpired(false)
  }, [])

  const registerUser = useCallback(
    async (
      email: string,
      password: string,
      fullName: string,
      role: Role,
      ownerStudentId?: string,
    ): Promise<void> => {
      await apiRegisterUser(email, password, fullName, role, ownerStudentId)
      // A self-registered patient is left pending until their student
      // confirms them -- don't auto-login-and-redirect into the app for
      // that role; RegisterPage shows a "pending confirmation" message and
      // sends them to the normal login page instead.
      if (role !== 'patient') {
        await login(email, password)
      }
    },
    [login],
  )

  const logout = useCallback((): void => {
    localStorage.removeItem(STORAGE_KEY)
    setPrincipal(null)
  }, [])

  const clearSessionExpired = useCallback(() => setSessionExpired(false), [])

  const handleSessionExpired = useCallback((): void => {
    logout()
    setSessionExpired(true)
  }, [logout])

  useEffect(() => {
    // Centrally reacts to a 401 on any authenticated request (see
    // httpClient.ts) -- a logout the *user* didn't initiate, so it's
    // tracked separately from a manual "Log out" click via `sessionExpired`
    // rather than reusing `logout()` alone, letting LoginPage show an
    // explicit "your session expired" message instead of silently bouncing
    // back to a blank login form.
    setUnauthorizedHandler(handleSessionExpired)
    return () => setUnauthorizedHandler(null)
  }, [handleSessionExpired])

  const value = useMemo<AuthContextValue>(
    () => ({
      principal,
      isLoading,
      sessionExpired,
      clearSessionExpired,
      handleSessionExpired,
      login,
      registerUser,
      logout,
    }),
    [
      principal,
      isLoading,
      sessionExpired,
      clearSessionExpired,
      handleSessionExpired,
      login,
      registerUser,
      logout,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
