import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as notificationsApi from '../../api/notifications'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { NotificationsPage } from './NotificationsPage'

vi.mock('../../api/notifications')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

describe('NotificationsPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not the empty state, when the notifications request fails', async () => {
    vi.mocked(notificationsApi.listNotifications).mockRejectedValue(new Error('network down'))

    renderWithProviders(<NotificationsPage />, { route: '/notifications' })

    expect(await screen.findByText('Failed to load notifications.')).toBeInTheDocument()
    expect(screen.queryByText(/No notifications/)).not.toBeInTheDocument()
  })
})
