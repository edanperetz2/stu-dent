import type { AppointmentCreateInput } from './appointments'
import { request } from './httpClient'
import type { WaitlistEntry } from './types'

export function listWaitlistEntries(token: string) {
  return request<WaitlistEntry[]>('/waitlist', { token })
}

export function getWaitlistEntry(token: string, entryId: string) {
  return request<WaitlistEntry>(`/waitlist/${entryId}`, { token })
}

// Same request shape as creating an appointment -- the backend
// independently re-derives the conflict cause rather than trusting
// whatever the caller claims, so this is never a speculative "I'd like a
// slot sometime" entry, only ever a real attempted request that failed.
export function joinWaitlist(token: string, payload: AppointmentCreateInput) {
  return request<WaitlistEntry>('/waitlist', { method: 'POST', body: payload, token })
}

export function cancelWaitlistEntry(token: string, entryId: string) {
  return request<WaitlistEntry>(`/waitlist/${entryId}/cancel`, { method: 'POST', token })
}
