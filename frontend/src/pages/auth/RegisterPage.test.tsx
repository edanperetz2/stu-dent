import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { renderWithProviders } from '../../test/renderWithProviders'
import { RegisterPage } from './RegisterPage'

vi.mock('../../api/auth')

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('registers then logs in with the same credentials', async () => {
    vi.mocked(authApi.registerUser).mockResolvedValue({
      id: 'u1',
      email: 'new@example.com',
      full_name: 'New Student',
      role: 'student',
      is_active: true,
    })
    vi.mocked(authApi.login).mockResolvedValue({ access_token: 'tok456', token_type: 'bearer' })
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      id: 'u1',
      email: 'new@example.com',
      full_name: 'New Student',
      role: 'student',
      is_active: true,
    })

    renderWithProviders(<RegisterPage />, { route: '/register' })

    await userEvent.type(screen.getByLabelText('Full name'), 'New Student')
    await userEvent.type(screen.getByLabelText('Email'), 'new@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))

    await waitFor(() => {
      expect(authApi.registerUser).toHaveBeenCalledWith(
        'new@example.com',
        'password123',
        'New Student',
        'student',
      )
    })
    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith('new@example.com', 'password123')
    })
  })

  it('rejects a password shorter than 8 characters', async () => {
    renderWithProviders(<RegisterPage />, { route: '/register' })

    await userEvent.type(screen.getByLabelText('Full name'), 'New Student')
    await userEvent.type(screen.getByLabelText('Email'), 'new@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))

    expect(
      await screen.findByText('Password must be at least 8 characters'),
    ).toBeInTheDocument()
    expect(authApi.registerUser).not.toHaveBeenCalled()
  })
})
