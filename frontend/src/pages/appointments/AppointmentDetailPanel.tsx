import { Badge, Button, Group, Modal, Select, Stack, Text, Textarea } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  acceptAppointment,
  approveAppointment,
  cancelAppointment,
  completeAppointment,
  markNoShow,
  rejectAppointment,
  updateAppointment,
  type AppointmentCreateInput,
  type AppointmentUpdateInput,
} from '../../api/appointments'
import { apiErrorMessage, ApiError } from '../../api/httpClient'
import type { Appointment, ConflictReason, Equipment, Room, User } from '../../api/types'
import { joinWaitlist } from '../../api/waitlist'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { AppointmentDateTimeInput } from '../../components/AppointmentDateTimeInput'
import { ConfirmButton } from '../../components/ConfirmButton'
import { ConflictResolutionModal } from '../../components/ConflictResolutionModal'
import {
  APPOINTMENT_END_TIME_OPTIONS,
  APPOINTMENT_START_TIME_OPTIONS,
  formatDateTime,
  isoToMantineDateTime,
  mantineDateTimeToIso,
} from '../../utils/dates'
import {
  getAvailableActions,
  STATUS_COLORS,
  TERMINAL_STATUSES,
  type AppointmentActionName,
} from './appointmentActions'

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

// These three finalize the appointment (or, for cancel, end it outright) --
// worth a confirmation step before firing, unlike accept/approve/reject/edit
// which just move it forward in the normal flow.
const CONFIRM_MESSAGES: Partial<Record<AppointmentActionName, string>> = {
  cancel: 'This will cancel the appointment.',
  complete: 'This will mark the appointment as completed.',
  no_show: 'This will mark the appointment as a no-show.',
}

interface EditFormValues {
  // DateTimePicker value format -- see src/utils/dates.ts
  start_time: string | null
  end_time: string | null
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  notes: string
}

interface AppointmentDetailPanelProps {
  appointment: Appointment
  attendings?: User[]
  rooms?: Room[]
  equipment?: Equipment[]
  // Called after any direct action (accept/approve/reject/cancel/complete/
  // no_show) or a waitlist-join-cancels-this-appointment succeeds. Only
  // wired up by the Calendar view's viewing Modal (to close itself) --
  // left undefined for the inline List-view row expansions, which should
  // just keep showing the updated status in place, not collapse.
  onActionSuccess?: () => void
}

/** Inline/modal expanded detail for an appointment -- takes the
 * already-fetched list object (and the list page's already-fetched
 * attendings/rooms/equipment) as props rather than re-fetching any of them,
 * same shape as ForumPostCard/PatientDetailPanel. Rendered both inline in
 * AppointmentsListPage's List sub-view (inside an expanded table row) and
 * inside a Modal for the Calendar sub-view. */
export function AppointmentDetailPanel({
  appointment,
  attendings,
  rooms,
  equipment,
  onActionSuccess,
}: AppointmentDetailPanelProps) {
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

  const isStudent = principal?.role === 'student'

  const invalidateAppointments = () => queryClient.invalidateQueries({ queryKey: ['appointments'] })

  const actionMutation = useMutation({
    mutationFn: (actionName: AppointmentActionName) =>
      ACTION_FUNCTIONS[actionName](token, appointment.id),
    onSuccess: () => {
      invalidateAppointments()
      notifications.show({ message: 'Appointment updated', color: 'green' })
      onActionSuccess?.()
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
    mutationFn: (roomId?: string) => acceptAppointment(token, appointment.id, roomId),
    onSuccess: () => {
      invalidateAppointments()
      notifications.show({ message: 'Appointment updated', color: 'green' })
      closeAccept()
      onActionSuccess?.()
    },
    onError: (err, roomId) => {
      if (err instanceof ApiError && err.status === 409 && err.conflicts?.length) {
        setConflictState({
          payload: {
            patient_id: appointment.patient_id,
            attending_id: appointment.attending_id ?? undefined,
            room_id: roomId ?? appointment.room_id ?? undefined,
            equipment_id: appointment.equipment_id ?? undefined,
            start_time: appointment.start_time,
            end_time: appointment.end_time,
            notes: appointment.notes ?? undefined,
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
      updateAppointment(token, appointment.id, payload),
    onSuccess: () => {
      invalidateAppointments()
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
            patient_id: appointment.patient_id,
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
        await cancelAppointment(token, appointment.id)
        invalidateAppointments()
        notifications.show({
          message: 'Added to the waitlist and cancelled this appointment',
          color: 'green',
        })
      } catch (err) {
        invalidateAppointments()
        notifications.show({
          message: apiErrorMessage(
            err,
            'Added to the waitlist, but failed to cancel this appointment -- please cancel it manually',
          ),
          color: 'orange',
        })
      }
      onActionSuccess?.()
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to join the waitlist'),
        color: 'red',
      })
    },
  })

  if (!principal) return null

  const actions = getAvailableActions(appointment, principal)
  const acceptAction = actions.find((a) => a.name === 'accept')
  const otherActions = actions.filter((a) => a.name !== 'accept')
  const isOwningStudent = isStudent && appointment.student_id === principal.id
  const isTerminal = TERMINAL_STATUSES.includes(appointment.status)

  function handleAcceptClick() {
    if (appointment.room_id) {
      acceptMutation.mutate(undefined)
    } else {
      setAcceptRoomId(null)
      openAccept()
    }
  }

  function openEditModal() {
    editForm.setValues({
      start_time: isoToMantineDateTime(appointment.start_time),
      end_time: isoToMantineDateTime(appointment.end_time),
      attending_id: appointment.attending_id,
      room_id: appointment.room_id,
      equipment_id: appointment.equipment_id,
      notes: appointment.notes ?? '',
    })
    openEdit()
  }

  return (
    <Stack maw={480}>
      <Group justify="space-between">
        <Badge color={STATUS_COLORS[appointment.status]}>{appointment.status}</Badge>
      </Group>

      <Text>Start: {formatDateTime(appointment.start_time)}</Text>
      <Text>End: {formatDateTime(appointment.end_time)}</Text>
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
        {otherActions.map((action) => {
          const confirmMessage = CONFIRM_MESSAGES[action.name]
          if (confirmMessage) {
            return (
              <ConfirmButton
                key={action.name}
                label={action.label}
                message={confirmMessage}
                color={action.color}
                onConfirm={() => actionMutation.mutate(action.name)}
                loading={actionMutation.isPending}
              />
            )
          }
          return (
            <Button
              key={action.name}
              color={action.color}
              loading={actionMutation.isPending}
              onClick={() => actionMutation.mutate(action.name)}
            >
              {action.label}
            </Button>
          )
        })}
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
