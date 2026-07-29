import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as appointmentsApi from '../../api/appointments'
import { ApiError } from '../../api/httpClient'
import type { Appointment } from '../../api/types'
import * as waitlistApi from '../../api/waitlist'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { renderWithProviders } from '../../test/renderWithProviders'
import { AppointmentDetailPanel } from './AppointmentDetailPanel'

vi.mock('../../api/appointments')
vi.mock('../../api/waitlist')

const STUDENT_PRINCIPAL = {
  token: 'tok-student-1',
  id: 'student-1',
  role: 'student' as const,
  fullName: 'Test Student',
  email: 'student@example.com',
  ownerStudentId: null,
  ownerStudentName: null,
  ownerConfirmedAt: null,
}

vi.mock('../../auth/AuthContext', () => ({
  useAuth: () => ({
    principal: STUDENT_PRINCIPAL,
    isLoading: false,
    login: vi.fn(),
    registerUser: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: ReactNode }) => children,
}))

const APPOINTMENT: Appointment = {
  id: 'appt-1',
  student_id: STUDENT_PRINCIPAL.id,
  patient_id: 'patient-1',
  attending_id: null,
  room_id: 'room-1',
  equipment_id: null,
  start_time: '2026-09-01T09:00:00+00:00',
  end_time: '2026-09-01T10:00:00+00:00',
  status: 'confirmed',
  student_confirmed_at: '2026-08-01T09:00:00+00:00',
  attending_approved_at: null,
  notes: null,
  student_name: 'Test Student',
  patient_name: 'Test Patient',
  attending_name: null,
  room_name: 'Room 1',
  equipment_name: null,
}

const CONFLICTS = [{ resource_type: 'room' as const, resource_id: 'room-2', resource_name: 'Room 2' }]

describe('AppointmentDetailPanel', () => {
  beforeEach(resetAuthTestState)

  it('editing into a conflict, then choosing "Cancel & join waitlist", joins the waitlist and cancels the original appointment', async () => {
    const user = userEvent.setup()

    vi.mocked(appointmentsApi.updateAppointment).mockRejectedValue(
      new ApiError(409, 'Requested change conflicts with an existing booking', CONFLICTS),
    )
    vi.mocked(waitlistApi.joinWaitlist).mockResolvedValue({
      id: 'wl-1',
      student_id: STUDENT_PRINCIPAL.id,
      patient_id: APPOINTMENT.patient_id,
      attending_id: null,
      room_id: APPOINTMENT.room_id,
      equipment_id: null,
      start_time: APPOINTMENT.start_time,
      end_time: APPOINTMENT.end_time,
      notes: null,
      status: 'active',
      resolved_at: null,
      resulting_appointment_id: null,
      resulting_appointment_status: null,
      conflicts: CONFLICTS,
      student_name: APPOINTMENT.student_name,
      patient_name: APPOINTMENT.patient_name,
      attending_name: null,
      room_name: APPOINTMENT.room_name,
      equipment_name: null,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any)
    vi.mocked(appointmentsApi.cancelAppointment).mockResolvedValue({
      ...APPOINTMENT,
      status: 'cancelled',
    })

    renderWithProviders(<AppointmentDetailPanel appointment={APPOINTMENT} />)

    await user.click(screen.getByRole('button', { name: 'Edit' }))
    await user.click(await screen.findByRole('button', { name: 'Save' }))

    expect(await screen.findByText(/This request isn't available/i)).toBeInTheDocument()

    await user.click(await screen.findByRole('button', { name: 'Cancel & join waitlist' }))

    await waitFor(() => expect(waitlistApi.joinWaitlist).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(appointmentsApi.cancelAppointment).toHaveBeenCalledTimes(1))

    // The cancel must only happen after the waitlist join actually
    // succeeded, never the other way around or in parallel.
    const joinOrder = vi.mocked(waitlistApi.joinWaitlist).mock.invocationCallOrder[0]
    const cancelOrder = vi.mocked(appointmentsApi.cancelAppointment).mock.invocationCallOrder[0]
    expect(joinOrder).toBeLessThan(cancelOrder)

    expect(appointmentsApi.cancelAppointment).toHaveBeenCalledWith(
      STUDENT_PRINCIPAL.token,
      APPOINTMENT.id,
    )
  })
})
