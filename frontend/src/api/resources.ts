import { request } from './httpClient'
import type { ResourceBooking } from './types'

// Combined room+equipment busy windows across every user's bookings --
// reveals which student booked each slot, never the patient. Any
// authenticated role can call this.
export function getResourcesSchedule(token: string) {
  return request<ResourceBooking[]>('/resources/schedule', { token })
}
