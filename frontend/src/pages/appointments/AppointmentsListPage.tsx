import {
  Badge,
  Button,
  Group,
  Modal,
  Select,
  Stack,
  Table,
  Text,
  Textarea,
  Title,
} from '@mantine/core'
import { DateTimePicker } from '@mantine/dates'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  createAppointment,
  listAppointments,
  type AppointmentCreateInput,
} from '../../api/appointments'
import { listAttendings } from '../../api/attendings'
import { listActiveEquipment } from '../../api/equipment'
import { ApiError } from '../../api/httpClient'
import { listPatients } from '../../api/patients'
import { listActiveRooms } from '../../api/rooms'
import type { AppointmentStatus } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { mantineDateTimeToIso } from '../../utils/dates'

const STATUS_COLORS: Record<AppointmentStatus, string> = {
  proposed: 'gray',
  awaiting_confirmation: 'yellow',
  confirmed: 'green',
  cancelled: 'red',
  completed: 'blue',
  no_show: 'orange',
  rescheduling_requested: 'yellow',
}

interface CreateFormValues {
  patient_id: string
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  // Mantine's DateTimePicker onChange always emits a "YYYY-MM-DD HH:mm:ss"
  // string, never a Date -- see src/utils/dates.ts.
  start_time: string | null
  end_time: string | null
  notes: string
}

export function AppointmentsListPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [opened, { open, close }] = useDisclosure(false)

  const isStudent = principal?.role === 'student'
  const isPatient = principal?.role === 'patient'

  const { data: appointments, isLoading } = useQuery({
    queryKey: ['appointments'],
    queryFn: () => listAppointments(token),
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
      notes: '',
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
    mutationFn: (payload: AppointmentCreateInput) => createAppointment(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      notifications.show({ message: 'Appointment requested', color: 'green' })
      form.reset()
      close()
    },
    onError: (err) => {
      notifications.show({
        message: err instanceof ApiError ? err.message : 'Failed to create appointment',
        color: 'red',
      })
    },
  })

  function handleSubmit(values: CreateFormValues) {
    const payload: AppointmentCreateInput = {
      start_time: mantineDateTimeToIso(values.start_time!),
      end_time: mantineDateTimeToIso(values.end_time!),
      notes: values.notes || undefined,
    }
    if (isStudent) {
      payload.patient_id = values.patient_id
      if (values.attending_id) payload.attending_id = values.attending_id
      if (values.room_id) payload.room_id = values.room_id
      if (values.equipment_id) payload.equipment_id = values.equipment_id
    }
    createMutation.mutate(payload)
  }

  const patientOptions = (patients ?? []).map((p) => ({ value: p.id, label: p.full_name }))
  const attendingOptions = (attendings ?? []).map((a) => ({ value: a.id, label: a.full_name }))
  const roomOptions = (rooms ?? []).map((r) => ({ value: r.id, label: r.name }))
  const equipmentOptions = (equipment ?? []).map((e) => ({ value: e.id, label: e.name }))

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Appointments</Title>
        {(isStudent || isPatient) && <Button onClick={open}>New Appointment</Button>}
      </Group>

      {isLoading ? (
        <Text>Loading...</Text>
      ) : (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Start</Table.Th>
              <Table.Th>End</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {appointments?.map((appointment) => (
              <Table.Tr
                key={appointment.id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/appointments/${appointment.id}`)}
              >
                <Table.Td>{new Date(appointment.start_time).toLocaleString()}</Table.Td>
                <Table.Td>{new Date(appointment.end_time).toLocaleString()}</Table.Td>
                <Table.Td>
                  <Badge color={STATUS_COLORS[appointment.status]}>{appointment.status}</Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="New Appointment">
        <form onSubmit={form.onSubmit(handleSubmit)}>
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
            <Textarea label="Notes (optional)" {...form.getInputProps('notes')} />
            <Button type="submit" loading={createMutation.isPending}>
              Request
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
