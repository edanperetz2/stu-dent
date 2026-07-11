import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { ApiError } from '../../api/httpClient'
import { renderWithProviders } from '../../test/renderWithProviders'
import { LoginPage } from './LoginPage'

vi.mock('../../api/auth')

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('logs in and persists the session', async () => {
    vi.mocked(authApi.login).mockResolvedValue({ access_token: 'tok123', token_type: 'bearer' })
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

    renderWithProviders(<LoginPage />, { route: '/login' })

    await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith('a@b.com', 'password123', undefined)
    })
    expect(JSON.parse(localStorage.getItem('stu_dent_auth')!)).toEqual({
      token: 'tok123',
    })
  })

  it('shows an error message on failed login', async () => {
    vi.mocked(authApi.login).mockRejectedValue(new ApiError(401, 'Incorrect email or password'))

    renderWithProviders(<LoginPage />, { route: '/login' })

    await userEvent.type(screen.getByLabelText('Email'), 'a@b.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('Incorrect email or password')).toBeInTheDocument()
  })
})
