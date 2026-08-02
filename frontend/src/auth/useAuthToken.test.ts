import { renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fakePrincipal } from '../test/authMocks'
import { useAuth } from './AuthContext'
import { useAuthToken } from './useAuthToken'

vi.mock('./AuthContext', () => ({ useAuth: vi.fn() }))

describe('useAuthToken', () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReset()
  })

  it("returns the authenticated principal's token", () => {
    vi.mocked(useAuth).mockReturnValue({
      principal: fakePrincipal('student', { token: 'the-real-token' }),
      isLoading: false,
      sessionExpired: false,
      clearSessionExpired: vi.fn(),
      handleSessionExpired: vi.fn(),
      login: vi.fn(),
      registerUser: vi.fn(),
      logout: vi.fn(),
    })

    const { result } = renderHook(() => useAuthToken())
    expect(result.current).toBe('the-real-token')
  })

  it('throws (not returns undefined/empty) when called with no authenticated principal', () => {
    vi.mocked(useAuth).mockReturnValue({
      principal: null,
      isLoading: false,
      sessionExpired: false,
      clearSessionExpired: vi.fn(),
      handleSessionExpired: vi.fn(),
      login: vi.fn(),
      registerUser: vi.fn(),
      logout: vi.fn(),
    })

    expect(() => renderHook(() => useAuthToken())).toThrow(
      'useAuthToken called without an authenticated principal',
    )
  })
})
