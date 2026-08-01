import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as forumApi from '../../api/forum'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { ForumListPage } from './ForumListPage'

vi.mock('../../api/forum')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

describe('ForumListPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not the empty state, when the posts request fails', async () => {
    vi.mocked(forumApi.listPosts).mockRejectedValue(new Error('network down'))

    renderWithProviders(<ForumListPage />, { route: '/forum' })

    expect(await screen.findByText('Failed to load the forum.')).toBeInTheDocument()
    expect(screen.queryByText(/No posts yet/)).not.toBeInTheDocument()
  })
})
