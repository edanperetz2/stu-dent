import { request } from './httpClient'
import type { PreferredTimeOfDay, Role, TokenResponse, User } from './types'

export interface UserSelfUpdateInput {
  contact_phone?: string | null
  preferred_time_of_day?: PreferredTimeOfDay | null
}

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

export function updateCurrentUser(token: string, payload: UserSelfUpdateInput) {
  return request<User>('/users/me', { method: 'PATCH', body: payload, token })
}

// Both endpoints return 204 with no body -- the backend deliberately gives
// no signal either way on `requestPasswordReset` (whether the email
// matched a real account), so there's nothing meaningful to type as a
// response beyond "the request didn't throw".
export function requestPasswordReset(email: string) {
  return request<void>('/auth/password-reset/request', { method: 'POST', body: { email } })
}

export function confirmPasswordReset(token: string, newPassword: string) {
  return request<void>('/auth/password-reset/confirm', {
    method: 'POST',
    body: { token, new_password: newPassword },
  })
}
