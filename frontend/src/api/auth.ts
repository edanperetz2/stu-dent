import { request } from './httpClient'
import type { Role, TokenResponse, User } from './types'

export function registerUser(
  email: string,
  password: string,
  fullName: string,
  role: Role,
  ownerStudentId?: string,
) {
  return request<User>('/auth/register', {
    method: 'POST',
    body: {
      email,
      password,
      full_name: fullName,
      role,
      ...(ownerStudentId ? { owner_student_id: ownerStudentId } : {}),
    },
  })
}

export function login(email: string, password: string, role?: Role) {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password, ...(role ? { role } : {}) },
  })
}

export function getCurrentUser(token: string) {
  return request<User>('/users/me', { token })
}
