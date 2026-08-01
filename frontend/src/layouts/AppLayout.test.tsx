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

vi.mock('../api/notifications')
vi.mock('../api/messages')
vi.mock('../api/feedback')
vi.mock('../auth/AuthContext', () => authContextMock(fakePrincipal('attending')))

describe('AppLayout', () => {
  beforeEach(resetAuthTestState)

  it('marks a nav badge as unavailable, not silently zero, when its count request fails', async () => {
    vi.mocked(notificationsApi.getUnreadNotificationCount).mockRejectedValue(
      new Error('network down'),
    )
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

    expect(await screen.findByLabelText('Notifications count unavailable')).toBeInTheDocument()
  })

  it('renders every nav item as a real, focusable link, with the current page marked', async () => {
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

    // Every attending nav item (Appointments, Messages, Notifications,
    // Feedback, Reports) is a real anchor with a real href -- not a
    // clickable <a> missing `to`/`href` that a keyboard user can't reach.
    const appointmentsLink = await screen.findByRole('link', { name: 'Appointments' })
    expect(appointmentsLink).toHaveAttribute('href', '/appointments')
    expect(appointmentsLink).toHaveAttribute('aria-current', 'page')

    const messagesLink = screen.getByRole('link', { name: 'Messages' })
    expect(messagesLink).toHaveAttribute('href', '/messages')
    expect(messagesLink).not.toHaveAttribute('aria-current')

    const reportsLink = screen.getByRole('link', { name: 'Reports' })
    expect(reportsLink).toHaveAttribute('href', '/reports')
  })

  it('renders a skip-to-main-content link as the first focusable element', async () => {
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

    const skipLink = await screen.findByRole('link', { name: 'Skip to main content' })
    expect(skipLink).toHaveAttribute('href', '#main-content')
    expect(document.getElementById('main-content')).toBeInTheDocument()
  })
})
