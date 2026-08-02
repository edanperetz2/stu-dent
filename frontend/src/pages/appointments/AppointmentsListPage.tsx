import {
  ActionIcon,
  Button,
  Chip,
  Collapse,
  Fieldset,
  Group,
  Modal,
  Select,
  SegmentedControl,
  Skeleton,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { IconSortAscending, IconSortDescending } from '@tabler/icons-react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { SlotInfo, View } from 'react-big-calendar'
import { useSearchParams } from 'react-router-dom'
import { listAppointments, type AppointmentCreateInput } from '../../api/appointments'
import { listAttendings } from '../../api/attendings'
import { listActiveEquipment } from '../../api/equipment'
import { listPatients } from '../../api/patients'
import { getResourcesSchedule } from '../../api/resources'
import { listActiveRooms } from '../../api/rooms'
import type { Appointment, AppointmentStatus } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { AppointmentDateTimeInput } from '../../components/AppointmentDateTimeInput'
import { ConflictResolutionModal } from '../../components/ConflictResolutionModal'
import { TableSkeleton } from '../../components/Skeletons'
import { EmptyText, ErrorText } from '../../components/StateText'
import { useListQuery } from '../../hooks/useListQuery'
import {
  addMinutesToMantineDateTime,
  APPOINTMENT_END_TIME_OPTIONS,
  APPOINTMENT_START_TIME_OPTIONS,
  formatDateTime,
  isoToMantineDateTime,
  mantineDateTimeToIso,
} from '../../utils/dates'
import { AppointmentDetailPanel } from './AppointmentDetailPanel'
import { AppointmentsCalendarView } from './AppointmentsCalendarView'
import { statusLabel } from './appointmentActions'
import { PersonalAppointmentsTable } from './PersonalAppointmentsTable'
import { ResourceAppointmentsTable } from './ResourceAppointmentsTable'
import {
  buildCombinedResourceOptions,
  buildPersonalCalendarEvents,
  buildResourceCalendarEvents,
  getCalendarViewRange,
  hashResourceColor,
  type CalendarEventItem,
} from './resourceColors'
import { useAppointmentActions, type CreateFormValues } from './useAppointmentActions'

// What the calendar/list view is currently showing: the signed-in user's own
// appointments (default, status-colored), or a clinic-wide resource view --
// every room+equipment booking, colored per resource instead of per status.
// Patients only ever get 'personal'. Students/attendings can switch to
// 'resources', which is anonymized (reveals only which student booked a
// slot, never the patient) via the /resources/schedule endpoint. Admin only
// ever gets 'resources' too, but built from the full appointment list it
// already has -- same shape, full detail, no anonymization.
type CalendarLens = 'personal' | 'resources'

// Duration shortcut chips on the New Appointment modal's "When" fieldset --
// 'custom' falls back to a second explicit end-time picker; the preset
// minute counts drive addMinutesToMantineDateTime directly off whatever
// start time is picked, so the end time never needs a second manual entry
// for the common cases. Only multiples of 30 belong here -- every start
// time is itself on the half-hour grid (APPOINTMENT_START_TIME_OPTIONS),
// and APPOINTMENT_END_TIME_OPTIONS only offers half-hour slots too, so a
// non-30-multiple preset (45 min was here once) computes an end time the
// Select can't represent as selected once a user switches to Custom.
type DurationMode = '30' | '60' | 'custom'
const DURATION_MINUTES: Record<Exclude<DurationMode, 'custom'>, number> = {
  '30': 30,
  '60': 60,
}

// 'cancelled' is deliberately excluded -- the appointments query always
// excludes cancelled rows server-side now, so filtering by it would only
// ever produce an empty, confusing result.
const STATUS_FILTER_OPTIONS: { value: AppointmentStatus; label: string }[] = (
  ['proposed', 'awaiting_confirmation', 'confirmed', 'rescheduling_requested', 'completed', 'no_show'] as const
).map((status) => ({ value: status, label: statusLabel(status) }))

type SortField = 'start_time' | 'status' | 'patient_name' | 'student_name'
const SORT_FIELD_OPTIONS: { value: SortField; label: string }[] = [
  { value: 'start_time', label: 'Start time' },
  { value: 'status', label: 'Status' },
  { value: 'patient_name', label: 'Patient' },
  { value: 'student_name', label: 'Student' },
]

export function AppointmentsListPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [opened, { open, close }] = useDisclosure(false)
  const [durationMode, setDurationMode] = useState<DurationMode>('30')
  const [moreOptionsOpened, { toggle: toggleMoreOptions, close: closeMoreOptions }] = useDisclosure(false)
  const [describeMode, { toggle: toggleDescribeMode, close: closeDescribeMode }] = useDisclosure(false)
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list')
  const [calendarView, setCalendarView] = useState<View>('week')
  const [calendarDate, setCalendarDate] = useState(new Date())
  const [calendarLens, setCalendarLens] = useState<CalendarLens>('personal')
  const [hiddenResourceIds, setHiddenResourceIds] = useState<string[]>([])
  // Search/status-filter/sort only apply to the Personal-lens List
  // sub-view -- the Resources lens already has its own resource-identity
  // filter chips, and the Calendar sub-view has no table to sort/search.
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<AppointmentStatus | null>(null)
  const [sortField, setSortField] = useState<SortField>('start_time')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  // Row-expansion key for the List sub-view -- plain appointment id for the
  // Personal-lens table, but the composite `${resourceId}-${id}` key for the
  // admin Resources-lens table, since one appointment using both a room and
  // equipment produces two rows sharing the same appointment id there (see
  // resourceColors.ts's buildResourceCalendarEvents).
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

  // Only the Calendar sub-view has a well-defined "on-screen" date window
  // (month/week/day, from calendarView+calendarDate) -- the List sub-view
  // shows a flat table with no inherent range, so it keeps requesting
  // everything (up to the backend's own cap) rather than being scoped to a
  // window it has no UI to represent.
  const calendarRange = useMemo(
    () => (viewMode === 'calendar' ? getCalendarViewRange(calendarDate, calendarView) : null),
    [viewMode, calendarDate, calendarView],
  )

  // isEmpty always false -- this page's own content branches below (list vs
  // calendar, personal vs resources lens) each render their own empty
  // state, since "empty" means something different in each of them.
  const appointmentsQuery = useListQuery({
    queryKey: ['appointments', calendarRange?.start.toISOString(), calendarRange?.end.toISOString()],
    queryFn: () =>
      listAppointments(token, {
        startAfter: calendarRange?.start.toISOString(),
        startBefore: calendarRange?.end.toISOString(),
        excludeCancelled: true,
      }),
    errorFallback: 'Failed to load appointments.',
    isEmpty: () => false,
  })
  const appointments = appointmentsQuery.status === 'ready' ? appointmentsQuery.data : undefined

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
  // from the booking data itself instead, see buildCombinedResourceOptions.
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
  // `appointments` list instead (see buildResourceCalendarEvents). Needed
  // for both List and Calendar sub-views now, not just Calendar.
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

  const {
    describeText,
    setDescribeText,
    interpretWarnings,
    resetInterpretState,
    conflictState,
    setConflictState,
    createMutation,
    joinWaitlistMutation,
    interpretMutation,
  } = useAppointmentActions({
    token,
    form,
    onSubmitSuccess: close,
    // The interpreted start/end times are a specific pair, not "start time
    // + a round duration" -- switch to Custom so the duration-sync effect
    // below doesn't immediately overwrite the interpreted end time.
    onInterpretApplied: () => setDurationMode('custom'),
  })

  // Keeps end_time in lockstep with start_time while a duration preset is
  // active, so picking a later start time doesn't leave a stale end time
  // behind -- skipped entirely once the user picks Custom.
  useEffect(() => {
    if (durationMode === 'custom') return
    const start = form.values.start_time
    if (!start) return
    const nextEnd = addMinutesToMantineDateTime(start, DURATION_MINUTES[durationMode])
    if (nextEnd !== form.values.end_time) {
      form.setFieldValue('end_time', nextEnd)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-sync on start_time/durationMode, not on end_time (which this effect itself sets) or form identity
  }, [form.values.start_time, durationMode])

  function handleOpenModal() {
    // Closing without submitting (X, Escape, backdrop click) never reset
    // the form -- the previously-picked patient/room/attending/notes were
    // still silently selected the next time this opened, a real risk of
    // submitting for the wrong patient without noticing. Same reasoning
    // now covers the modal's own UI state (duration mode, collapsed
    // sections, describe-instead mode).
    form.reset()
    resetInterpretState()
    setDurationMode('30')
    closeMoreOptions()
    closeDescribeMode()
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
    // A drag-selected slot is already an exact start/end pair, same reason
    // as the interpret path above -- don't let a duration preset clobber it.
    setDurationMode('custom')
  }

  function handleSelectEvent(event: CalendarEventItem) {
    // Non-admin Resources lens has no real appointment to show -- clicking a
    // busy block instead reveals only which student booked it, never the
    // patient or any other detail. Admin's Resources events are full real
    // appointments (see buildResourceCalendarEvents), so they still open
    // like Personal ones.
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

  // Cancelled appointments are excluded server-side now (exclude_cancelled
  // on the query above). Search/status-filter only apply to the
  // Personal-lens List sub-view (see the state comment above); every other
  // view gets the full fetched set, sorted -- default sort matches the
  // page's original fixed behavior (ascending by start_time), so switching
  // to Calendar or the Resources lens is unaffected by whatever sort/filter
  // was left set on the Personal List table. Feeds both the Personal-lens
  // table directly and, for admin, the Resources-lens table via
  // buildResourceCalendarEvents below.
  const visibleAppointments = useMemo(() => {
    let list = appointments ?? []
    if (viewMode === 'list' && effectiveLens === 'personal') {
      const query = searchQuery.trim().toLowerCase()
      if (query) {
        list = list.filter((appointment) =>
          [
            appointment.patient_name,
            appointment.student_name,
            appointment.attending_name,
            appointment.room_name,
            appointment.equipment_name,
          ]
            .filter((field): field is string => !!field)
            .some((field) => field.toLowerCase().includes(query)),
        )
      }
      if (statusFilter) {
        list = list.filter((appointment) => appointment.status === statusFilter)
      }
    }
    const direction = sortDirection === 'asc' ? 1 : -1
    return [...list].sort((a, b) => {
      if (sortField === 'start_time') {
        return (new Date(a.start_time).getTime() - new Date(b.start_time).getTime()) * direction
      }
      return a[sortField].localeCompare(b[sortField]) * direction
    })
  }, [appointments, viewMode, effectiveLens, searchQuery, statusFilter, sortField, sortDirection])

  const personalCalendarEvents = useMemo(
    () => buildPersonalCalendarEvents(visibleAppointments),
    [visibleAppointments],
  )

  const resourceCalendarEvents = useMemo(
    () => buildResourceCalendarEvents({ isAdmin, appointments: visibleAppointments, resourcesSchedule }),
    [isAdmin, visibleAppointments, resourcesSchedule],
  )

  const combinedResourceOptions = useMemo(
    () => buildCombinedResourceOptions({ rooms, equipment, resourceCalendarEvents }),
    [rooms, equipment, resourceCalendarEvents],
  )

  const isResourceLens = effectiveLens === 'resources'

  // Hashed by id, not by list position -- stays put across resource
  // create/deactivate/reactivate churn (see resourceColors.ts).
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

  let content: ReactNode
  if (appointmentsQuery.status === 'error') {
    content = <ErrorText onRetry={appointmentsQuery.retry}>{appointmentsQuery.message}</ErrorText>
  } else if (appointmentsQuery.status === 'loading') {
    content =
      viewMode === 'calendar' ? (
        <Skeleton height={700} />
      ) : (
        <TableSkeleton columns={effectiveLens === 'personal' ? 5 : isAdmin ? 8 : 5} />
      )
  } else if (viewMode === 'list' && effectiveLens === 'personal') {
    content =
      visibleAppointments.length === 0 ? (
        <EmptyText>
          {searchQuery.trim() || statusFilter
            ? 'No appointments match your search/filter.'
            : 'No appointments yet. Click "New Appointment" to create one.'}
        </EmptyText>
      ) : (
        <PersonalAppointmentsTable
          appointments={visibleAppointments}
          attendings={attendings}
          rooms={rooms}
          equipment={equipment}
          expandedId={expandedAppointmentId}
          onToggleExpand={(id) =>
            setExpandedAppointmentId((current) => (current === id ? null : id))
          }
          viewerRole={principal!.role}
          groupByDay={sortField === 'start_time'}
        />
      )
  } else if (viewMode === 'list') {
    content = (
      <ResourceAppointmentsTable
        events={visibleEvents}
        isAdmin={isAdmin}
        attendings={attendings}
        rooms={rooms}
        equipment={equipment}
        expandedId={expandedAppointmentId}
        onToggleExpand={(compositeKey) =>
          setExpandedAppointmentId((current) => (current === compositeKey ? null : compositeKey))
        }
      />
    )
  } else {
    content = (
      <AppointmentsCalendarView
        events={visibleEvents}
        view={calendarView}
        onViewChange={setCalendarView}
        date={calendarDate}
        onNavigate={setCalendarDate}
        selectable={canCreate && effectiveLens === 'personal'}
        onSelectSlot={handleSelectSlot}
        onSelectEvent={handleSelectEvent}
        isResourceLens={isResourceLens}
        resourceColorNames={resourceColorNames}
      />
    )
  }

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

      {viewMode === 'list' && effectiveLens === 'personal' && (
        <Group align="flex-end">
          <TextInput
            label="Search"
            placeholder="Patient, student, attending, room, equipment..."
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.currentTarget.value)}
            flex={1}
            miw={200}
          />
          <Select
            label="Status"
            placeholder="All statuses"
            data={STATUS_FILTER_OPTIONS}
            value={statusFilter}
            onChange={(value) => setStatusFilter(value as AppointmentStatus | null)}
            clearable
            w={180}
          />
          <Select
            label="Sort by"
            data={SORT_FIELD_OPTIONS}
            value={sortField}
            onChange={(value) => value && setSortField(value as SortField)}
            allowDeselect={false}
            w={160}
          />
          <ActionIcon
            variant="default"
            size="lg"
            aria-label={sortDirection === 'asc' ? 'Sort ascending' : 'Sort descending'}
            onClick={() => setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))}
          >
            {sortDirection === 'asc' ? (
              <IconSortAscending size={18} />
            ) : (
              <IconSortDescending size={18} />
            )}
          </ActionIcon>
        </Group>
      )}

      {content}

      <Modal opened={opened} onClose={close} title="New Appointment" size="lg">
        <Button
          type="button"
          variant="subtle"
          size="xs"
          onClick={toggleDescribeMode}
          mb={describeMode ? 'xs' : 'md'}
        >
          {describeMode ? 'Fill in the form manually instead' : 'Describe it in your own words instead'}
        </Button>
        <Collapse expanded={describeMode}>
          <Stack mb="md">
            <Textarea
              label="Describe it in your own words"
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
        </Collapse>

        {/* A plain <form>, not a Mantine component -- no flex/miw/mah shorthand props apply to it. */}
        <form onSubmit={form.onSubmit(handleSubmit)} style={{ display: 'flex', flexDirection: 'column' }}>
          {/* overflowY has no Mantine shorthand; mah covers max-height. */}
          <Stack mah="55vh" style={{ overflowY: 'auto' }} pb="sm" pr={4}>
            {isStudent && (
              <Fieldset legend="Who">
                <Select
                  label="Patient"
                  withAsterisk
                  data={patientOptions}
                  {...form.getInputProps('patient_id')}
                />
              </Fieldset>
            )}

            <Fieldset legend="When">
              <Stack gap="sm">
                <AppointmentDateTimeInput
                  label="Start time"
                  required
                  timeOptions={APPOINTMENT_START_TIME_OPTIONS}
                  {...form.getInputProps('start_time')}
                />
                <div>
                  <Text size="sm" fw={500} mb={4}>
                    Duration
                  </Text>
                  <Chip.Group
                    value={durationMode}
                    onChange={(value) => setDurationMode(value as DurationMode)}
                  >
                    <Group gap="xs">
                      <Chip value="30">30 min</Chip>
                      <Chip value="60">60 min</Chip>
                      <Chip value="custom">Custom</Chip>
                    </Group>
                  </Chip.Group>
                </div>
                {durationMode === 'custom' ? (
                  <AppointmentDateTimeInput
                    label="End time"
                    required
                    timeOptions={APPOINTMENT_END_TIME_OPTIONS}
                    {...form.getInputProps('end_time')}
                  />
                ) : (
                  form.values.end_time && (
                    <Text size="sm" c="dimmed">
                      Ends at {formatDateTime(form.values.end_time)}
                    </Text>
                  )
                )}
              </Stack>
            </Fieldset>

            {isStudent && (
              <Fieldset legend="Where">
                <Select
                  label="Room"
                  withAsterisk
                  data={roomOptions}
                  {...form.getInputProps('room_id')}
                />
              </Fieldset>
            )}

            {isStudent ? (
              <>
                <Button
                  type="button"
                  variant="subtle"
                  size="xs"
                  onClick={toggleMoreOptions}
                  // No Mantine shorthand for align-self.
                  style={{ alignSelf: 'flex-start' }}
                >
                  {moreOptionsOpened ? 'Fewer options' : 'More options (attending, equipment, notes)'}
                </Button>
                <Collapse expanded={moreOptionsOpened}>
                  <Stack gap="sm">
                    <Select
                      label="Attending"
                      data={attendingOptions}
                      clearable
                      {...form.getInputProps('attending_id')}
                    />
                    <Select
                      label="Equipment"
                      data={equipmentOptions}
                      clearable
                      {...form.getInputProps('equipment_id')}
                    />
                    <Textarea label="Notes" {...form.getInputProps('notes')} />
                  </Stack>
                </Collapse>
              </>
            ) : (
              <Textarea label="Notes" {...form.getInputProps('notes')} />
            )}
          </Stack>

          {/* No Mantine shorthand for a single border side (`bd` sets all four). */}
          <Group
            justify="flex-end"
            pt="sm"
            style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}
          >
            <Button type="submit" loading={createMutation.isPending}>
              Request
            </Button>
          </Group>
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
        size="md"
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
        size="sm"
      >
        <Text>Booked by {viewingBookedBy}</Text>
      </Modal>
    </Stack>
  )
}
