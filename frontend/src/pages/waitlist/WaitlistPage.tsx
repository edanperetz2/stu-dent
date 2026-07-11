import { Badge, Button, Group, Modal, Select, Stack, Table, Title } from '@mantine/core'
import { DateTimePicker } from '@mantine/dates'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { listAttendings } from '../../api/attendings'
import { listActiveEquipment } from '../../api/equipment'
import { apiErrorMessage } from '../../api/httpClient'
import { listPatients } from '../../api/patients'
import { listActiveRooms } from '../../api/rooms'
import type { WaitlistStatus } from '../../api/types'
import { cancelWaitlistEntry, createWaitlistEntry, listWaitlistEntries } from '../../api/waitlist'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { ConfirmButton } from '../../components/ConfirmButton'
import { LoadingText } from '../../components/StateText'
import { mantineDateTimeToIso } from '../../utils/dates'

const STATUS_COLORS: Record<WaitlistStatus, string> = {
  active: 'blue',
  notified: 'green',
  cancelled: 'gray',
}

interface CreateFormValues {
  patient_id: string
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  start_time: string | null
  end_time: string | null
}

export function WaitlistPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [opened, { open, close }] = useDisclosure(false)

  const isStudent = principal?.role === 'student'
  const isPatient = principal?.role === 'patient'
  const canManageOwn = isStudent || isPatient

  const { data: entries, isLoading } = useQuery({
    queryKey: ['waitlist'],
    queryFn: () => listWaitlistEntries(token),
  })

  const { data: patients } = useQuery({
    queryKey: ['patients'],
    queryFn: () => listPatients(token),
    enabled: isStudent,
  })
  const { data: attendings } = useQuery({
    queryKey: ['attendings'],
    queryFn: () => listAttendings(token),
    enabled: isStudent,
  })
  const { data: rooms } = useQuery({
    queryKey: ['rooms'],
    queryFn: () => listActiveRooms(token),
    enabled: isStudent,
  })
  const { data: equipment } = useQuery({
    queryKey: ['equipment'],
    queryFn: () => listActiveEquipment(token),
    enabled: isStudent,
  })

  const form = useForm<CreateFormValues>({
    initialValues: {
      patient_id: '',
      attending_id: null,
      room_id: null,
      equipment_id: null,
      start_time: null,
      end_time: null,
    },
    validate: {
      patient_id: (value) => (isStudent && !value ? 'Patient is required' : null),
      start_time: (value) => (value ? null : 'Start time is required'),
      end_time: (value, values) =>
        value && values.start_time && value <= values.start_time
          ? 'End time must be after start time'
          : null,
    },
  })

  const createMutation = useMutation({
    mutationFn: () => {
      const values = form.values
      return createWaitlistEntry(token, {
        ...(isStudent ? { patient_id: values.patient_id } : {}),
        ...(values.attending_id ? { attending_id: values.attending_id } : {}),
        ...(values.room_id ? { room_id: values.room_id } : {}),
        ...(values.equipment_id ? { equipment_id: values.equipment_id } : {}),
        start_time: mantineDateTimeToIso(values.start_time!),
        end_time: mantineDateTimeToIso(values.end_time!),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['waitlist'] })
      notifications.show({ message: 'Added to waitlist', color: 'green' })
      form.reset()
      close()
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to join waitlist'),
        color: 'red',
      })
    },
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

  const patientOptions = (patients ?? []).map((p) => ({ value: p.id, label: p.full_name }))
  const attendingOptions = (attendings ?? []).map((a) => ({ value: a.id, label: a.full_name }))
  const roomOptions = (rooms ?? []).map((r) => ({ value: r.id, label: r.name }))
  const equipmentOptions = (equipment ?? []).map((e) => ({ value: e.id, label: e.name }))

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Waitlist</Title>
        {canManageOwn && <Button onClick={open}>New Waitlist Entry</Button>}
      </Group>

      {isLoading ? (
        <LoadingText />
      ) : (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Start</Table.Th>
              <Table.Th>End</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {entries?.map((entry) => (
              <Table.Tr key={entry.id}>
                <Table.Td>{new Date(entry.start_time).toLocaleString()}</Table.Td>
                <Table.Td>{new Date(entry.end_time).toLocaleString()}</Table.Td>
                <Table.Td>
                  <Badge color={STATUS_COLORS[entry.status]}>{entry.status}</Badge>
                </Table.Td>
                <Table.Td>
                  {canManageOwn && entry.status === 'active' && (
                    <ConfirmButton
                      label="Cancel"
                      message="This will cancel your waitlist entry."
                      onConfirm={() => cancelMutation.mutate(entry.id)}
                      loading={cancelMutation.isPending}
                    />
                  )}
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="New Waitlist Entry">
        <form onSubmit={form.onSubmit(() => createMutation.mutate())}>
          <Stack>
            {isStudent && (
              <Select label="Patient" data={patientOptions} {...form.getInputProps('patient_id')} />
            )}
            <DateTimePicker label="Start time" {...form.getInputProps('start_time')} />
            <DateTimePicker label="End time" {...form.getInputProps('end_time')} />
            {isStudent && (
              <>
                <Select
                  label="Attending (optional)"
                  data={attendingOptions}
                  clearable
                  {...form.getInputProps('attending_id')}
                />
                <Select
                  label="Room (optional)"
                  data={roomOptions}
                  clearable
                  {...form.getInputProps('room_id')}
                />
                <Select
                  label="Equipment (optional)"
                  data={equipmentOptions}
                  clearable
                  {...form.getInputProps('equipment_id')}
                />
              </>
            )}
            <Button type="submit" loading={createMutation.isPending}>
              Join Waitlist
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
