import { request } from './httpClient'
import type { AvailabilityWindow } from './types'

export interface AvailabilityWindowInput {
  day_of_week: number
  start_time: string
  end_time: string
}

export function getMyAvailability(token: string) {
  return request<AvailabilityWindow[]>('/students/me/availability', { token })
}

export function replaceMyAvailability(token: string, windows: AvailabilityWindowInput[]) {
  return request<AvailabilityWindow[]>('/students/me/availability', {
    method: 'PUT',
    body: windows,
    token,
  })
}
