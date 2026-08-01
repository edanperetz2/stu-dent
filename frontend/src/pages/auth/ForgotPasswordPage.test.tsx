import { notifications } from '@mantine/notifications'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { ApiError } from '../../api/httpClient'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { ForgotPasswordPage } from './ForgotPasswordPage'

vi.mock('../../api/auth')

describe('ForgotPasswordPage', () => {
  beforeEach(resetAuthTestState)

  it('shows the same generic confirmation regardless of whether the email has an account', async () => {
    vi.mocked(authApi.requestPasswordReset).mockResolvedValue(undefined)

    renderWithProviders(<ForgotPasswordPage />, { route: '/forgot-password' })

    await userEvent.type(screen.getByLabelText('Email'), 'someone@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }))

    expect(authApi.requestPasswordReset).toHaveBeenCalledWith('someone@example.com')
    expect(
      await screen.findByText(/we've sent a link to reset the password/),
    ).toBeInTheDocument()
  })

  it('toasts an error and stays on the form when the request itself fails (e.g. rate limited)', async () => {
    vi.mocked(authApi.requestPasswordReset).mockRejectedValue(
      new ApiError(429, 'Too many attempts. Try again later.'),
    )
    const showSpy = vi.spyOn(notifications, 'show')

    renderWithProviders(<ForgotPasswordPage />, { route: '/forgot-password' })

    await userEvent.type(screen.getByLabelText('Email'), 'someone@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }))

    await waitFor(() => {
      expect(showSpy).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Too many attempts. Try again later.', color: 'red' }),
      )
    })
    // Stays on the form -- does not show the generic confirmation on a real
    // failure.
    expect(screen.queryByText(/we've sent a link/)).not.toBeInTheDocument()
  })
})
