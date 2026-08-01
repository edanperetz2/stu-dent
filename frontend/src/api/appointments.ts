import { request } from './httpClient'
import type { Appointment } from './types'

export interface AppointmentCreateInput {
  patient_id?: string
  attending_id?: string
  room_id?: string
  equipment_id?: string
  start_time: string
  end_time: string
  notes?: string
}

export interface AppointmentUpdateInput {
  start_time?: string
  end_time?: string
  attending_id?: string | null
  room_id?: string | null
  equipment_id?: string | null
  notes?: string | null
}

export interface ListAppointmentsOptions {
  /** ISO 8601 strings -- start_time >= startAfter and < startBefore. */
  startAfter?: string
  startBefore?: string
  excludeCancelled?: boolean
  limit?: number
  offset?: number
}

export function listAppointments(token: string, options: ListAppointmentsOptions = {}) {
  return request<Appointment[]>('/appointments', {
    token,
    query: {
      start_after: options.startAfter,
      start_before: options.startBefore,
      exclude_cancelled: options.excludeCancelled,
      limit: options.limit,
      offset: options.offset,
    },
  })
}

export function getAppointment(token: string, appointmentId: string) {
  return request<Appointment>(`/appointments/${appointmentId}`, { token })
}

export function createAppointment(token: string, payload: AppointmentCreateInput) {
  return request<Appointment>('/appointments', { method: 'POST', body: payload, token })
}

export function updateAppointment(
  token: string,
  appointmentId: string,
  payload: AppointmentUpdateInput,
) {
  return request<Appointment>(`/appointments/${appointmentId}`, {
    method: 'PATCH',
    body: payload,
    token,
  })
}

function appointmentAction(actionName: string) {
  return (token: string, appointmentId: string) =>
    request<Appointment>(`/appointments/${appointmentId}/${actionName}`, {
      method: 'POST',
      token,
    })
}

// A patient-initiated request starts room-less; the owning student supplies
// one here if the appointment doesn't already have one -- see backend
// AppointmentAccept.
export function acceptAppointment(token: string, appointmentId: string, roomId?: string) {
  return request<Appointment>(`/appointments/${appointmentId}/accept`, {
    method: 'POST',
    body: roomId ? { room_id: roomId } : undefined,
    token,
  })
}

export const approveAppointment = appointmentAction('approve')
export const rejectAppointment = appointmentAction('reject')
export const cancelAppointment = appointmentAction('cancel')
export const completeAppointment = appointmentAction('complete')
export const markNoShow = appointmentAction('no-show')
