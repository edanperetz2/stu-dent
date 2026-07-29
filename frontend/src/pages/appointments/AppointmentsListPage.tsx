import {
  Badge,
  Button,
  Chip,
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
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { Fragment, useEffect, useMemo, useState } from 'react'
import { Calendar, dayjsLocalizer, type Formats, type SlotInfo, type View } from 'react-big-calendar'
import { useSearchParams } from 'react-router-dom'
import {
  createAppointment,
  listAppointments,
  type AppointmentCreateInput,
} from '../../api/appointments'
import { listAttendings } from '../../api/attendings'
import { listActiveEquipment } from '../../api/equipment'
import { apiErrorMessage, ApiError } from '../../api/httpClient'
import { listPatients } from '../../api/patients'
import { getResourcesSchedule } from '../../api/resources'
import { listActiveRooms } from '../../api/rooms'
import { interpretSchedulingRequest } from '../../api/schedulingAssistant'
import type { Appointment, AppointmentStatus, ConflictReason } from '../../api/types'
import { joinWaitlist } from '../../api/waitlist'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { AppointmentDateTimeInput } from '../../components/AppointmentDateTimeInput'
import { ConflictResolutionModal } from '../../components/ConflictResolutionModal'
import { EmptyText, LoadingText } from '../../components/StateText'
import { AppointmentDetailPanel } from './AppointmentDetailPanel'
import { STATUS_COLORS } from './appointmentActions'
import {
  APPOINTMENT_END_TIME_OPTIONS,
  APPOINTMENT_START_TIME_OPTIONS,
  formatDateTime,
  isoToMantineDateTime,
  mantineDateTimeToIso,
} from '../../utils/dates'

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

// dayjsLocalizer's own defaults use dayjs's localized-time token ('LT'),
// which in the default English locale is 12-hour with AM/PM -- override
// with plain dd/mm + 24h tokens instead (Israel-based app). Agenda-view
// format keys are intentionally left at their defaults since Agenda isn't
// one of this calendar's enabled `views` below.
const CALENDAR_FORMATS: Formats = {
  timeGutterFormat: 'HH:mm',
  dayFormat: 'ddd DD/MM',
  dayHeaderFormat: 'dddd DD/MM/YYYY',
  dayRangeHeaderFormat: ({ start, end }, culture, localizer) =>
    `${localizer!.format(start, 'DD/MM', culture)} – ${localizer!.format(end, 'DD/MM', culture)}`,
  eventTimeRangeFormat: ({ start, end }, culture, localizer) =>
    `${localizer!.format(start, 'HH:mm', culture)} – ${localizer!.format(end, 'HH:mm', culture)}`,
  selectRangeFormat: ({ start, end }, culture, localizer) =>
    `${localizer!.format(start, 'HH:mm', culture)} – ${localizer!.format(end, 'HH:mm', culture)}`,
}

// What the calendar/list view is currently showing: the signed-in user's own
// appointments (default, status-colored), or a clinic-wide resource view --
// every room+equipment booking, colored per resource instead of per status.
// Patients only ever get 'personal'. Students/attendings can switch to
// 'resources', which is anonymized (reveals only which student booked a
// slot, never the patient) via the /resources/schedule endpoint. Admin only
// ever gets 'resources' too, but built from the full appointment list it
// already has -- same shape, full detail, no anonymization.
type CalendarLens = 'personal' | 'resources'

// A stable palette so each resource gets a distinct color -- looked up by
// hashing the resourceId (see hashResourceColor) rather than by its
// position in a list, so a resource's color never shifts just because
// another resource was added, deactivated, or reactivated. Paired arrays
// (same key = same color) since Mantine's <Chip color> wants a theme color
// name but react-big-calendar's eventPropGetter needs a real CSS hex value.
const RESOURCE_COLOR_NAMES = [
  'gray',
  'orange',
  'blue',
  'green',
  'red',
  'grape',
  'cyan',
  'pink',
  'yellow',
  'teal',
] as const
const RESOURCE_COLOR_HEX: Record<(typeof RESOURCE_COLOR_NAMES)[number], string> = {
  gray: '#868e96',
  orange: '#f59f00',
  blue: '#1971c2',
  green: '#2f9e44',
  red: '#e03131',
  grape: '#9c36b5',
  cyan: '#0c8599',
  pink: '#c2255c',
  yellow: '#f08c00',
  teal: '#0ca678',
}

export function hashResourceColor(resourceId: string): (typeof RESOURCE_COLOR_NAMES)[number] {
  let hash = 0
  for (let i = 0; i < resourceId.length; i++) {
    hash = (hash * 31 + resourceId.charCodeAt(i)) | 0
  }
  return RESOURCE_COLOR_NAMES[Math.abs(hash) % RESOURCE_COLOR_NAMES.length]
}

interface ResourceOption {
  resourceId: string
  resourceTitle: string
}

// `resource` is null for the anonymized Resources-lens busy-window events
// (no real appointment behind them for a non-admin viewer) -- `studentName`
// covers that case instead. `resourceId`/`resourceName`/`resourceKind` are
// only set for Resources-lens events; they drive the color, the show/hide
// filter chips, and the List view's columns.
interface CalendarEventItem {
  id: string
  title: string
  start: Date
  end: Date
  resourceId?: string
  resourceName?: string
  resourceKind?: 'room' | 'equipment'
  resource: Appointment | null
  studentName?: string
}

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
  const [searchParams, setSearchParams] = useSearchParams()
  const [opened, { open, close }] = useDisclosure(false)
  const [describeText, setDescribeText] = useState('')
  const [interpretWarnings, setInterpretWarnings] = useState<string[]>([])
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list')
  const [calendarView, setCalendarView] = useState<View>('week')
  const [calendarDate, setCalendarDate] = useState(new Date())
  const [calendarLens, setCalendarLens] = useState<CalendarLens>('personal')
  const [hiddenResourceIds, setHiddenResourceIds] = useState<string[]>([])
  const [conflictState, setConflictState] = useState<{
    payload: AppointmentCreateInput
    conflicts: ConflictReason[]
  } | null>(null)
  // Row-expansion key for the List sub-view -- plain appointment id for the
  // Personal-lens table, but the composite `${resourceId}-${id}` key for the
  // admin Resources-lens table, since one appointment using both a room and
  // equipment produces two rows sharing the same appointment id there (see
  // resourceCalendarEvents below, which already keys those rows the same way).
  const [expandedAppointmentId, setExpandedAppointmentId] = useState<string | null>(null)
  // Calendar sub-view has no "row" to expand underneath -- clicking an event
  // opens this appointment in a Modal instead (a "banner/window similar to
  // the New Appointment modal", per the user's request).
  const [viewingAppointment, setViewingAppointment] = useState<Appointment | null>(null)
  // Non-admin Resources lens has no real appointment to show for a busy
  // block -- just which student booked it. A Modal (not an auto-dismissing
  // toast) matches every other click-to-view interaction on this page and
  // doesn't disappear before the user reads it.
  const [viewingBookedBy, setViewingBookedBy] = useState<string | null>(null)

  // Deep-link support for WaitlistPage's "View appointment" button, which
  // can't navigate to a /appointments/:id route anymore (removed) -- it
  // instead links to /appointments?appointment=<id>, and this one-time
  // effect expands that row here. Self-terminating: clearing the param
  // makes the effect's own `if (id)` guard a no-op on the next run, so no
  // extra ref/flag is needed to prevent it firing again.
  useEffect(() => {
    const id = searchParams.get('appointment')
    if (id) {
      setViewMode('list')
      setExpandedAppointmentId(id)
      setSearchParams({}, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount only
  }, [])

  const isStudent = principal?.role === 'student'
  const isPatient = principal?.role === 'patient'
  const isAttending = principal?.role === 'attending'
  const isAdmin = principal?.role === 'admin'
  const canCreate = isStudent || isPatient
  // Resources deliberately excludes patients -- a patient has no reason to
  // see clinic-wide room/equipment usage, only their own appointments.
  const canSeeResources = isStudent || isAttending
  // Admin has no personal option at all -- it's always Resources, just
  // built from data admin already sees in full. Students/attendings pick
  // between Personal (default) and Resources; patients never leave
  // Personal.
  const effectiveLens: CalendarLens = isAdmin
    ? 'resources'
    : canSeeResources && calendarLens === 'resources'
      ? 'resources'
      : 'personal'

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
  // Fetched for every role now: the Resources lens's color legend/filter
  // chips need the active lists regardless of role, not just for the
  // student create-appointment form. Only ever the currently-active
  // resources -- deactivated ones with existing bookings are recovered
  // from the booking data itself instead, see combinedResourceOptions.
  const { data: rooms } = useQuery({
    queryKey: ['rooms'],
    queryFn: () => listActiveRooms(token),
  })
  const { data: equipment } = useQuery({
    queryKey: ['equipment'],
    queryFn: () => listActiveEquipment(token),
  })

  // Combined anonymized resource schedule -- only fetched for non-admin
  // roles, since admin's Resources lens reuses the already-fetched full
  // `appointments` list instead (see resourceCalendarEvents). Needed for
  // both List and Calendar sub-views now, not just Calendar.
  const { data: resourcesSchedule } = useQuery({
    queryKey: ['resources', 'schedule'],
    queryFn: () => getResourcesSchedule(token),
    enabled: !isAdmin && effectiveLens === 'resources',
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
    onError: (err, payload) => {
      if (err instanceof ApiError && err.status === 409 && err.conflicts?.length) {
        setConflictState({ payload, conflicts: err.conflicts })
        return
      }
      notifications.show({
        message: apiErrorMessage(err, 'Failed to create appointment'),
        color: 'red',
      })
    },
  })

  const joinWaitlistMutation = useMutation({
    mutationFn: (payload: AppointmentCreateInput) => joinWaitlist(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['waitlist'] })
      notifications.show({ message: 'Added to the waitlist', color: 'green' })
      setConflictState(null)
      form.reset()
      setDescribeText('')
      setInterpretWarnings([])
      close()
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to join the waitlist'),
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
    // Closing without submitting (X, Escape, backdrop click) never reset
    // the form -- the previously-picked patient/room/attending/notes were
    // still silently selected the next time this opened, a real risk of
    // submitting for the wrong patient without noticing.
    form.reset()
    setDescribeText('')
    setInterpretWarnings([])
    open()
  }

  function handleSelectSlot(slotInfo: SlotInfo) {
    // Only the personal lens represents "your own bookable calendar" --
    // the Resources lens is a read-only availability check, not a place to
    // start a new booking from.
    if (!canCreate || effectiveLens !== 'personal') return
    handleOpenModal()
    form.setValues({
      start_time: isoToMantineDateTime(slotInfo.start.toISOString()),
      end_time: isoToMantineDateTime(slotInfo.end.toISOString()),
    })
  }

  function handleSelectEvent(event: CalendarEventItem) {
    // Non-admin Resources lens has no real appointment to show -- clicking a
    // busy block instead reveals only which student booked it, never the
    // patient or any other detail. Admin's Resources events are full real
    // appointments (see resourceCalendarEvents), so they still open like
    // Personal ones.
    if (effectiveLens === 'resources' && !isAdmin) {
      setViewingBookedBy(event.studentName ?? null)
      return
    }
    setViewingAppointment(event.resource)
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

  // A cancelled appointment is done -- it holds no resource and is no
  // longer actionable, so it's dropped from the list/calendar entirely
  // rather than cluttering either view. Still reachable directly (e.g. via
  // a notification link) at /appointments/{id}, which shows its true
  // status unfiltered. Sorted ascending by start_time (soonest first) --
  // feeds both the Personal-lens table directly and, for admin, the
  // Resources-lens table via resourceCalendarEvents below.
  const visibleAppointments = useMemo(
    () =>
      (appointments ?? [])
        .filter((appointment) => appointment.status !== 'cancelled')
        .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()),
    [appointments],
  )

  // Personal lens: your own appointments, full detail -- unchanged from
  // before the Resources lens existed.
  const personalCalendarEvents = useMemo<CalendarEventItem[]>(
    () =>
      visibleAppointments.map((appointment) => ({
        id: appointment.id,
        title: `${appointment.patient_name} · ${appointment.status}`,
        start: new Date(appointment.start_time),
        end: new Date(appointment.end_time),
        resource: appointment,
      })),
    [visibleAppointments],
  )

  // Resources lens, both roles: one entry per resource actually occupied by
  // an appointment -- an appointment using both a room and equipment
  // produces two entries, one per resource, so filtering/coloring by
  // resourceId is always unambiguous (matches what /resources/schedule
  // already returns for the non-admin case below). Admin builds this
  // straight from the full appointment list it already has (full detail,
  // no anonymization); everyone else builds it from the anonymized
  // schedule endpoint.
  const resourceCalendarEvents = useMemo<CalendarEventItem[]>(() => {
    if (isAdmin) {
      const events: CalendarEventItem[] = []
      for (const appointment of visibleAppointments) {
        const title = `${appointment.patient_name} · ${appointment.status}`
        if (appointment.room_id) {
          events.push({
            id: appointment.id,
            title,
            start: new Date(appointment.start_time),
            end: new Date(appointment.end_time),
            resourceId: `room:${appointment.room_id}`,
            resourceName: appointment.room_name ?? undefined,
            resourceKind: 'room',
            resource: appointment,
            studentName: appointment.student_name,
          })
        }
        if (appointment.equipment_id) {
          events.push({
            id: appointment.id,
            title,
            start: new Date(appointment.start_time),
            end: new Date(appointment.end_time),
            resourceId: `equipment:${appointment.equipment_id}`,
            resourceName: appointment.equipment_name ?? undefined,
            resourceKind: 'equipment',
            resource: appointment,
            studentName: appointment.student_name,
          })
        }
      }
      return events
    }
    // Non-admin: no title text, since the resource name/color is the only
    // detail shown by default -- the booking student's name is only
    // revealed on click (Calendar) or as its own column (List), see
    // handleSelectEvent and the Resources list table below.
    return [...(resourcesSchedule ?? [])]
      .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime())
      .map((booking, index) => ({
        id: `resource-busy-${index}`,
        title: '',
        start: new Date(booking.start_time),
        end: new Date(booking.end_time),
        resourceId: `${booking.resource_kind}:${booking.resource_id}`,
        resourceName: booking.resource_name,
        resourceKind: booking.resource_kind,
        resource: null,
        studentName: booking.student_name,
      }))
  }, [isAdmin, visibleAppointments, resourcesSchedule])

  // Every currently-active room/equipment, plus any resource that's
  // deactivated but still has a booking showing in resourceCalendarEvents
  // above -- so a deactivated resource's past/future bookings keep a
  // stable color and a chip to toggle them, instead of losing their color
  // mapping the moment the resource itself is deactivated. A newly created
  // resource shows up immediately (as soon as `rooms`/`equipment` refetch),
  // with zero bookings, ready to be picked in the create-appointment form
  // and booked like any other.
  const combinedResourceOptions = useMemo<ResourceOption[]>(() => {
    const options = new Map<string, ResourceOption>()
    for (const room of rooms ?? []) {
      options.set(`room:${room.id}`, { resourceId: `room:${room.id}`, resourceTitle: `${room.name} (Room)` })
    }
    for (const item of equipment ?? []) {
      options.set(`equipment:${item.id}`, {
        resourceId: `equipment:${item.id}`,
        resourceTitle: `${item.name} (Equipment)`,
      })
    }
    for (const event of resourceCalendarEvents) {
      if (event.resourceId && event.resourceName && event.resourceKind && !options.has(event.resourceId)) {
        options.set(event.resourceId, {
          resourceId: event.resourceId,
          resourceTitle: `${event.resourceName} (${event.resourceKind === 'room' ? 'Room' : 'Equipment'})`,
        })
      }
    }
    return Array.from(options.values()).sort((a, b) => a.resourceTitle.localeCompare(b.resourceTitle))
  }, [rooms, equipment, resourceCalendarEvents])

  const isResourceLens = effectiveLens === 'resources'

  // Hashed by id, not by list position -- stays put across resource
  // create/deactivate/reactivate churn (see hashResourceColor above).
  const resourceColorNames = useMemo(
    () => Object.fromEntries(combinedResourceOptions.map((opt) => [opt.resourceId, hashResourceColor(opt.resourceId)])),
    [combinedResourceOptions],
  )

  const allEvents: CalendarEventItem[] =
    effectiveLens === 'resources' ? resourceCalendarEvents : personalCalendarEvents
  // Hidden-by-filter-chip events/rows are dropped entirely (not just
  // dimmed) -- applies to both the Resources list and calendar below. The
  // personal lens has no resourceId on its events, so it's unaffected.
  const visibleEvents = allEvents.filter(
    (event) => !event.resourceId || !hiddenResourceIds.includes(event.resourceId),
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
          {canSeeResources && (
            <SegmentedControl
              value={effectiveLens}
              onChange={(value) => setCalendarLens(value as CalendarLens)}
              data={[
                { label: 'Personal', value: 'personal' },
                { label: 'Resources', value: 'resources' },
              ]}
            />
          )}
          {canCreate && <Button onClick={handleOpenModal}>New Appointment</Button>}
        </Group>
      </Group>

      {isResourceLens && combinedResourceOptions.length > 0 && (
        <Chip.Group
          multiple
          value={combinedResourceOptions
            .map((opt) => opt.resourceId)
            .filter((id) => !hiddenResourceIds.includes(id))}
          onChange={(visibleIds) => {
            const hidden = combinedResourceOptions
              .map((opt) => opt.resourceId)
              .filter((id) => !visibleIds.includes(id))
            setHiddenResourceIds(hidden)
          }}
        >
          <Group gap="xs">
            {combinedResourceOptions.map((opt) => (
              <Chip
                key={opt.resourceId}
                value={opt.resourceId}
                color={resourceColorNames[opt.resourceId]}
              >
                {opt.resourceTitle}
              </Chip>
            ))}
          </Group>
        </Chip.Group>
      )}

      {isLoading ? (
        <LoadingText />
      ) : viewMode === 'list' && effectiveLens === 'personal' && visibleAppointments.length === 0 ? (
        <EmptyText>No appointments yet. Click "New Appointment" to create one.</EmptyText>
      ) : viewMode === 'list' && effectiveLens === 'personal' ? (
        <Table.ScrollContainer minWidth={800}>
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
                <Table.Th>Equipment</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {visibleAppointments.map((appointment) => {
                const expanded = expandedAppointmentId === appointment.id
                const toggle = () =>
                  setExpandedAppointmentId((current) =>
                    current === appointment.id ? null : appointment.id,
                  )
                return (
                  <Fragment key={appointment.id}>
                    <Table.Tr
                      style={{ cursor: 'pointer' }}
                      onClick={toggle}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          toggle()
                        }
                      }}
                      tabIndex={0}
                      role="button"
                      aria-expanded={expanded}
                    >
                      <Table.Td>{formatDateTime(appointment.start_time)}</Table.Td>
                      <Table.Td>{formatDateTime(appointment.end_time)}</Table.Td>
                      <Table.Td>
                        <Badge color={STATUS_COLORS[appointment.status]}>{appointment.status}</Badge>
                      </Table.Td>
                      <Table.Td>{appointment.student_name}</Table.Td>
                      <Table.Td>{appointment.patient_name}</Table.Td>
                      <Table.Td>{appointment.attending_name ?? '—'}</Table.Td>
                      <Table.Td>{appointment.room_name ?? '—'}</Table.Td>
                      <Table.Td>{appointment.equipment_name ?? '—'}</Table.Td>
                    </Table.Tr>
                    {expanded && (
                      <Table.Tr>
                        <Table.Td colSpan={8}>
                          <AppointmentDetailPanel
                            appointment={appointment}
                            attendings={attendings}
                            rooms={rooms}
                            equipment={equipment}
                          />
                        </Table.Td>
                      </Table.Tr>
                    )}
                  </Fragment>
                )
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      ) : viewMode === 'list' ? (
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
                </>
              ) : (
                <Table.Th>Booked by</Table.Th>
              )}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {visibleEvents.map((event) => {
              // One appointment using both a room and equipment produces two
              // rows here sharing the same event.id but different
              // resourceId (see resourceCalendarEvents' isAdmin branch) --
              // the expansion key must be the same composite string already
              // used for React's key, or clicking either row would expand
              // both. The bare-id fallback below only matters for the
              // Waitlist deep-link (which only knows the appointment id, not
              // which resource row it landed on); harmless in the rare
              // dual-resource case since both rows are then just correct.
              const compositeKey = `${event.resourceId}-${event.id}`
              const expanded =
                expandedAppointmentId === compositeKey || expandedAppointmentId === event.id
              const toggle = () =>
                setExpandedAppointmentId((current) => (current === compositeKey ? null : compositeKey))
              return (
                <Fragment key={compositeKey}>
                  <Table.Tr
                    style={isAdmin ? { cursor: 'pointer' } : undefined}
                    onClick={isAdmin ? toggle : undefined}
                    onKeyDown={
                      isAdmin
                        ? (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              toggle()
                            }
                          }
                        : undefined
                    }
                    tabIndex={isAdmin ? 0 : undefined}
                    role={isAdmin ? 'button' : undefined}
                    aria-expanded={isAdmin ? expanded : undefined}
                  >
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
                            <Badge color={STATUS_COLORS[event.resource.status]}>
                              {event.resource.status}
                            </Badge>
                          )}
                        </Table.Td>
                      </>
                    ) : (
                      <Table.Td>{event.studentName}</Table.Td>
                    )}
                  </Table.Tr>
                  {isAdmin && expanded && event.resource && (
                    <Table.Tr>
                      <Table.Td colSpan={7}>
                        <AppointmentDetailPanel
                          appointment={event.resource}
                          attendings={attendings}
                          rooms={rooms}
                          equipment={equipment}
                        />
                      </Table.Td>
                    </Table.Tr>
                  )}
                </Fragment>
              )
            })}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      ) : (
        // One flat calendar for every lens -- the Resources lens colors
        // events by resource (via the chips above) instead of splitting
        // into per-resource lanes, so every room/equipment's bookings are
        // visible together without any horizontal scrolling.
        <div style={{ height: 700 }}>
          <Calendar
            localizer={localizer}
            formats={CALENDAR_FORMATS}
            events={visibleEvents}
            views={['month', 'week', 'day']}
            view={calendarView}
            onView={setCalendarView}
            date={calendarDate}
            onNavigate={setCalendarDate}
            selectable={canCreate && effectiveLens === 'personal'}
            onSelectSlot={handleSelectSlot}
            onSelectEvent={handleSelectEvent}
            eventPropGetter={(event) => {
              const color =
                isResourceLens && event.resourceId
                  ? RESOURCE_COLOR_HEX[resourceColorNames[event.resourceId]]
                  : event.resource
                    ? STATUS_CSS_COLORS[event.resource.status]
                    : '#868e96'
              return { style: { backgroundColor: color } }
            }}
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
            <AppointmentDateTimeInput
              label="Start time"
              timeOptions={APPOINTMENT_START_TIME_OPTIONS}
              {...form.getInputProps('start_time')}
            />
            <AppointmentDateTimeInput
              label="End time"
              timeOptions={APPOINTMENT_END_TIME_OPTIONS}
              {...form.getInputProps('end_time')}
            />
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

      {conflictState && (
        <ConflictResolutionModal
          opened
          onClose={() => setConflictState(null)}
          conflicts={conflictState.conflicts}
          joining={joinWaitlistMutation.isPending}
          onJoinWaitlist={() => joinWaitlistMutation.mutate(conflictState.payload)}
        />
      )}

      <Modal
        opened={!!viewingAppointment}
        onClose={() => setViewingAppointment(null)}
        title="Appointment"
      >
        {viewingAppointment && (
          <AppointmentDetailPanel
            appointment={viewingAppointment}
            attendings={attendings}
            rooms={rooms}
            equipment={equipment}
            onActionSuccess={() => setViewingAppointment(null)}
          />
        )}
      </Modal>

      <Modal
        opened={!!viewingBookedBy}
        onClose={() => setViewingBookedBy(null)}
        title="Booked slot"
      >
        <Text>Booked by {viewingBookedBy}</Text>
      </Modal>
    </Stack>
  )
}
