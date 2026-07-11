import { request } from './httpClient'
import type { Patient, Role, TokenResponse, User } from './types'

export function registerUser(email: string, password: string, fullName: string, role: Role) {
  return request<User>('/auth/register', {
    method: 'POST',
    body: { email, password, full_name: fullName, role },
  })
}

export function login(email: string, password: string) {
  return request<TokenResponse>('/auth/login', { method: 'POST', body: { email, password } })
}

export function patientLogin(email: string, password: string) {
  return request<TokenResponse>('/patients/login', { method: 'POST', body: { email, password } })
}

export function getCurrentUser(token: string) {
  return request<User>('/users/me', { token })
}

export function getCurrentPatient(token: string) {
  return request<Patient>('/patients/me', { token })
}
