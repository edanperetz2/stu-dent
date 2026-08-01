import { Badge, Box, Collapse, Table, useComputedColorScheme } from '@mantine/core'
import { Fragment } from 'react'
import type { Equipment, Room, User } from '../../api/types'
import { ClickableRow } from '../../components/ClickableRow'
import { formatDateTime } from '../../utils/dates'
import { AppointmentDetailPanel } from './AppointmentDetailPanel'
import { statusBadgeStyle, statusLabel } from './appointmentActions'
import type { CalendarEventItem } from './resourceColors'

interface ResourceAppointmentsTableProps {
  events: CalendarEventItem[]
  isAdmin: boolean
  attendings: User[] | undefined
  rooms: Room[] | undefined
  equipment: Equipment[] | undefined
  expandedId: string | null
  onToggleExpand: (compositeKey: string) => void
}

/** The clinic-wide Resources lens: one row per resource booking. Non-admin
 * rows aren't clickable at all (no real appointment behind them to expand
 * into -- see resourceColors.ts's buildResourceCalendarEvents), so they
 * render as plain, static rows instead of a ClickableRow with nothing for
 * its action to do. */
export function ResourceAppointmentsTable({
  events,
  isAdmin,
  attendings,
  rooms,
  equipment,
  expandedId,
  onToggleExpand,
}: ResourceAppointmentsTableProps) {
  const colorScheme = useComputedColorScheme('light')
  return (
    <Table.ScrollContainer minWidth={700}>
      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Resource</Table.Th>
            <Table.Th>Kind</Table.Th>
            <Table.Th>Start</Table.Th>
            <Table.Th>End</Table.Th>
            {isAdmin ? (
              <>
                <Table.Th>Student</Table.Th>
                <Table.Th>Patient</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th />
              </>
            ) : (
              <Table.Th>Booked by</Table.Th>
            )}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {events.map((event) => {
            // One appointment using both a room and equipment produces two
            // rows here sharing the same event.id but different
            // resourceId (see buildResourceCalendarEvents' isAdmin branch)
            // -- the expansion key must be the same composite string
            // already used for React's key, or clicking either row would
            // expand both. The bare-id fallback below only matters for the
            // Waitlist deep-link (which only knows the appointment id, not
            // which resource row it landed on); harmless in the rare
            // dual-resource case since both rows are then just correct.
            const compositeKey = `${event.resourceId}-${event.id}`
            const expanded = expandedId === compositeKey || expandedId === event.id
            const rowContent = (
              <>
                <Table.Td>{event.resourceName}</Table.Td>
                <Table.Td>{event.resourceKind === 'room' ? 'Room' : 'Equipment'}</Table.Td>
                <Table.Td>{formatDateTime(event.start)}</Table.Td>
                <Table.Td>{formatDateTime(event.end)}</Table.Td>
                {isAdmin ? (
                  <>
                    <Table.Td>{event.resource?.student_name}</Table.Td>
                    <Table.Td>{event.resource?.patient_name}</Table.Td>
                    <Table.Td>
                      {event.resource && (
                        <Badge style={statusBadgeStyle(event.resource.status, colorScheme)}>
                          {statusLabel(event.resource.status)}
                        </Badge>
                      )}
                    </Table.Td>
                  </>
                ) : (
                  <Table.Td>{event.studentName}</Table.Td>
                )}
              </>
            )
            return (
              <Fragment key={compositeKey}>
                {isAdmin ? (
                  <ClickableRow
                    onToggle={() => onToggleExpand(compositeKey)}
                    expanded={expanded}
                    expandLabel={`Toggle details for ${event.resourceName} at ${formatDateTime(event.start)}`}
                  >
                    {rowContent}
                  </ClickableRow>
                ) : (
                  <Table.Tr className="list-item-enter">{rowContent}</Table.Tr>
                )}
                {isAdmin && (
                  <Table.Tr>
                    <Table.Td colSpan={8} p={0}>
                      <Collapse expanded={expanded} keepMounted={false}>
                        {event.resource && (
                          <Box p="md">
                            <AppointmentDetailPanel
                              appointment={event.resource}
                              attendings={attendings}
                              rooms={rooms}
                              equipment={equipment}
                            />
                          </Box>
                        )}
                      </Collapse>
                    </Table.Td>
                  </Table.Tr>
                )}
              </Fragment>
            )
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  )
}
