import { MantineProvider } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { Appointment } from '../../api/types'
import { ResourceAppointmentsTable } from './ResourceAppointmentsTable'
import type { CalendarEventItem } from './resourceColors'

const APPOINTMENT: Appointment = {
  id: 'appt-1',
  student_id: 'student-1',
  patient_id: 'patient-1',
  attending_id: null,
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
  attending_name: null,
  room_name: 'Room 1',
  equipment_name: null,
}

function adminEvent(): CalendarEventItem {
  return {
    id: APPOINTMENT.id,
    title: 'Demo Patient · Confirmed',
    start: new Date(APPOINTMENT.start_time),
    end: new Date(APPOINTMENT.end_time),
    resourceId: 'room:room-1',
    resourceName: 'Room 1',
    resourceKind: 'room',
    resource: APPOINTMENT,
    studentName: APPOINTMENT.student_name,
  }
}

function nonAdminEvent(): CalendarEventItem {
  return {
    id: 'resource-busy-0',
    title: '',
    start: new Date(APPOINTMENT.start_time),
    end: new Date(APPOINTMENT.end_time),
    resourceId: 'room:room-1',
    resourceName: 'Room 1',
    resourceKind: 'room',
    resource: null,
    studentName: 'Demo Student',
  }
}

describe('ResourceAppointmentsTable', () => {
  it('shows full detail columns and an expandable row for admin', async () => {
    const user = userEvent.setup()
    render(
      <MantineProvider>
        <ResourceAppointmentsTable
          events={[adminEvent()]}
          isAdmin
          attendings={undefined}
          rooms={undefined}
          equipment={undefined}
          expandedId={null}
          onToggleExpand={vi.fn()}
        />
      </MantineProvider>,
    )

    expect(screen.getByText('Demo Student')).toBeInTheDocument()
    expect(screen.getByText('Demo Patient')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Status' })).toBeInTheDocument()

    const toggle = screen.getByRole('button', { name: /Toggle details/i })
    expect(toggle).toBeInTheDocument()
    await user.click(toggle)
  })

  it('shows only "Booked by" and no expand control for a non-admin viewer', () => {
    render(
      <MantineProvider>
        <ResourceAppointmentsTable
          events={[nonAdminEvent()]}
          isAdmin={false}
          attendings={undefined}
          rooms={undefined}
          equipment={undefined}
          expandedId={null}
          onToggleExpand={vi.fn()}
        />
      </MantineProvider>,
    )

    expect(screen.getByRole('columnheader', { name: 'Booked by' })).toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: 'Status' })).not.toBeInTheDocument()
    expect(screen.getByText('Demo Student')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Toggle details/i })).not.toBeInTheDocument()
  })

  it('calls onToggleExpand with the composite resourceId-eventId key', async () => {
    const user = userEvent.setup()
    const onToggleExpand = vi.fn()
    render(
      <MantineProvider>
        <ResourceAppointmentsTable
          events={[adminEvent()]}
          isAdmin
          attendings={undefined}
          rooms={undefined}
          equipment={undefined}
          expandedId={null}
          onToggleExpand={onToggleExpand}
        />
      </MantineProvider>,
    )

    await user.click(screen.getByRole('button', { name: /Toggle details/i }))
    expect(onToggleExpand).toHaveBeenCalledWith('room:room-1-appt-1')
  })
})
