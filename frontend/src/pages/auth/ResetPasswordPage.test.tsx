import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { ApiError } from '../../api/httpClient'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { ResetPasswordPage } from './ResetPasswordPage'

vi.mock('../../api/auth')

describe('ResetPasswordPage', () => {
  beforeEach(resetAuthTestState)

  it('shows a request-a-new-link message when no token is present in the URL', () => {
    renderWithProviders(<ResetPasswordPage />, { route: '/reset-password' })

    expect(screen.getByRole('alert')).toHaveTextContent('missing its token')
    expect(screen.queryByLabelText('New password')).not.toBeInTheDocument()
  })

  it('resets the password and shows a success message', async () => {
    vi.mocked(authApi.confirmPasswordReset).mockResolvedValue(undefined)

    renderWithProviders(<ResetPasswordPage />, { route: '/reset-password?token=abc123' })

    await userEvent.type(screen.getByLabelText('New password'), 'newpassword123')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))

    expect(authApi.confirmPasswordReset).toHaveBeenCalledWith('abc123', 'newpassword123')
    expect(await screen.findByText('Your password has been reset.')).toBeInTheDocument()
  })

  it('shows an inline alert, not just a toast, when the token is invalid or expired', async () => {
    vi.mocked(authApi.confirmPasswordReset).mockRejectedValue(
      new ApiError(400, 'This reset link is invalid or has expired. Request a new one.'),
    )

    renderWithProviders(<ResetPasswordPage />, { route: '/reset-password?token=stale' })

    await userEvent.type(screen.getByLabelText('New password'), 'newpassword123')
    await userEvent.click(screen.getByRole('button', { name: 'Reset password' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'This reset link is invalid or has expired. Request a new one.',
    )
  })
})
