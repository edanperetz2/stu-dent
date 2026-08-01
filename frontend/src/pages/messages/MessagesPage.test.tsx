import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as messagesApi from '../../api/messages'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { MessagesPage } from './MessagesPage'

// Partial mock -- `targetKey` is a plain pure function this page calls
// directly while rendering (not a network call), so it must keep its real
// implementation; only the network-backed functions are replaced.
vi.mock('../../api/messages', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/messages')>()
  return { ...actual, listContacts: vi.fn(), listGroups: vi.fn(), getThreadSummaries: vi.fn() }
})
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

describe('MessagesPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not the empty state, when the contacts request fails', async () => {
    vi.mocked(messagesApi.listContacts).mockRejectedValue(new Error('network down'))
    vi.mocked(messagesApi.listGroups).mockResolvedValue([])
    vi.mocked(messagesApi.getThreadSummaries).mockResolvedValue([])

    renderWithProviders(<MessagesPage />, { route: '/messages' })

    expect(await screen.findByText('Failed to load contacts.')).toBeInTheDocument()
    expect(screen.queryByText('No contacts yet.')).not.toBeInTheDocument()
  })
})
