import { Badge, Button, Group, Stack, Table, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiErrorMessage } from '../../api/httpClient'
import type { ConflictResourceType, WaitlistStatus } from '../../api/types'
import { cancelWaitlistEntry, listWaitlistEntries } from '../../api/waitlist'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { ConfirmButton } from '../../components/ConfirmButton'
import { LoadingText } from '../../components/StateText'

const STATUS_COLORS: Record<WaitlistStatus, string> = {
  active: 'blue',
  booked: 'green',
  cancelled: 'gray',
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

  const isStudent = principal?.role === 'student'
  const isPatient = principal?.role === 'patient'
  const canManageOwn = isStudent || isPatient

  const { data: entries, isLoading } = useQuery({
    queryKey: ['waitlist'],
    queryFn: () => listWaitlistEntries(token),
  })

  const cancelMutation = useMutation({
    mutationFn: (entryId: string) => cancelWaitlistEntry(token, entryId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['waitlist'] })
      notifications.show({ message: 'Waitlist entry cancelled', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to cancel entry'),
        color: 'red',
      })
    },
  })

  const sortedEntries = [...(entries ?? [])].sort(
    (a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime(),
  )

  return (
    <Stack>
      <Title order={2}>Waitlist</Title>
      <Text size="sm" c="dimmed">
        A log of appointment requests that couldn't be booked because something was unavailable.
        Joining happens automatically when you try to book a conflicting time -- once whatever was
        blocking it frees up, it's booked for you here.
      </Text>

      {isLoading ? (
        <LoadingText />
      ) : sortedEntries.length === 0 ? (
        <Text c="dimmed">Nothing on the waitlist.</Text>
      ) : (
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
              <Table.Tr key={entry.id}>
                <Table.Td>
                  {new Date(entry.start_time).toLocaleString()} &ndash;{' '}
                  {new Date(entry.end_time).toLocaleString()}
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
                  <Badge color={STATUS_COLORS[entry.status]}>{entry.status}</Badge>
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
                      <ConfirmButton
                        label="Cancel"
                        message="This will remove your waitlist entry."
                        onConfirm={() => cancelMutation.mutate(entry.id)}
                        loading={cancelMutation.isPending}
                      />
                    )}
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  )
}
