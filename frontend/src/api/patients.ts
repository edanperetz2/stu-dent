import { request } from './httpClient'
import type { Patient, PreferredTimeOfDay } from './types'

export interface PatientCreateInput {
  full_name: string
  contact_phone?: string | null
}

export interface PatientUpdateInput {
  full_name?: string
  contact_phone?: string | null
  preferred_time_of_day?: PreferredTimeOfDay | null
}

export function listPatients(token: string) {
  return request<Patient[]>('/patients', { token })
}

export function getPatient(token: string, patientId: string) {
  return request<Patient>(`/patients/${patientId}`, { token })
}

export function createPatient(token: string, payload: PatientCreateInput) {
  return request<Patient>('/patients', { method: 'POST', body: payload, token })
}

export function updatePatient(token: string, patientId: string, payload: PatientUpdateInput) {
  return request<Patient>(`/patients/${patientId}`, { method: 'PATCH', body: payload, token })
}

export function deletePatient(token: string, patientId: string) {
  return request<void>(`/patients/${patientId}`, { method: 'DELETE', token })
}

export function setPatientCredentials(
  token: string,
  patientId: string,
  email: string,
  password: string,
) {
  return request<Patient>(`/patients/${patientId}/credentials`, {
    method: 'POST',
    body: { email, password },
    token,
  })
}
