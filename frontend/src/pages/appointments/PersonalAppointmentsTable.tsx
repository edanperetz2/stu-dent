import { Badge, Box, Collapse, Table, Text, useComputedColorScheme } from '@mantine/core'
import dayjs from 'dayjs'
import { Fragment } from 'react'
import type { Appointment, Equipment, Role, Room, User } from '../../api/types'
import { ClickableRow } from '../../components/ClickableRow'
import { AppointmentDetailPanel } from './AppointmentDetailPanel'
import { statusBadgeStyle, statusLabel } from './appointmentActions'

interface PersonalAppointmentsTableProps {
  appointments: Appointment[]
  attendings: User[] | undefined
  rooms: Room[] | undefined
  equipment: Equipment[] | undefined
  expandedId: string | null
  onToggleExpand: (appointmentId: string) => void
  /** Whichever of Student/Patient/Attending is the *viewer's own* identity
   * gets dropped from the People column below -- every row in this table
   * is already known to be "an appointment involving me", so repeating the
   * viewer's own name on every row added nothing. Admin never renders this
   * table (always the Resources lens), so it falls through to showing all
   * three, but that combination can't actually occur. */
  viewerRole: Role
  /** Only the default chronological sort (start_time) groups rows under a
   * day heading -- grouping while sorted by status/patient/student would
   * scatter the same day's rows non-contiguously across the table, which
   * reads as broken rather than organized. */
  groupByDay: boolean
}

function personLabel(name: string | null | undefined, role: string): string {
  return name ? `${name} (${role})` : `No ${role} assigned`
}

/** The viewer's own appointments -- one row per appointment, grouped by day
 * when chronologically sorted. Split out of AppointmentsListPage alongside
 * ResourceAppointmentsTable and AppointmentsCalendarView, its two siblings
 * for the other two view modes. Cut from the original 8 columns (Start,
 * End, Status, Student, Patient, Attending, Room, Equipment) to 4 -- Time,
 * Status, People, Where -- per the frontend review's table-redesign
 * proposal. */
export function PersonalAppointmentsTable({
  appointments,
  attendings,
  rooms,
  equipment,
  expandedId,
  onToggleExpand,
  viewerRole,
  groupByDay,
}: PersonalAppointmentsTableProps) {
  const colorScheme = useComputedColorScheme('light')
  let previousDayKey: string | null = null

  return (
    <Table.ScrollContainer minWidth={640}>
      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Time</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>People</Table.Th>
            <Table.Th>Where</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {appointments.map((appointment, index) => {
            const expanded = expandedId === appointment.id
            const dayKey = dayjs(appointment.start_time).format('YYYY-MM-DD')
            const isNewDay = groupByDay && dayKey !== previousDayKey
            const isFirstRow = index === 0
            previousDayKey = dayKey

            const people = [
              viewerRole !== 'student' && {
                role: 'student',
                label: personLabel(appointment.student_name, 'student'),
              },
              viewerRole !== 'patient' && {
                role: 'patient',
                label: personLabel(appointment.patient_name, 'patient'),
              },
              viewerRole !== 'attending' && {
                role: 'attending',
                label: personLabel(appointment.attending_name, 'attending'),
              },
            ].filter((entry): entry is { role: string; label: string } => !!entry)

            const where = [
              appointment.room_name ?? 'No room assigned',
              appointment.equipment_name ?? 'No equipment assigned',
            ].join(', ')

            return (
              <Fragment key={appointment.id}>
                {isNewDay && (
                  <Table.Tr>
                    <Table.Td colSpan={5} pt={isFirstRow ? 4 : 'md'} pb={4}>
                      <Text size="xs" fw={700} c="dimmed" tt="uppercase">
                        {dayjs(appointment.start_time).format('dddd, DD/MM/YY')}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                )}
                <ClickableRow
                  onToggle={() => onToggleExpand(appointment.id)}
                  expanded={expanded}
                  expandLabel={`Toggle details for the appointment at ${dayjs(appointment.start_time).format('HH:mm')}`}
                >
                  <Table.Td>
                    {dayjs(appointment.start_time).format('HH:mm')}–
                    {dayjs(appointment.end_time).format('HH:mm')}
                  </Table.Td>
                  <Table.Td>
                    <Badge style={statusBadgeStyle(appointment.status, colorScheme)}>
                      {statusLabel(appointment.status)}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {people.map((entry) => entry.label).join(', ')}
                  </Table.Td>
                  <Table.Td>{where}</Table.Td>
                </ClickableRow>
                <Table.Tr>
                  <Table.Td colSpan={5} p={0}>
                    <Collapse expanded={expanded} keepMounted={false}>
                      <Box p="md">
                        <AppointmentDetailPanel
                          appointment={appointment}
                          attendings={attendings}
                          rooms={rooms}
                          equipment={equipment}
                        />
                      </Box>
                    </Collapse>
                  </Table.Td>
                </Table.Tr>
              </Fragment>
            )
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}
