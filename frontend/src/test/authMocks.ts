import type { ReactNode } from 'react'
import { vi } from 'vitest'
import type { Role } from '../api/types'
import type { Principal } from '../auth/AuthContext'

export function fakePrincipal(role: Role, overrides: Partial<Principal> = {}): Principal {
  return {
    token: 'test-token',
    id: 'test-user-id',
    role,
    fullName: 'Test User',
    email: 'test-user@example.com',
    ownerStudentId: null,
    ownerStudentName: null,
    ownerConfirmedAt: null,
    ...overrides,
  }
}

/** What every page-level test's own `vi.mock('.../auth/AuthContext', () =>
 * authContextMock(...))` factory should return. Replaces the real
 * AuthProvider (whose bootstrap effect resolves a principal asynchronously
 * from a stored token, via a real `getCurrentUser` call) with an
 * already-resolved one -- a page calling `useAuthToken()`/`useAuth()`
 * otherwise throws on its first, synchronous render, before the real
 * provider's effect would have had a chance to run. Each test file must
 * call `vi.mock` itself (its path argument has to be statically resolvable
 * per file, so this can't be done from inside a shared helper), but can
 * import this to build the returned object.
 *
 * Deliberately kept in its own module with no runtime import of
 * `../auth/AuthContext` (only a type-only one, erased at compile time) --
 * `renderWithProviders.tsx` has a *real* runtime import of `AuthProvider`
 * from that same module, and combining the two in one file created a
 * hoisting cycle: a test's `vi.mock('.../AuthContext', ...)` factory (which
 * vitest hoists above all imports) would need `renderWithProviders.tsx` to
 * have already finished initializing, which itself needs the now-mocked
 * `AuthContext` module to finish initializing first. */
export function authContextMock(principal: Principal | null) {
  return {
    useAuth: () => ({
      principal,
      isLoading: false,
      sessionExpired: false,
      clearSessionExpired: vi.fn(),
      handleSessionExpired: vi.fn(),
      login: vi.fn(),
      registerUser: vi.fn(),
      logout: vi.fn(),
    }),
    AuthProvider: ({ children }: { children: ReactNode }) => children,
  }
}
