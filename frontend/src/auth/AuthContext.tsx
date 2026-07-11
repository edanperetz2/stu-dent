import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import {
  getCurrentPatient,
  getCurrentUser,
  login as apiLogin,
  patientLogin as apiPatientLogin,
  registerUser as apiRegisterUser,
} from '../api/auth'
import type { Role } from '../api/types'

export type Principal =
  | { kind: 'user'; token: string; id: string; role: Role; fullName: string; email: string }
  | { kind: 'patient'; token: string; id: string; fullName: string; email: string | null }

interface StoredAuth {
  kind: 'user' | 'patient'
  token: string
}

const STORAGE_KEY = 'stu_dent_auth'

interface AuthContextValue {
  principal: Principal | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  registerUser: (email: string, password: string, fullName: string, role: Role) => Promise<void>
  patientLogin: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function persist(kind: 'user' | 'patient', token: string): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ kind, token } satisfies StoredAuth))
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [principal, setPrincipal] = useState<Principal | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) {
      setIsLoading(false)
      return
    }

    const { kind, token } = JSON.parse(stored) as StoredAuth
    ;(async () => {
      try {
        if (kind === 'user') {
          const user = await getCurrentUser(token)
          setPrincipal({
            kind: 'user',
            token,
            id: user.id,
            role: user.role,
            fullName: user.full_name,
            email: user.email,
          })
        } else {
          const patient = await getCurrentPatient(token)
          setPrincipal({
            kind: 'patient',
            token,
            id: patient.id,
            fullName: patient.full_name,
            email: patient.email,
          })
        }
      } catch {
        localStorage.removeItem(STORAGE_KEY)
      } finally {
        setIsLoading(false)
      }
    })()
  }, [])

  async function login(email: string, password: string): Promise<void> {
    const { access_token: token } = await apiLogin(email, password)
    const user = await getCurrentUser(token)
    persist('user', token)
    setPrincipal({
      kind: 'user',
      token,
      id: user.id,
      role: user.role,
      fullName: user.full_name,
      email: user.email,
    })
  }

  async function registerUser(
    email: string,
    password: string,
    fullName: string,
    role: Role,
  ): Promise<void> {
    await apiRegisterUser(email, password, fullName, role)
    await login(email, password)
  }

  async function patientLogin(email: string, password: string): Promise<void> {
    const { access_token: token } = await apiPatientLogin(email, password)
    const patient = await getCurrentPatient(token)
    persist('patient', token)
    setPrincipal({
      kind: 'patient',
      token,
      id: patient.id,
      fullName: patient.full_name,
      email: patient.email,
    })
  }

  function logout(): void {
    localStorage.removeItem(STORAGE_KEY)
    setPrincipal(null)
  }

  const value: AuthContextValue = {
    principal,
    isLoading,
    login,
    registerUser,
    patientLogin,
    logout,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
