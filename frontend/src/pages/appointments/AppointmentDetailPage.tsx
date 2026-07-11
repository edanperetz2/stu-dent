import { Badge, Button, Group, Modal, Select, Stack, Text, Textarea, Title } from '@mantine/core'
import { DateTimePicker } from '@mantine/dates'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import {
  acceptAppointment,
  approveAppointment,
  cancelAppointment,
  completeAppointment,
  getAppointment,
  markNoShow,
  rejectAppointment,
  updateAppointment,
  type AppointmentUpdateInput,
} from '../../api/appointments'
import { listAttendings } from '../../api/attendings'
import { listActiveEquipment } from '../../api/equipment'
import { ApiError } from '../../api/httpClient'
import { listActiveRooms } from '../../api/rooms'
import type { Appointment, AppointmentStatus } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { isoToMantineDateTime, mantineDateTimeToIso } from '../../utils/dates'
import { getAvailableActions, type AppointmentActionName } from './appointmentActions'

const STATUS_COLORS: Record<AppointmentStatus, string> = {
  proposed: 'gray',
  awaiting_confirmation: 'yellow',
  confirmed: 'green',
  cancelled: 'red',
  completed: 'blue',
  no_show: 'orange',
  rescheduling_requested: 'yellow',
}

const ACTION_FUNCTIONS: Record<
  AppointmentActionName,
  (token: string, id: string) => Promise<Appointment>
> = {
  accept: acceptAppointment,
  approve: approveAppointment,
  reject: rejectAppointment,
  cancel: cancelAppointment,
  complete: completeAppointment,
  no_show: markNoShow,
}

const TERMINAL_STATUSES: AppointmentStatus[] = ['cancelled', 'completed', 'no_show']

interface EditFormValues {
  // DateTimePicker value format -- see src/utils/dates.ts
  start_time: string | null
  end_time: string | null
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  notes: string
}

export function AppointmentDetailPage() {
  const { appointmentId } = useParams<{ appointmentId: string }>()
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [editOpened, { open: openEdit, close: closeEdit }] = useDisclosure(false)

  const { data: appointment, isLoading } = useQuery({
    queryKey: ['appointments', appointmentId],
    queryFn: () => getAppointment(token, appointmentId!),
    enabled: !!appointmentId,
  })

  const isStudent = principal?.role === 'student'

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

  const actionMutation = useMutation({
    mutationFn: (actionName: AppointmentActionName) =>
      ACTION_FUNCTIONS[actionName](token, appointmentId!),
    onSuccess: (updated) => {
      queryClient.setQueryData(['appointments', appointmentId], updated)
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      notifications.show({ message: 'Appointment updated', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: err instanceof ApiError ? err.message : 'Action failed',
        color: 'red',
      })
    },
  })

  const editForm = useForm<EditFormValues>({
    initialValues: {
      start_time: null,
      end_time: null,
      attending_id: null,
      room_id: null,
      equipment_id: null,
      notes: '',
    },
  })

  const editMutation = useMutation({
    mutationFn: (payload: AppointmentUpdateInput) =>
      updateAppointment(token, appointmentId!, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(['appointments', appointmentId], updated)
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      notifications.show({ message: 'Appointment updated', color: 'green' })
      closeEdit()
    },
    onError: (err) => {
      notifications.show({
        message: err instanceof ApiError ? err.message : 'Failed to update appointment',
        color: 'red',
      })
    },
  })

  if (isLoading) return <Text>Loading...</Text>
  if (!appointment || !principal) return <Text>Appointment not found.</Text>

  const actions = getAvailableActions(appointment, principal)
  const isOwningStudent = isStudent && appointment.student_id === principal.id
  const isTerminal = TERMINAL_STATUSES.includes(appointment.status)

  function openEditModal() {
    editForm.setValues({
      start_time: isoToMantineDateTime(appointment!.start_time),
      end_time: isoToMantineDateTime(appointment!.end_time),
      attending_id: appointment!.attending_id,
      room_id: appointment!.room_id,
      equipment_id: appointment!.equipment_id,
      notes: appointment!.notes ?? '',
    })
    openEdit()
  }

  return (
    <Stack maw={480}>
      <Group justify="space-between">
        <Title order={2}>Appointment</Title>
        <Badge color={STATUS_COLORS[appointment.status]}>{appointment.status}</Badge>
      </Group>

      <Text>Start: {new Date(appointment.start_time).toLocaleString()}</Text>
      <Text>End: {new Date(appointment.end_time).toLocaleString()}</Text>
      {appointment.notes && <Text>Notes: {appointment.notes}</Text>}

      <Group>
        {actions.map((action) => (
          <Button
            key={action.name}
            color={action.color}
            loading={actionMutation.isPending}
            onClick={() => actionMutation.mutate(action.name)}
          >
            {action.label}
          </Button>
        ))}
        {isOwningStudent && !isTerminal && (
          <Button variant="light" onClick={openEditModal}>
            Edit
          </Button>
        )}
      </Group>

      <Modal opened={editOpened} onClose={closeEdit} title="Edit Appointment">
        <form
          onSubmit={editForm.onSubmit((values) =>
            editMutation.mutate({
              start_time: values.start_time ? mantineDateTimeToIso(values.start_time) : undefined,
              end_time: values.end_time ? mantineDateTimeToIso(values.end_time) : undefined,
              attending_id: values.attending_id,
              room_id: values.room_id,
              equipment_id: values.equipment_id,
              notes: values.notes || null,
            }),
          )}
        >
          <Stack>
            <DateTimePicker label="Start time" {...editForm.getInputProps('start_time')} />
            <DateTimePicker label="End time" {...editForm.getInputProps('end_time')} />
            <Select
              label="Attending"
              data={(attendings ?? []).map((a) => ({ value: a.id, label: a.full_name }))}
              clearable
              {...editForm.getInputProps('attending_id')}
            />
            <Select
              label="Room"
              data={(rooms ?? []).map((r) => ({ value: r.id, label: r.name }))}
              clearable
              {...editForm.getInputProps('room_id')}
            />
            <Select
              label="Equipment"
              data={(equipment ?? []).map((e) => ({ value: e.id, label: e.name }))}
              clearable
              {...editForm.getInputProps('equipment_id')}
            />
            <Textarea label="Notes" {...editForm.getInputProps('notes')} />
            <Button type="submit" loading={editMutation.isPending}>
              Save
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
