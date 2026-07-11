import { request } from './httpClient'
import type { WaitlistEntry } from './types'

export interface WaitlistEntryCreateInput {
  patient_id?: string
  attending_id?: string
  room_id?: string
  equipment_id?: string
  start_time: string
  end_time: string
}

export function listWaitlistEntries(token: string) {
  return request<WaitlistEntry[]>('/waitlist', { token })
}

export function getWaitlistEntry(token: string, entryId: string) {
  return request<WaitlistEntry>(`/waitlist/${entryId}`, { token })
}

export function createWaitlistEntry(token: string, payload: WaitlistEntryCreateInput) {
  return request<WaitlistEntry>('/waitlist', { method: 'POST', body: payload, token })
}

export function cancelWaitlistEntry(token: string, entryId: string) {
  return request<WaitlistEntry>(`/waitlist/${entryId}/cancel`, { method: 'POST', token })
}
