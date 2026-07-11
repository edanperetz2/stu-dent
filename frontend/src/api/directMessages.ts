import { request } from './httpClient'
import type { DirectMessage } from './types'

export function listMessages(token: string, patientId: string) {
  return request<DirectMessage[]>(`/patients/${patientId}/messages`, { token })
}

export function sendMessage(token: string, patientId: string, body: string) {
  return request<DirectMessage>(`/patients/${patientId}/messages`, {
    method: 'POST',
    body: { body },
    token,
  })
}

export function markMessageRead(token: string, patientId: string, messageId: string) {
  return request<DirectMessage>(`/patients/${patientId}/messages/${messageId}/read`, {
    method: 'POST',
    token,
  })
}
