import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../api/auth'
import { listPatients } from '../api/patients'
import { LoginPage } from '../pages/auth/LoginPage'
import { useAuthToken } from '../auth/useAuthToken'
import { renderWithProviders } from '../test/renderWithProviders'
import { resetAuthTestState } from '../test/resetAuthTestState'
import { RequireAuth } from './RequireAuth'

vi.mock('../api/auth')

const FAKE_USER = {
  id: 'u1',
  email: 'a@b.com',
  full_name: 'Ada',
  role: 'student' as const,
  is_active: true,
  owner_student_id: null,
  owner_student_name: null,
  owner_confirmed_at: null,
  contact_phone: null,
  preferred_time_of_day: null,
}

function ProtectedPage() {
  return <div>Protected content</div>
}

describe('RequireAuth', () => {
  beforeEach(resetAuthTestState)

  it('redirects to login and returns to the originally-requested page after logging in', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access_token: 'tok1', token_type: 'bearer' })
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(FAKE_USER)

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/patients" element={<ProtectedPage />} />
        </Route>
      </Routes>,
      { route: '/patients' },
    )

    // No stored token -> bounced straight to /login.
    expect(await screen.findByLabelText('Email')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    // Lands back on /patients, not the generic /appointments default.
    expect(await screen.findByText('Protected content')).toBeInTheDocument()
  })

  it('shows an explicit session-expired message after an authenticated request gets a 401', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue(FAKE_USER)
    localStorage.setItem('stu_dent_auth', JSON.stringify({ token: 'tok1' }))

    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        new Response(JSON.stringify({ detail: 'Could not validate credentials' }), {
          status: 401,
        }),
      )

    // A real page reaching through the real (unmocked) httpClient -- this
    // exercises the actual chain: httpClient's 401 branch -> AuthContext's
    // registered unauthorized handler -> logout + sessionExpired -> the
    // RequireAuth guard's own reactive redirect -> LoginPage's banner.
    function PageMakingAnAuthenticatedRequest() {
      const token = useAuthToken()
      useEffect(() => {
        listPatients(token).catch(() => {})
      }, [token])
      return <div>Protected content</div>
    }

    renderWithProviders(
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/patients" element={<PageMakingAnAuthenticatedRequest />} />
        </Route>
      </Routes>,
      { route: '/patients' },
    )

    expect(
      await screen.findByText('Your session expired. Log in again to continue where you left off.'),
    ).toBeInTheDocument()

    fetchSpy.mockRestore()
  })
})
