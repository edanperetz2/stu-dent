import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as forumApi from '../../api/forum'
import type { ForumPost } from '../../api/types'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { ForumPostCard } from './ForumPostCard'

vi.mock('../../api/forum')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

const POST: ForumPost = {
  id: 'post-1',
  author_student_id: 'author-1',
  title: 'A post',
  body: 'Post body',
  likes: 0,
  dislikes: 0,
  comment_count: 2,
  my_vote: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('ForumPostCard', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not just loading, when the comments request fails while expanded', async () => {
    vi.mocked(forumApi.listComments).mockRejectedValue(new Error('network down'))

    renderWithProviders(
      <ForumPostCard post={POST} expanded onToggleExpand={() => {}} />,
      { route: '/forum' },
    )

    expect(await screen.findByText('Failed to load replies.')).toBeInTheDocument()
  })
})
