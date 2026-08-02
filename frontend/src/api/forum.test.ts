import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import {
  createComment,
  createPost,
  deleteComment,
  deletePost,
  listComments,
  listPosts,
  removeCommentVote,
  removePostVote,
  updatePost,
  voteComment,
  votePost,
} from './forum'

describe('forum api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listPosts requests GET /forum/posts', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listPosts('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/forum/posts')
  })

  it('createPost requests POST /forum/posts with the payload', async () => {
    const fetchMock = mockFetchOnce(201, {})
    await createPost('tok', { title: 'Title', body: 'Body' })
    const call = lastFetchCall(fetchMock)
    expect(call.method).toBe('POST')
    expect(call.body).toEqual({ title: 'Title', body: 'Body' })
  })

  it('updatePost requests PATCH /forum/posts/:id with the payload', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await updatePost('tok', 'post-1', { title: 'New title' })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/forum/posts/post-1')
    expect(call.method).toBe('PATCH')
  })

  it('deletePost requests DELETE /forum/posts/:id', async () => {
    const fetchMock = mockFetchOnce(204, undefined)
    await deletePost('tok', 'post-1')
    expect(lastFetchCall(fetchMock).method).toBe('DELETE')
  })

  it('listComments requests GET /forum/posts/:id/comments', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listComments('tok', 'post-1')
    expect(lastFetchCall(fetchMock).url).toContain('/forum/posts/post-1/comments')
  })

  it('createComment requests POST /forum/posts/:id/comments with the payload', async () => {
    const fetchMock = mockFetchOnce(201, {})
    await createComment('tok', 'post-1', { body: 'A comment' })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/forum/posts/post-1/comments')
    expect(call.method).toBe('POST')
    expect(call.body).toEqual({ body: 'A comment' })
  })

  it('deleteComment requests DELETE /forum/comments/:id', async () => {
    const fetchMock = mockFetchOnce(204, undefined)
    await deleteComment('tok', 'comment-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/forum/comments/comment-1')
    expect(call.method).toBe('DELETE')
  })

  it('votePost requests PUT /forum/posts/:id/vote with the value', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await votePost('tok', 'post-1', 1)
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/forum/posts/post-1/vote')
    expect(call.method).toBe('PUT')
    expect(call.body).toEqual({ value: 1 })
  })

  it('removePostVote requests DELETE /forum/posts/:id/vote', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await removePostVote('tok', 'post-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/forum/posts/post-1/vote')
    expect(call.method).toBe('DELETE')
  })

  it('voteComment requests PUT /forum/comments/:id/vote with the value', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await voteComment('tok', 'comment-1', -1)
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/forum/comments/comment-1/vote')
    expect(call.method).toBe('PUT')
    expect(call.body).toEqual({ value: -1 })
  })

  it('removeCommentVote requests DELETE /forum/comments/:id/vote', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await removeCommentVote('tok', 'comment-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/forum/comments/comment-1/vote')
    expect(call.method).toBe('DELETE')
  })
})
