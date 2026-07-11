import { request } from './httpClient'
import type { ForumComment, ForumPost } from './types'

export interface ForumPostCreateInput {
  title: string
  body: string
}

export interface ForumPostUpdateInput {
  title?: string
  body?: string
}

export interface ForumCommentCreateInput {
  body: string
}

export function listPosts(token: string) {
  return request<ForumPost[]>('/forum/posts', { token })
}

export function getPost(token: string, postId: string) {
  return request<ForumPost>(`/forum/posts/${postId}`, { token })
}

export function createPost(token: string, payload: ForumPostCreateInput) {
  return request<ForumPost>('/forum/posts', { method: 'POST', body: payload, token })
}

export function updatePost(token: string, postId: string, payload: ForumPostUpdateInput) {
  return request<ForumPost>(`/forum/posts/${postId}`, { method: 'PATCH', body: payload, token })
}

export function deletePost(token: string, postId: string) {
  return request<void>(`/forum/posts/${postId}`, { method: 'DELETE', token })
}

export function listComments(token: string, postId: string) {
  return request<ForumComment[]>(`/forum/posts/${postId}/comments`, { token })
}

export function createComment(token: string, postId: string, payload: ForumCommentCreateInput) {
  return request<ForumComment>(`/forum/posts/${postId}/comments`, {
    method: 'POST',
    body: payload,
    token,
  })
}

export function deleteComment(token: string, commentId: string) {
  return request<void>(`/forum/comments/${commentId}`, { method: 'DELETE', token })
}

export function votePost(token: string, postId: string, value: 1 | -1) {
  return request<ForumPost>(`/forum/posts/${postId}/vote`, {
    method: 'PUT',
    body: { value },
    token,
  })
}

export function removePostVote(token: string, postId: string) {
  return request<ForumPost>(`/forum/posts/${postId}/vote`, { method: 'DELETE', token })
}

export function voteComment(token: string, commentId: string, value: 1 | -1) {
  return request<ForumComment>(`/forum/comments/${commentId}/vote`, {
    method: 'PUT',
    body: { value },
    token,
  })
}

export function removeCommentVote(token: string, commentId: string) {
  return request<ForumComment>(`/forum/comments/${commentId}/vote`, {
    method: 'DELETE',
    token,
  })
}
