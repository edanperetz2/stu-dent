import dayjs from 'dayjs'
import type { View } from 'react-big-calendar'
import type { Appointment, Equipment, ResourceBooking, Room } from '../../api/types'
import { statusLabel } from './appointmentActions'

/** The date range react-big-calendar is currently showing for a given
 * `view`/`date` pair -- month view pads out to full weeks (matching what
 * the grid actually renders, including the leading/trailing days from
 * adjacent months), week/day don't need padding. Backs the appointments
 * query's start_after/start_before params so the Calendar sub-view only
 * fetches what's actually on screen instead of every appointment ever
 * made. */
// Matches react-big-calendar's own Agenda.range(date, {length}) exactly
// (Agenda.js: `[date, add(date, length, 'day')]`, not week-aligned) -- the
// AppointmentsCalendarView must pass the same `length` to <Calendar>, or
// the two silently disagree about the window and Agenda renders days with
// no data fetched for them at all (indistinguishable from "no
// appointments").
export const AGENDA_LENGTH_DAYS = 7

export function getCalendarViewRange(date: Date, view: View): { start: Date; end: Date } {
  const anchor = dayjs(date)
  switch (view) {
    case 'month':
      return {
        start: anchor.startOf('month').startOf('week').toDate(),
        end: anchor.endOf('month').endOf('week').toDate(),
      }
    case 'day':
      return { start: anchor.startOf('day').toDate(), end: anchor.endOf('day').toDate() }
    case 'agenda':
      return {
        start: anchor.startOf('day').toDate(),
        end: anchor.startOf('day').add(AGENDA_LENGTH_DAYS, 'day').toDate(),
      }
    case 'week':
    default:
      return { start: anchor.startOf('week').toDate(), end: anchor.endOf('week').toDate() }
  }
}

// A stable palette so each resource gets a distinct color -- looked up by
// hashing the resourceId (see hashResourceColor) rather than by its
// position in a list, so a resource's color never shifts just because
// another resource was added, deactivated, or reactivated. Mantine's
// <Chip color> wants just the theme color name; react-big-calendar's
// eventPropGetter needs a real CSS hex value, looked up from the theme
// itself (via useMantineTheme() at the render site) rather than a second
// hand-maintained parallel hex map that could drift out of sync with this.
export const RESOURCE_COLOR_NAMES = [
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

export function hashResourceColor(resourceId: string): (typeof RESOURCE_COLOR_NAMES)[number] {
  let hash = 0
  for (let i = 0; i < resourceId.length; i++) {
    hash = (hash * 31 + resourceId.charCodeAt(i)) | 0
  }
  return RESOURCE_COLOR_NAMES[Math.abs(hash) % RESOURCE_COLOR_NAMES.length]
}

export interface ResourceOption {
  resourceId: string
  resourceTitle: string
}

// `resource` is null for the anonymized Resources-lens busy-window events
// (no real appointment behind them for a non-admin viewer) -- `studentName`
// covers that case instead. `resourceId`/`resourceName`/`resourceKind` are
// only set for Resources-lens events; they drive the color, the show/hide
// filter chips, and the List view's columns.
export interface CalendarEventItem {
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

/** Personal lens: the viewer's own appointments, full detail. */
export function buildPersonalCalendarEvents(appointments: Appointment[]): CalendarEventItem[] {
  return appointments.map((appointment) => ({
    id: appointment.id,
    title: `${appointment.patient_name} · ${statusLabel(appointment.status)}`,
    start: new Date(appointment.start_time),
    end: new Date(appointment.end_time),
    resource: appointment,
  }))
}

/** Resources lens, both roles: one entry per resource actually occupied by
 * an appointment -- an appointment using both a room and equipment
 * produces two entries, one per resource, so filtering/coloring by
 * resourceId is always unambiguous (matches what /resources/schedule
 * already returns for the non-admin case below). Admin builds this
 * straight from the full appointment list it already has (full detail, no
 * anonymization); everyone else builds it from the anonymized schedule
 * endpoint. */
export function buildResourceCalendarEvents({
  isAdmin,
  appointments,
  resourcesSchedule,
}: {
  isAdmin: boolean
  appointments: Appointment[]
  resourcesSchedule: ResourceBooking[] | undefined
}): CalendarEventItem[] {
  if (isAdmin) {
    const events: CalendarEventItem[] = []
    for (const appointment of appointments) {
      const title = `${appointment.patient_name} · ${statusLabel(appointment.status)}`
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
  // detail shown by default -- the booking student's name is only revealed
  // on click (Calendar) or as its own column (List).
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
}

/** Every currently-active room/equipment, plus any resource that's
 * deactivated but still has a booking showing in `resourceCalendarEvents`
 * -- so a deactivated resource's past/future bookings keep a stable color
 * and a chip to toggle them, instead of losing their color mapping the
 * moment the resource itself is deactivated. A newly created resource
 * shows up immediately (as soon as rooms/equipment refetch), with zero
 * bookings, ready to be picked in the create-appointment form and booked
 * like any other. */
export function buildCombinedResourceOptions({
  rooms,
  equipment,
  resourceCalendarEvents,
}: {
  rooms: Room[] | undefined
  equipment: Equipment[] | undefined
  resourceCalendarEvents: CalendarEventItem[]
}): ResourceOption[] {
  const options = new Map<string, ResourceOption>()
  for (const room of rooms ?? []) {
    options.set(`room:${room.id}`, {
      resourceId: `room:${room.id}`,
      resourceTitle: `${room.name} (Room)`,
    })
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
}
