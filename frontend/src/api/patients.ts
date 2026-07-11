import { request } from './httpClient'
import type { PreferredTimeOfDay, User } from './types'

export interface PatientCreateInput {
  full_name: string
  email: string
  password: string
  contact_phone?: string | null
}

export interface PatientUpdateInput {
  full_name?: string
  contact_phone?: string | null
  preferred_time_of_day?: PreferredTimeOfDay | null
}

export function listPatients(token: string) {
  return request<User[]>('/patients', { token })
}

export function getPatient(token: string, patientId: string) {
  return request<User>(`/patients/${patientId}`, { token })
}

export function createPatient(token: string, payload: PatientCreateInput) {
  return request<User>('/patients', { method: 'POST', body: payload, token })
}

export function updatePatient(token: string, patientId: string, payload: PatientUpdateInput) {
  return request<User>(`/patients/${patientId}`, { method: 'PATCH', body: payload, token })
}

export function deletePatient(token: string, patientId: string) {
  return request<void>(`/patients/${patientId}`, { method: 'DELETE', token })
}

export function confirmPatient(token: string, patientId: string) {
  return request<User>(`/patients/${patientId}/confirm`, { method: 'POST', token })
}
