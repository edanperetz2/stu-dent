import { Badge, Button, Group, Stack, Table, Text, Title, useComputedColorScheme } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiErrorMessage, humanizeFieldName } from '../../api/httpClient'
import type { ConflictResourceType, WaitlistStatus } from '../../api/types'
import {
  cancelWaitlistEntry,
  listWaitlistEntries,
  reactivateWaitlistEntry,
} from '../../api/waitlist'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { TableSkeleton } from '../../components/Skeletons'
import { ErrorText } from '../../components/StateText'
import { showUndoToast } from '../../hooks/showUndoToast'
import { useListQuery } from '../../hooks/useListQuery'
import { BRAND_INK, hslToHex } from '../../theme'
import { formatDateTime } from '../../utils/dates'
import { maxLightnessForContrast } from '../../utils/colorContrast'

// One hue (+ saturation) per status -- same generation pattern as
// appointmentActions.ts's (larger) status table, kept as its own small
// table here rather than importing that one, since WaitlistStatus and
// AppointmentStatus are genuinely different enums that only coincide on
// "cancelled" by name. Saturation 0 (cancelled) is a neutral gray.
const STATUS_COLOR_SPEC: Record<WaitlistStatus, { hue: number; saturation: number }> = {
  active: { hue: 208, saturation: 0.85 },
  booked: { hue: 132, saturation: 0.85 },
  cancelled: { hue: 0, saturation: 0 },
}

const WHITE = '#ffffff'
const PALE_LIGHTNESS = 0.93

// Pale background + a uniform dark ink text color for light mode -- same
// reasoning as appointmentActions.ts's statusBadgeStyle (reliable AA
// contrast regardless of hue, without hand-picking a matching dark shade
// per status). Dark mode uses the saturated variant below instead, so a
// badge doesn't stay a bright near-white pill against a dark page.
const STATUS_BADGE_BACKGROUND: Record<WaitlistStatus, string> = Object.fromEntries(
  Object.entries(STATUS_COLOR_SPEC).map(([status, { hue, saturation }]) => [
    status,
    hslToHex(hue, saturation, PALE_LIGHTNESS),
  ]),
) as Record<WaitlistStatus, string>

const STATUS_BADGE_BACKGROUND_DARK: Record<WaitlistStatus, string> = Object.fromEntries(
  Object.entries(STATUS_COLOR_SPEC).map(([status, { hue, saturation }]) => [
    status,
    hslToHex(hue, saturation, maxLightnessForContrast(hue, saturation, hslToHex, WHITE)),
  ]),
) as Record<WaitlistStatus, string>

function statusBadgeStyle(status: WaitlistStatus, colorScheme: 'light' | 'dark'): CSSProperties {
  if (colorScheme === 'dark') {
    return { backgroundColor: STATUS_BADGE_BACKGROUND_DARK[status], color: '#ffffff' }
  }
  return { backgroundColor: STATUS_BADGE_BACKGROUND[status], color: BRAND_INK }
}

const CAUSE_LABELS: Record<ConflictResourceType, string> = {
  student: 'Student busy',
  patient: 'Patient busy',
  attending: 'Attending busy',
  room: 'Room busy',
  equipment: 'Equipment busy',
}

export function WaitlistPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const colorScheme = useComputedColorScheme('light')
  const isStudent = principal?.role === 'student'
  const isPatient = principal?.role === 'patient'
  const canManageOwn = isStudent || isPatient

  const waitlistQuery = useListQuery({
    queryKey: ['waitlist'],
    queryFn: () => listWaitlistEntries(token),
    errorFallback: 'Failed to load the waitlist.',
  })
  const entries = waitlistQuery.status === 'ready' ? waitlistQuery.data : undefined

  const invalidateWaitlist = () => queryClient.invalidateQueries({ queryKey: ['waitlist'] })

  const cancelMutation = useMutation({
    mutationFn: (entryId: string) => cancelWaitlistEntry(token, entryId),
    onSuccess: (_, entryId) => {
      invalidateWaitlist()
      showUndoToast({
        message: 'Waitlist entry cancelled.',
        onUndo: () => reactivateMutation.mutate(entryId),
      })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to cancel entry'),
        color: 'red',
      })
    },
  })

  const reactivateMutation = useMutation({
    mutationFn: (entryId: string) => reactivateWaitlistEntry(token, entryId),
    onSuccess: invalidateWaitlist,
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to restore the waitlist entry'),
        color: 'red',
      })
    },
  })

  // Ascending -- soonest-requested time first, matching the appointments
  // lists' sort order.
  const sortedEntries = [...(entries ?? [])].sort(
    (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime(),
  )

  return (
    <Stack>
      <Title order={2}>Waitlist</Title>
      <Text size="sm" c="dimmed">
        A log of appointment requests that couldn't be booked because something was unavailable.
        Joining happens automatically when you try to book a conflicting time -- once whatever was
        blocking it frees up, it's booked for you here.
      </Text>

      {waitlistQuery.status === 'loading' ? (
        <TableSkeleton columns={5} />
      ) : waitlistQuery.status === 'error' ? (
        <ErrorText onRetry={waitlistQuery.retry}>{waitlistQuery.message}</ErrorText>
      ) : waitlistQuery.status === 'empty' ? (
        <Text c="dimmed">Nothing on the waitlist.</Text>
      ) : (
        <Table.ScrollContainer minWidth={600}>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Requested time</Table.Th>
              <Table.Th>Requested for</Table.Th>
              <Table.Th>Why</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {sortedEntries.map((entry) => (
              <Table.Tr key={entry.id} className="list-item-enter">
                <Table.Td>
                  {formatDateTime(entry.start_time)} &ndash;{' '}
                  {formatDateTime(entry.end_time)}
                </Table.Td>
                <Table.Td>
                  {[entry.attending_name, entry.room_name, entry.equipment_name]
                    .filter(Boolean)
                    .join(', ') || '—'}
                </Table.Td>
                <Table.Td>
                  <Group gap={4}>
                    {entry.conflicts.map((conflict) => (
                      <Badge key={conflict.resource_type} size="sm" color="orange">
                        {CAUSE_LABELS[conflict.resource_type]}
                      </Badge>
                    ))}
                  </Group>
                </Table.Td>
                <Table.Td>
                  <Badge style={statusBadgeStyle(entry.status, colorScheme)}>
                    {humanizeFieldName(entry.status)}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Group gap="xs">
                    {entry.status === 'booked' && entry.resulting_appointment_id && (
                      <Button
                        size="xs"
                        variant="light"
                        onClick={() => navigate(`/appointments?appointment=${entry.resulting_appointment_id}`)}
                      >
                        View appointment ({entry.resulting_appointment_status})
                      </Button>
                    )}
                    {canManageOwn && entry.status === 'active' && (
                      <Button
                        size="xs"
                        color="red"
                        variant="light"
                        loading={cancelMutation.isPending && cancelMutation.variables === entry.id}
                        onClick={() => cancelMutation.mutate(entry.id)}
                      >
                        Cancel
                      </Button>
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
