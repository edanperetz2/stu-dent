import { describe, expect, it } from 'vitest'
import type { Appointment, Equipment, ResourceBooking, Room } from '../../api/types'
import {
  buildCombinedResourceOptions,
  buildPersonalCalendarEvents,
  buildResourceCalendarEvents,
  getCalendarViewRange,
  hashResourceColor,
} from './resourceColors'

function makeAppointment(overrides: Partial<Appointment> = {}): Appointment {
  return {
    id: 'appt-1',
    student_id: 'student-1',
    patient_id: 'patient-1',
    attending_id: null,
    room_id: null,
    equipment_id: null,
    start_time: '2026-01-01T09:00:00Z',
    end_time: '2026-01-01T10:00:00Z',
    status: 'confirmed',
    student_confirmed_at: null,
    attending_approved_at: null,
    notes: null,
    student_name: 'Student',
    patient_name: 'Patient',
    attending_name: null,
    room_name: null,
    equipment_name: null,
    ...overrides,
  }
}

describe('hashResourceColor', () => {
  it('is deterministic for the same id', () => {
    expect(hashResourceColor('room-123')).toBe(hashResourceColor('room-123'))
  })

  it('always returns one of the known palette colors', () => {
    const palette = new Set([
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
    ])
    for (const id of ['a', 'room-1', 'equipment-9', '00000000-0000-0000-0000-000000000000']) {
      expect(palette.has(hashResourceColor(id))).toBe(true)
    }
  })

  it('tends to differ for different ids (not a constant function)', () => {
    const colors = new Set(
      ['room-1', 'room-2', 'room-3', 'room-4', 'room-5', 'room-6'].map(hashResourceColor),
    )
    expect(colors.size).toBeGreaterThan(1)
  })
})

describe('buildPersonalCalendarEvents', () => {
  it('titles each event with the patient name and a humanized status', () => {
    const events = buildPersonalCalendarEvents([
      makeAppointment({ id: 'a1', patient_name: 'Jane Doe', status: 'no_show' }),
    ])
    expect(events).toHaveLength(1)
    expect(events[0]).toMatchObject({ id: 'a1', title: 'Jane Doe · No show' })
    expect(events[0].resource?.id).toBe('a1')
  })
})

describe('buildResourceCalendarEvents', () => {
  it('admin: emits one event per occupied resource, up to two per appointment', () => {
    const appointment = makeAppointment({
      id: 'a1',
      room_id: 'room-1',
      room_name: 'Room A',
      equipment_id: 'equip-1',
      equipment_name: 'X-Ray',
    })
    const events = buildResourceCalendarEvents({
      isAdmin: true,
      appointments: [appointment],
      resourcesSchedule: undefined,
    })
    expect(events).toHaveLength(2)
    expect(events.map((e) => e.resourceId)).toEqual(['room:room-1', 'equipment:equip-1'])
    expect(events.every((e) => e.resource?.id === 'a1')).toBe(true)
  })

  it('admin: an appointment holding no resource produces no event', () => {
    const events = buildResourceCalendarEvents({
      isAdmin: true,
      appointments: [makeAppointment({ room_id: null, equipment_id: null })],
      resourcesSchedule: undefined,
    })
    expect(events).toHaveLength(0)
  })

  it('non-admin: builds anonymized events from the resource schedule, sorted by start time, with no title and no resource', () => {
    const bookings: ResourceBooking[] = [
      {
        resource_kind: 'room',
        resource_id: 'room-1',
        resource_name: 'Room A',
        start_time: '2026-01-01T12:00:00Z',
        end_time: '2026-01-01T13:00:00Z',
        student_name: 'Student B',
      },
      {
        resource_kind: 'equipment',
        resource_id: 'equip-1',
        resource_name: 'X-Ray',
        start_time: '2026-01-01T09:00:00Z',
        end_time: '2026-01-01T10:00:00Z',
        student_name: 'Student A',
      },
    ]
    const events = buildResourceCalendarEvents({
      isAdmin: false,
      appointments: [],
      resourcesSchedule: bookings,
    })
    expect(events).toHaveLength(2)
    // Sorted ascending by start_time, not input order.
    expect(events[0].studentName).toBe('Student A')
    expect(events[1].studentName).toBe('Student B')
    expect(events.every((e) => e.title === '' && e.resource === null)).toBe(true)
  })

  it('non-admin: an undefined schedule (not yet loaded) produces no events, not a crash', () => {
    expect(
      buildResourceCalendarEvents({ isAdmin: false, appointments: [], resourcesSchedule: undefined }),
    ).toEqual([])
  })
})

describe('buildCombinedResourceOptions', () => {
  const rooms: Room[] = [{ id: 'room-1', name: 'Room A', is_active: true, inactive_until: null }]
  const equipment: Equipment[] = [
    { id: 'equip-1', name: 'X-Ray', equipment_type: null, is_active: true, inactive_until: null },
  ]

  it('lists every active room and equipment item, labeled by kind', () => {
    const options = buildCombinedResourceOptions({ rooms, equipment, resourceCalendarEvents: [] })
    expect(options.map((o) => o.resourceTitle)).toEqual(['Room A (Room)', 'X-Ray (Equipment)'])
  })

  it('recovers a deactivated resource from its own booking events, without duplicating an active one', () => {
    const options = buildCombinedResourceOptions({
      rooms,
      equipment,
      resourceCalendarEvents: [
        {
          id: 'a1',
          title: '',
          start: new Date(),
          end: new Date(),
          resourceId: 'room:room-2',
          resourceName: 'Room B (deactivated)',
          resourceKind: 'room',
          resource: null,
        },
        // Same resourceId as the already-active room-1 -- must not produce
        // a second, duplicate entry.
        {
          id: 'a2',
          title: '',
          start: new Date(),
          end: new Date(),
          resourceId: 'room:room-1',
          resourceName: 'Room A',
          resourceKind: 'room',
          resource: null,
        },
      ],
    })
    expect(options).toHaveLength(3)
    expect(options.map((o) => o.resourceId)).toContain('room:room-2')
    expect(options.filter((o) => o.resourceId === 'room:room-1')).toHaveLength(1)
  })

  it('sorts alphabetically by title', () => {
    const options = buildCombinedResourceOptions({
      rooms: [
        { id: 'z', name: 'Zebra Room', is_active: true, inactive_until: null },
        { id: 'a', name: 'Alpha Room', is_active: true, inactive_until: null },
      ],
      equipment: [],
      resourceCalendarEvents: [],
    })
    expect(options.map((o) => o.resourceTitle)).toEqual(['Alpha Room (Room)', 'Zebra Room (Room)'])
  })
})

describe('getCalendarViewRange', () => {
  it('spans just the day for day view', () => {
    const { start, end } = getCalendarViewRange(new Date(2026, 6, 15, 13, 0), 'day')
    expect(start.getDate()).toBe(15)
    expect(start.getHours()).toBe(0)
    expect(end.getDate()).toBe(15)
    expect(end.getHours()).toBe(23)
  })

  it('spans Sunday through Saturday for week view', () => {
    // 2026-07-15 is a Wednesday.
    const { start, end } = getCalendarViewRange(new Date(2026, 6, 15), 'week')
    expect(start.getDay()).toBe(0)
    expect(end.getDay()).toBe(6)
    expect(start.getDate()).toBe(12)
    expect(end.getDate()).toBe(18)
  })

  it('pads month view out to full weeks, including adjacent-month days', () => {
    // 2026-07-01 is a Wednesday, so the grid must include the trailing
    // days of June to complete that first week.
    const { start, end } = getCalendarViewRange(new Date(2026, 6, 15), 'month')
    expect(start.getMonth()).toBe(5) // June
    expect(start.getDay()).toBe(0)
    expect(end.getDay()).toBe(6)
  })
})
