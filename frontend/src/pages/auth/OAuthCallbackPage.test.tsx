import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { OAuthCallbackPage } from './OAuthCallbackPage'

vi.mock('../../api/auth')

describe('OAuthCallbackPage', () => {
  beforeEach(resetAuthTestState)

  it('consumes an OAuth token and persists the resulting session', async () => {
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      id: 'u1',
      email: 'social@example.com',
      full_name: 'Social User',
      role: 'student',
      is_active: true,
      owner_student_id: null,
      owner_student_name: null,
      owner_confirmed_at: null,
      contact_phone: null,
      preferred_time_of_day: null,
    })

    window.history.pushState(null, '', '/oauth/callback#token=oauth-token&next=%2Fappointments')
    renderWithProviders(<OAuthCallbackPage />, { route: '/oauth/callback' })

    await waitFor(() => expect(authApi.getCurrentUser).toHaveBeenCalledWith('oauth-token'))
    expect(JSON.parse(localStorage.getItem('stu_dent_auth')!)).toEqual({ token: 'oauth-token' })
  })

  it('shows provider callback errors', () => {
    renderWithProviders(<OAuthCallbackPage />, {
      route: '/oauth/callback?error=Sign-in+was+cancelled',
    })

    expect(screen.getByRole('alert')).toHaveTextContent('Sign-in was cancelled')
  })
})
