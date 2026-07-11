import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../api/auth'
import { AuthProvider, useAuth } from './AuthContext'

vi.mock('../api/auth')

function PrincipalProbe() {
  const { principal, isLoading } = useAuth()
  if (isLoading) return <div>loading</div>
  return <div>{principal ? `logged in as ${principal.fullName}` : 'logged out'}</div>
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('rehydrates a persisted session on load', async () => {
    localStorage.setItem('stu_dent_auth', JSON.stringify({ token: 'tok123' }))
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      id: 'u1',
      email: 'a@b.com',
      full_name: 'Ada',
      role: 'student',
      is_active: true,
      owner_student_id: null,
      owner_confirmed_at: null,
      contact_phone: null,
      preferred_time_of_day: null,
    })

    render(
      <AuthProvider>
        <PrincipalProbe />
      </AuthProvider>,
    )

    expect(await screen.findByText('logged in as Ada')).toBeInTheDocument()
    expect(authApi.getCurrentUser).toHaveBeenCalledWith('tok123')
  })

  it('rehydrates a persisted patient session on load', async () => {
    localStorage.setItem('stu_dent_auth', JSON.stringify({ token: 'ptok789' }))
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      id: 'p1',
      email: 'pat@example.com',
      full_name: 'Pat Patient',
      role: 'patient',
      is_active: true,
      owner_student_id: 's1',
      owner_confirmed_at: '2026-01-01T00:00:00Z',
      contact_phone: null,
      preferred_time_of_day: null,
    })

    render(
      <AuthProvider>
        <PrincipalProbe />
      </AuthProvider>,
    )

    expect(await screen.findByText('logged in as Pat Patient')).toBeInTheDocument()
  })

  it('clears a stale/invalid token instead of staying logged in', async () => {
    localStorage.setItem('stu_dent_auth', JSON.stringify({ token: 'expired' }))
    vi.mocked(authApi.getCurrentUser).mockRejectedValue(new Error('401'))

    render(
      <AuthProvider>
        <PrincipalProbe />
      </AuthProvider>,
    )

    expect(await screen.findByText('logged out')).toBeInTheDocument()
    expect(localStorage.getItem('stu_dent_auth')).toBeNull()
  })
})
