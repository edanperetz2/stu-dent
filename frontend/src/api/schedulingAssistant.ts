import { request } from './httpClient'

export interface InterpretedAppointment {
  patient_id: string | null
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  start_time: string | null
  end_time: string | null
  notes: string | null
  warnings: string[]
}

export function interpretSchedulingRequest(token: string, text: string) {
  return request<InterpretedAppointment>('/scheduling/interpret', {
    method: 'POST',
    body: { text },
    token,
  })
}
