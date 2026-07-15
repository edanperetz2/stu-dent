import { describe, expect, it } from 'vitest'
import type { Appointment, AppointmentStatus } from '../../api/types'
import type { Principal } from '../../auth/AuthContext'
import { getAvailableActions } from './appointmentActions'

const STUDENT_ID = 'student-1'
const ATTENDING_ID = 'attending-1'
const PATIENT_ID = 'patient-1'

function makeAppointment(overrides: Partial<Appointment> = {}): Appointment {
  return {
    id: 'appt-1',
    student_id: STUDENT_ID,
    patient_id: PATIENT_ID,
    attending_id: ATTENDING_ID,
    room_id: null,
    equipment_id: null,
    start_time: '2026-01-01T09:00:00Z',
    end_time: '2026-01-01T10:00:00Z',
    status: 'proposed',
    student_confirmed_at: null,
    attending_approved_at: null,
    notes: null,
    student_name: 'Student',
    patient_name: 'Patient',
    attending_name: 'Attending',
    room_name: null,
    equipment_name: null,
    ...overrides,
  }
}

const owningStudent: Principal = {
  token: 't',
  id: STUDENT_ID,
  role: 'student',
  fullName: 'Student',
  email: 's@example.com',
  ownerStudentId: null,
  ownerStudentName: null,
  ownerConfirmedAt: null,
}
const otherStudent: Principal = { ...owningStudent, id: 'other-student' }
const assignedAttending: Principal = {
  token: 't',
  id: ATTENDING_ID,
  role: 'attending',
  fullName: 'Attending',
  email: 'a@example.com',
  ownerStudentId: null,
  ownerStudentName: null,
  ownerConfirmedAt: null,
}
const otherAttending: Principal = { ...assignedAttending, id: 'other-attending' }
const admin: Principal = {
  token: 't',
  id: 'admin-1',
  role: 'admin',
  fullName: 'Admin',
  email: 'admin@example.com',
  ownerStudentId: null,
  ownerStudentName: null,
  ownerConfirmedAt: null,
}
const selfPatient: Principal = {
  token: 't',
  id: PATIENT_ID,
  role: 'patient',
  fullName: 'Patient',
  email: 'p@example.com',
  ownerStudentId: STUDENT_ID,
  ownerStudentName: 'Student',
  ownerConfirmedAt: '2026-01-01T00:00:00Z',
}
const otherPatient: Principal = { ...selfPatient, id: 'other-patient' }

function names(appointment: Appointment, principal: Principal, now?: Date): string[] {
  return getAvailableActions(appointment, principal, now).map((a) => a.name)
}

describe('getAvailableActions', () => {
  it('offers accept and cancel to the owning student on a proposed appointment', () => {
    const actions = names(makeAppointment({ status: 'proposed' }), owningStudent)
    expect(actions).toContain('accept')
    expect(actions).toContain('cancel')
    expect(actions).not.toContain('approve')
    expect(actions).not.toContain('complete')
  })

  it('offers nothing to an unrelated student', () => {
    expect(names(makeAppointment({ status: 'proposed' }), otherStudent)).toEqual([])
  })

  it('lets the assigned attending approve an awaiting_confirmation appointment', () => {
    const actions = names(makeAppointment({ status: 'awaiting_confirmation' }), assignedAttending)
    expect(actions).toContain('approve')
    expect(actions).toContain('reject')
    expect(actions).not.toContain('cancel')
  })

  it('lets the assigned attending approve a rescheduling_requested appointment', () => {
    expect(
      names(makeAppointment({ status: 'rescheduling_requested' }), assignedAttending),
    ).toContain('approve')
  })

  it('does not offer approve to an unrelated attending', () => {
    expect(names(makeAppointment({ status: 'awaiting_confirmation' }), otherAttending)).toEqual([])
  })

  it('does not offer approve once confirmed', () => {
    const actions = names(makeAppointment({ status: 'confirmed' }), assignedAttending)
    expect(actions).not.toContain('approve')
    expect(actions).toContain('reject')
  })

  it('offers complete and no_show only to the owning student on a confirmed, already-started appointment', () => {
    const afterStart = new Date('2026-01-01T10:00:00Z')
    const studentActions = names(makeAppointment({ status: 'confirmed' }), owningStudent, afterStart)
    expect(studentActions).toContain('complete')
    expect(studentActions).toContain('no_show')
    expect(studentActions).toContain('cancel')
    expect(studentActions).not.toContain('accept')

    const attendingActions = names(makeAppointment({ status: 'confirmed' }), assignedAttending, afterStart)
    expect(attendingActions).not.toContain('complete')
    expect(attendingActions).not.toContain('no_show')
  })

  it('does not offer complete/no_show before the appointment has started, but keeps cancel available', () => {
    const beforeStart = new Date('2026-01-01T08:00:00Z')
    const actions = names(makeAppointment({ status: 'confirmed' }), owningStudent, beforeStart)
    expect(actions).not.toContain('complete')
    expect(actions).not.toContain('no_show')
    expect(actions).toContain('cancel')
  })

  it('offers complete/no_show exactly at the start time', () => {
    const atStart = new Date('2026-01-01T09:00:00Z')
    const actions = names(makeAppointment({ status: 'confirmed' }), owningStudent, atStart)
    expect(actions).toContain('complete')
    expect(actions).toContain('no_show')
  })

  it('keeps cancel available on a past (already-started) confirmed appointment', () => {
    const wellAfterStart = new Date('2026-06-01T00:00:00Z')
    const actions = names(makeAppointment({ status: 'confirmed' }), owningStudent, wellAfterStart)
    expect(actions).toContain('cancel')
  })

  it('lets the self patient cancel their own non-terminal appointment', () => {
    expect(names(makeAppointment({ status: 'proposed' }), selfPatient)).toEqual(['cancel'])
  })

  it('offers nothing to an unrelated patient', () => {
    expect(names(makeAppointment({ status: 'proposed' }), otherPatient)).toEqual([])
  })

  it('offers nothing at all on terminal statuses', () => {
    for (const status of ['cancelled', 'completed', 'no_show'] as AppointmentStatus[]) {
      expect(names(makeAppointment({ status }), owningStudent)).toEqual([])
      expect(names(makeAppointment({ status }), assignedAttending)).toEqual([])
      expect(names(makeAppointment({ status }), selfPatient)).toEqual([])
    }
  })

  it('offers admin no actions at all (view-only)', () => {
    expect(names(makeAppointment({ status: 'proposed' }), admin)).toEqual([])
    expect(names(makeAppointment({ status: 'confirmed' }), admin)).toEqual([])
  })

  it('does not offer approve/reject when no attending is assigned', () => {
    const noAttending = makeAppointment({ status: 'confirmed', attending_id: null })
    expect(names(noAttending, assignedAttending)).toEqual([])
  })
})
