import {
  Badge,
  Button,
  Group,
  Modal,
  SegmentedControl,
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
import dayjs from 'dayjs'
import { useMemo, useState } from 'react'
import { Calendar, dayjsLocalizer, type SlotInfo, type View } from 'react-big-calendar'
import { useNavigate } from 'react-router-dom'
import {
  createAppointment,
  listAppointments,
  type AppointmentCreateInput,
} from '../../api/appointments'
import { listAttendings } from '../../api/attendings'
import { listActiveEquipment } from '../../api/equipment'
import { apiErrorMessage } from '../../api/httpClient'
import { listPatients } from '../../api/patients'
import { listActiveRooms } from '../../api/rooms'
import { interpretSchedulingRequest } from '../../api/schedulingAssistant'
import type { AppointmentStatus } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { LoadingText } from '../../components/StateText'
import { isoToMantineDateTime, mantineDateTimeToIso } from '../../utils/dates'

const STATUS_COLORS: Record<AppointmentStatus, string> = {
  proposed: 'gray',
  awaiting_confirmation: 'yellow',
  confirmed: 'green',
  cancelled: 'red',
  completed: 'blue',
  no_show: 'orange',
  rescheduling_requested: 'yellow',
}

// react-big-calendar's eventPropGetter needs a real CSS color, not a
// Mantine theme key -- these are the hex values behind STATUS_COLORS above.
const STATUS_CSS_COLORS: Record<AppointmentStatus, string> = {
  proposed: '#868e96',
  awaiting_confirmation: '#f59f00',
  confirmed: '#2f9e44',
  cancelled: '#e03131',
  completed: '#1971c2',
  no_show: '#e8590c',
  rescheduling_requested: '#f59f00',
}

const localizer = dayjsLocalizer(dayjs)

interface CreateFormValues {
  patient_id: string
  attending_id: string | null
  room_id: string | null
  equipment_id: string | null
  // DateTimePicker value format -- see src/utils/dates.ts
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
  const [describeText, setDescribeText] = useState('')
  const [interpretWarnings, setInterpretWarnings] = useState<string[]>([])
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list')
  const [calendarView, setCalendarView] = useState<View>('week')

  const isStudent = principal?.role === 'student'
  const isPatient = principal?.role === 'patient'
  const isAdmin = principal?.role === 'admin'
  const canCreate = isStudent || isPatient

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
    enabled: isStudent || isAdmin,
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
      room_id: (value) => (isStudent && !value ? 'Room is required' : null),
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
      setDescribeText('')
      setInterpretWarnings([])
      close()
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to create appointment'),
        color: 'red',
      })
    },
  })

  const interpretMutation = useMutation({
    mutationFn: (text: string) => interpretSchedulingRequest(token, text),
    onSuccess: (data) => {
      form.setValues({
        ...(data.patient_id && { patient_id: data.patient_id }),
        ...(data.attending_id && { attending_id: data.attending_id }),
        ...(data.room_id && { room_id: data.room_id }),
        ...(data.equipment_id && { equipment_id: data.equipment_id }),
        ...(data.start_time && { start_time: isoToMantineDateTime(data.start_time) }),
        ...(data.end_time && { end_time: isoToMantineDateTime(data.end_time) }),
        ...(data.notes && { notes: data.notes }),
      })
      setInterpretWarnings(data.warnings)
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to interpret request'),
        color: 'red',
      })
    },
  })

  function handleOpenModal() {
    setDescribeText('')
    setInterpretWarnings([])
    open()
  }

  function handleSelectSlot(slotInfo: SlotInfo) {
    if (!canCreate) return
    handleOpenModal()
    form.setValues({
      start_time: isoToMantineDateTime(slotInfo.start.toISOString()),
      end_time: isoToMantineDateTime(slotInfo.end.toISOString()),
    })
  }

  function handleSelectEvent(event: { id: string }) {
    navigate(`/appointments/${event.id}`)
  }

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

  const calendarEvents = useMemo(
    () =>
      (appointments ?? []).map((appointment) => ({
        id: appointment.id,
        title: isAdmin
          ? `${appointment.patient_name} · ${appointment.equipment_id ? 'equipment in use' : 'no equipment'}`
          : `${appointment.patient_name} · ${appointment.status}`,
        start: new Date(appointment.start_time),
        end: new Date(appointment.end_time),
        resourceId: appointment.room_id ?? undefined,
        resource: appointment,
      })),
    [appointments, isAdmin],
  )

  // Admin's calendar shows rooms as resource lanes (a room-in-use view) --
  // every appointment always ends up with a room once confirmed, so this
  // is meaningful for every non-proposed appointment. Only built/passed
  // for admin; other roles keep the plain per-user calendar.
  const roomResources = useMemo(
    () => (rooms ?? []).map((r) => ({ resourceId: r.id, resourceTitle: r.name })),
    [rooms],
  )

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Appointments</Title>
        <Group>
          <SegmentedControl
            value={viewMode}
            onChange={(value) => setViewMode(value as 'list' | 'calendar')}
            data={[
              { label: 'List', value: 'list' },
              { label: 'Calendar', value: 'calendar' },
            ]}
          />
          {canCreate && <Button onClick={handleOpenModal}>New Appointment</Button>}
        </Group>
      </Group>

      {isLoading ? (
        <LoadingText />
      ) : viewMode === 'list' ? (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Start</Table.Th>
              <Table.Th>End</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Student</Table.Th>
              <Table.Th>Patient</Table.Th>
              <Table.Th>Attending</Table.Th>
              <Table.Th>Room</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {appointments?.map((appointment) => (
              <Table.Tr
                key={appointment.id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/appointments/${appointment.id}`)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/appointments/${appointment.id}`)
                  }
                }}
                tabIndex={0}
                role="button"
              >
                <Table.Td>{new Date(appointment.start_time).toLocaleString()}</Table.Td>
                <Table.Td>{new Date(appointment.end_time).toLocaleString()}</Table.Td>
                <Table.Td>
                  <Badge color={STATUS_COLORS[appointment.status]}>{appointment.status}</Badge>
                </Table.Td>
                <Table.Td>{appointment.student_name}</Table.Td>
                <Table.Td>{appointment.patient_name}</Table.Td>
                <Table.Td>{appointment.attending_name ?? '—'}</Table.Td>
                <Table.Td>{appointment.room_name ?? '—'}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      ) : (
        <div style={{ height: 700 }}>
          <Calendar
            localizer={localizer}
            events={calendarEvents}
            views={['month', 'week', 'day']}
            view={calendarView}
            onView={setCalendarView}
            selectable={canCreate}
            onSelectSlot={handleSelectSlot}
            onSelectEvent={handleSelectEvent}
            eventPropGetter={(event) => ({
              style: { backgroundColor: STATUS_CSS_COLORS[event.resource.status] },
            })}
            {...(isAdmin
              ? {
                  resources: roomResources,
                  resourceIdAccessor: 'resourceId',
                  resourceTitleAccessor: 'resourceTitle',
                }
              : {})}
            style={{ height: '100%' }}
          />
        </div>
      )}

      <Modal opened={opened} onClose={close} title="New Appointment">
        <Stack mb="md">
          <Textarea
            label="Describe it in your own words (optional)"
            placeholder="e.g. book Jane with Dr. Smith in the X-ray room next Tuesday afternoon"
            value={describeText}
            onChange={(event) => setDescribeText(event.currentTarget.value)}
            autosize
            minRows={2}
          />
          <Button
            type="button"
            variant="light"
            onClick={() => interpretMutation.mutate(describeText)}
            loading={interpretMutation.isPending}
            disabled={!describeText.trim()}
          >
            Interpret
          </Button>
          {interpretWarnings.map((warning) => (
            <Text key={warning} size="sm" c="dimmed">
              {warning}
            </Text>
          ))}
        </Stack>

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
                <Select label="Room" data={roomOptions} {...form.getInputProps('room_id')} />
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
