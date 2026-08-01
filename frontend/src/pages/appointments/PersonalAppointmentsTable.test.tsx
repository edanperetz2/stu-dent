import { render, screen } from '@testing-library/react'
import { MantineProvider } from '@mantine/core'
import dayjs from 'dayjs'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { Appointment } from '../../api/types'
import { PersonalAppointmentsTable } from './PersonalAppointmentsTable'

function appointment(overrides: Partial<Appointment> = {}): Appointment {
  return {
    id: 'appt-1',
    student_id: 'student-1',
    patient_id: 'patient-1',
    attending_id: 'attending-1',
    room_id: 'room-1',
    equipment_id: null,
    start_time: '2026-09-01T09:00:00+00:00',
    end_time: '2026-09-01T09:30:00+00:00',
    status: 'confirmed',
    student_confirmed_at: '2026-08-01T09:00:00+00:00',
    attending_approved_at: null,
    notes: null,
    student_name: 'Demo Student',
    patient_name: 'Demo Patient',
    attending_name: 'Demo Attending',
    room_name: 'Room 1',
    equipment_name: null,
    ...overrides,
  }
}

function renderTable(props: Partial<ComponentProps<typeof PersonalAppointmentsTable>>) {
  return render(
    <MantineProvider>
      <PersonalAppointmentsTable
        appointments={[]}
        attendings={undefined}
        rooms={undefined}
        equipment={undefined}
        expandedId={null}
        onToggleExpand={vi.fn()}
        viewerRole="student"
        groupByDay={false}
        {...props}
      />
    </MantineProvider>,
  )
}

describe('PersonalAppointmentsTable', () => {
  it('drops the viewer\'s own identity from the People column', () => {
    renderTable({ appointments: [appointment()], viewerRole: 'student' })

    expect(screen.queryByText(/Demo Student \(student\)/)).not.toBeInTheDocument()
    expect(screen.getByText(/Demo Patient \(patient\)/)).toBeInTheDocument()
    expect(screen.getByText(/Demo Attending \(attending\)/)).toBeInTheDocument()
  })

  it('shows the patient\'s own identity dropped when viewed as a patient', () => {
    renderTable({ appointments: [appointment()], viewerRole: 'patient' })

    expect(screen.getByText(/Demo Student \(student\)/)).toBeInTheDocument()
    expect(screen.queryByText(/Demo Patient \(patient\)/)).not.toBeInTheDocument()
    expect(screen.getByText(/Demo Attending \(attending\)/)).toBeInTheDocument()
  })

  it('replaces missing attending/room/equipment with a real absence label, never a dash', () => {
    renderTable({
      appointments: [
        appointment({ attending_id: null, attending_name: null, room_id: null, room_name: null }),
      ],
      viewerRole: 'student',
    })

    expect(screen.getByText(/No attending assigned/)).toBeInTheDocument()
    expect(screen.getByText(/No room assigned/)).toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })

  it('collapses start/end into one HH:mm-HH:mm range', () => {
    const appt = appointment()
    renderTable({ appointments: [appt], viewerRole: 'student' })

    const expected = `${dayjs(appt.start_time).format('HH:mm')}–${dayjs(appt.end_time).format('HH:mm')}`
    expect(screen.getByText(expected)).toBeInTheDocument()
  })

  it('groups rows under a day heading only when groupByDay is true', () => {
    // A week apart (not just a day) so the expected day headings can't
    // collide across any real-world timezone offset.
    const appointments = [
      appointment({ id: 'a1', start_time: '2026-09-01T12:00:00+00:00', end_time: '2026-09-01T12:30:00+00:00' }),
      appointment({ id: 'a2', start_time: '2026-09-08T12:00:00+00:00', end_time: '2026-09-08T12:30:00+00:00' }),
    ]
    const firstHeading = dayjs(appointments[0].start_time).format('dddd, DD/MM/YY')
    const secondHeading = dayjs(appointments[1].start_time).format('dddd, DD/MM/YY')

    const { rerender } = render(
      <MantineProvider>
        <PersonalAppointmentsTable
          appointments={appointments}
          attendings={undefined}
          rooms={undefined}
          equipment={undefined}
          expandedId={null}
          onToggleExpand={vi.fn()}
          viewerRole="student"
          groupByDay={true}
        />
      </MantineProvider>,
    )
    expect(screen.getByText(firstHeading)).toBeInTheDocument()
    expect(screen.getByText(secondHeading)).toBeInTheDocument()

    rerender(
      <MantineProvider>
        <PersonalAppointmentsTable
          appointments={appointments}
          attendings={undefined}
          rooms={undefined}
          equipment={undefined}
          expandedId={null}
          onToggleExpand={vi.fn()}
          viewerRole="student"
          groupByDay={false}
        />
      </MantineProvider>,
    )
    expect(screen.queryByText(firstHeading)).not.toBeInTheDocument()
  })
})
