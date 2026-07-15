import { Badge, Button, Group, Modal, Select, Stack, Text, Textarea, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
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
  type AppointmentCreateInput,
  type AppointmentUpdateInput,
} from '../../api/appointments'
import { listAttendings } from '../../api/attendings'
import { listActiveEquipment } from '../../api/equipment'
import { apiErrorMessage, ApiError } from '../../api/httpClient'
import { listActiveRooms } from '../../api/rooms'
import type { Appointment, AppointmentStatus, ConflictReason } from '../../api/types'
import { joinWaitlist } from '../../api/waitlist'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { AppointmentDateTimeInput } from '../../components/AppointmentDateTimeInput'
import { ConflictResolutionModal } from '../../components/ConflictResolutionModal'
import { LoadingText } from '../../components/StateText'
import {
  APPOINTMENT_END_TIME_OPTIONS,
  APPOINTMENT_START_TIME_OPTIONS,
  isoToMantineDateTime,
  mantineDateTimeToIso,
} from '../../utils/dates'
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
  const [acceptOpened, { open: openAccept, close: closeAccept }] = useDisclosure(false)
  const [acceptRoomId, setAcceptRoomId] = useState<string | null>(null)
  const [conflictState, setConflictState] = useState<{
    payload: AppointmentCreateInput
    conflicts: ConflictReason[]
  } | null>(null)

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
        message: apiErrorMessage(err, 'Action failed'),
        color: 'red',
      })
    },
  })

  // A patient-initiated request starts room-less -- accepting it is the
  // point where the owning student must supply one, so it gets its own
  // mutation/modal instead of going through the generic actionMutation
  // above (which assumes no extra input is needed).
  const acceptMutation = useMutation({
    mutationFn: (roomId?: string) => acceptAppointment(token, appointmentId!, roomId),
    onSuccess: (updated) => {
      queryClient.setQueryData(['appointments', appointmentId], updated)
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      notifications.show({ message: 'Appointment updated', color: 'green' })
      closeAccept()
    },
    onError: (err, roomId) => {
      if (err instanceof ApiError && err.status === 409 && err.conflicts?.length) {
        setConflictState({
          payload: {
            patient_id: appointment!.patient_id,
            attending_id: appointment!.attending_id ?? undefined,
            room_id: roomId ?? appointment!.room_id ?? undefined,
            equipment_id: appointment!.equipment_id ?? undefined,
            start_time: appointment!.start_time,
            end_time: appointment!.end_time,
            notes: appointment!.notes ?? undefined,
          },
          conflicts: err.conflicts,
        })
        return
      }
      notifications.show({
        message: apiErrorMessage(err, 'Action failed'),
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
    validate: {
      room_id: (value) => (value ? null : 'Room is required'),
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
    onError: (err, payload) => {
      // The edit form always submits every field (pre-filled from the
      // current appointment, then edited) -- payload is already the full
      // attempted request, not a sparse patch, so no merge with
      // `appointment` is needed here.
      if (err instanceof ApiError && err.status === 409 && err.conflicts?.length) {
        setConflictState({
          payload: {
            patient_id: appointment!.patient_id,
            attending_id: payload.attending_id ?? undefined,
            room_id: payload.room_id ?? undefined,
            equipment_id: payload.equipment_id ?? undefined,
            start_time: payload.start_time!,
            end_time: payload.end_time!,
            notes: payload.notes ?? undefined,
          },
          conflicts: err.conflicts,
        })
        return
      }
      notifications.show({
        message: apiErrorMessage(err, 'Failed to update appointment'),
        color: 'red',
      })
    },
  })

  const joinWaitlistMutation = useMutation({
    mutationFn: (payload: AppointmentCreateInput) => joinWaitlist(token, payload),
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['waitlist'] })
      setConflictState(null)
      closeEdit()
      closeAccept()
      // This conflict came from editing/accepting an *existing*
      // appointment, not a fresh create -- joining the waitlist means
      // moving away from it, so cancel it now rather than leaving the
      // user holding both an active appointment and a pending waitlist
      // entry for the same intent. The join already succeeded by this
      // point, so a failure here is reported separately, not as "the
      // waitlist join failed" (it didn't).
      try {
        await cancelAppointment(token, appointmentId!)
        queryClient.invalidateQueries({ queryKey: ['appointments'] })
        notifications.show({
          message: 'Added to the waitlist and cancelled this appointment',
          color: 'green',
        })
      } catch (err) {
        queryClient.invalidateQueries({ queryKey: ['appointments'] })
        notifications.show({
          message: apiErrorMessage(
            err,
            'Added to the waitlist, but failed to cancel this appointment -- please cancel it manually',
          ),
          color: 'orange',
        })
      }
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to join the waitlist'),
        color: 'red',
      })
    },
  })

  if (isLoading) return <LoadingText />
  if (!appointment || !principal) return <Text>Appointment not found.</Text>

  const actions = getAvailableActions(appointment, principal)
  const acceptAction = actions.find((a) => a.name === 'accept')
  const otherActions = actions.filter((a) => a.name !== 'accept')
  const isOwningStudent = isStudent && appointment.student_id === principal.id
  const isTerminal = TERMINAL_STATUSES.includes(appointment.status)

  function handleAcceptClick() {
    if (appointment!.room_id) {
      acceptMutation.mutate(undefined)
    } else {
      setAcceptRoomId(null)
      openAccept()
    }
  }

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
      <Text>Student: {appointment.student_name}</Text>
      <Text>Patient: {appointment.patient_name}</Text>
      <Text>Attending: {appointment.attending_name ?? '—'}</Text>
      <Text>Room: {appointment.room_name ?? '—'}</Text>
      <Text>Equipment: {appointment.equipment_name ?? '—'}</Text>
      {appointment.notes && <Text>Notes: {appointment.notes}</Text>}

      <Group>
        {acceptAction && (
          <Button
            key={acceptAction.name}
            color={acceptAction.color}
            loading={acceptMutation.isPending}
            onClick={handleAcceptClick}
          >
            {acceptAction.label}
          </Button>
        )}
        {otherActions.map((action) => (
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
            <AppointmentDateTimeInput
              label="Start time"
              timeOptions={APPOINTMENT_START_TIME_OPTIONS}
              {...editForm.getInputProps('start_time')}
            />
            <AppointmentDateTimeInput
              label="End time"
              timeOptions={APPOINTMENT_END_TIME_OPTIONS}
              {...editForm.getInputProps('end_time')}
            />
            <Select
              label="Attending"
              data={(attendings ?? []).map((a) => ({ value: a.id, label: a.full_name }))}
              clearable
              {...editForm.getInputProps('attending_id')}
            />
            <Select
              label="Room"
              data={(rooms ?? []).map((r) => ({ value: r.id, label: r.name }))}
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

      <Modal opened={acceptOpened} onClose={closeAccept} title="Assign a room to accept">
        <Stack>
          <Select
            label="Room"
            data={(rooms ?? []).map((r) => ({ value: r.id, label: r.name }))}
            value={acceptRoomId}
            onChange={setAcceptRoomId}
          />
          <Button
            disabled={!acceptRoomId}
            loading={acceptMutation.isPending}
            onClick={() => acceptMutation.mutate(acceptRoomId ?? undefined)}
          >
            Accept
          </Button>
        </Stack>
      </Modal>

      {conflictState && (
        <ConflictResolutionModal
          opened
          onClose={() => setConflictState(null)}
          conflicts={conflictState.conflicts}
          joining={joinWaitlistMutation.isPending}
          onJoinWaitlist={() => joinWaitlistMutation.mutate(conflictState.payload)}
          cancelsExistingAppointment
        />
      )}
    </Stack>
  )
}
