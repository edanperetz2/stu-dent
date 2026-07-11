import { request } from './httpClient'
import type { Role, User } from './types'

export interface AdminUserUpdateInput {
  is_active?: boolean
  role?: Role
}

export function listAllUsers(token: string) {
  return request<User[]>('/admin/users', { token })
}

export function getUser(token: string, userId: string) {
  return request<User>(`/admin/users/${userId}`, { token })
}

export function updateUser(token: string, userId: string, payload: AdminUserUpdateInput) {
  return request<User>(`/admin/users/${userId}`, { method: 'PATCH', body: payload, token })
}

export function deleteUser(token: string, userId: string) {
  return request<void>(`/admin/users/${userId}`, { method: 'DELETE', token })
}
