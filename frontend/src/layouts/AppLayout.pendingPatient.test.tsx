import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import * as feedbackApi from '../api/feedback'
import * as messagesApi from '../api/messages'
import * as notificationsApi from '../api/notifications'
import { authContextMock, fakePrincipal } from '../test/authMocks'
import { renderWithProviders } from '../test/renderWithProviders'
import { resetAuthTestState } from '../test/resetAuthTestState'
import { AppLayout } from './AppLayout'

// A separate file (not a case inside AppLayout.test.tsx) because vi.mock's
// factory is fixed for the whole module -- this suite needs a patient
// principal, the main suite needs an attending one.
vi.mock('../api/notifications')
vi.mock('../api/messages')
vi.mock('../api/feedback')
vi.mock('../auth/AuthContext', () =>
  authContextMock(fakePrincipal('patient', { ownerConfirmedAt: null })),
)

describe('AppLayout (pending patient)', () => {
  beforeEach(resetAuthTestState)

  it('shows a persistent pending-confirmation banner on every page, not just at registration', async () => {
    vi.mocked(notificationsApi.getUnreadNotificationCount).mockResolvedValue({ count: 0 })
    vi.mocked(messagesApi.getUnreadCount).mockResolvedValue({ count: 0 })
    vi.mocked(feedbackApi.listPendingFeedback).mockResolvedValue([])

    renderWithProviders(
      <Routes>
        <Route path="/appointments" element={<AppLayout />}>
          <Route index element={<div>Appointments content</div>} />
        </Route>
      </Routes>,
      { route: '/appointments' },
    )

    const banner = await screen.findByRole('alert')
    expect(banner).toHaveTextContent('pending confirmation from your student')
  })
})
