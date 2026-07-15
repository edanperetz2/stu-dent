import type { Appointment, AppointmentStatus } from '../../api/types'
import type { Principal } from '../../auth/AuthContext'

export type AppointmentActionName = 'accept' | 'approve' | 'reject' | 'cancel' | 'complete' | 'no_show'

export interface AppointmentAction {
  name: AppointmentActionName
  label: string
  color: string
}

const TERMINAL_STATUSES: AppointmentStatus[] = ['cancelled', 'completed', 'no_show']

/**
 * Mirrors the authorization + status rules in
 * backend/app/api/routes/appointments.py exactly, so the UI never offers an
 * action the API would reject. Kept as a pure function (no rendering) so
 * it's directly unit-testable without mounting the page.
 */
export function getAvailableActions(
  appointment: Appointment,
  principal: Principal,
  now: Date = new Date(),
): AppointmentAction[] {
  const actions: AppointmentAction[] = []

  const isOwningStudent =
    principal.role === 'student' && appointment.student_id === principal.id
  const isAssignedAttending =
    principal.role === 'attending' && appointment.attending_id === principal.id
  const isSelfPatient = principal.role === 'patient' && appointment.patient_id === principal.id

  const isTerminal = TERMINAL_STATUSES.includes(appointment.status)

  if (isOwningStudent && appointment.status === 'proposed') {
    actions.push({ name: 'accept', label: 'Accept', color: 'green' })
  }

  if (
    isAssignedAttending &&
    (appointment.status === 'awaiting_confirmation' || appointment.status === 'rescheduling_requested')
  ) {
    actions.push({ name: 'approve', label: 'Approve', color: 'green' })
  }

  if (isAssignedAttending && !isTerminal) {
    actions.push({ name: 'reject', label: 'Reject', color: 'red' })
  }

  if ((isOwningStudent || isSelfPatient) && !isTerminal) {
    actions.push({ name: 'cancel', label: 'Cancel', color: 'red' })
  }

  if (
    isOwningStudent &&
    appointment.status === 'confirmed' &&
    now >= new Date(appointment.start_time)
  ) {
    actions.push({ name: 'complete', label: 'Complete', color: 'blue' })
    actions.push({ name: 'no_show', label: 'Mark No-Show', color: 'orange' })
  }

  return actions
}
