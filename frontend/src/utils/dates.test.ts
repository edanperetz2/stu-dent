import { describe, expect, it } from 'vitest'
import {
  addMinutesToMantineDateTime,
  formatDateTime,
  isoToMantineDateTime,
  mantineDateTimeToIso,
} from './dates'

describe('mantineDateTimeToIso', () => {
  it('converts a Mantine local-time string into a valid ISO string', () => {
    const iso = mantineDateTimeToIso('2026-07-15 09:30:00')
    // Round-trips through a real Date -- this is what a naive
    // `value.toISOString()` call would have thrown on, since Mantine's
    // DateTimePicker onChange emits this string shape, not a Date.
    expect(new Date(iso).toString()).not.toBe('Invalid Date')
    expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/)
  })
})

describe('isoToMantineDateTime', () => {
  it('round-trips back to the same wall-clock value mantineDateTimeToIso produced', () => {
    const original = '2026-07-15 09:30:00'
    const iso = mantineDateTimeToIso(original)
    expect(isoToMantineDateTime(iso)).toBe(original)
  })

  it('formats an ISO string from the backend into the expected Mantine shape', () => {
    const local = isoToMantineDateTime(new Date(2026, 0, 5, 8, 5, 0).toISOString())
    expect(local).toBe('2026-01-05 08:05:00')
  })
})

describe('addMinutesToMantineDateTime', () => {
  it('adds minutes within the same day', () => {
    expect(addMinutesToMantineDateTime('2026-07-15 09:30:00', 30)).toBe('2026-07-15 10:00:00')
  })

  it('rolls over into the next day when the addition crosses midnight', () => {
    expect(addMinutesToMantineDateTime('2026-07-15 23:45:00', 30)).toBe('2026-07-16 00:15:00')
  })
})

describe('formatDateTime', () => {
  it('formats a date as dd/mm/yy HH:mm, day-first and 24-hour, no seconds or timezone', () => {
    // 2026-08-05, 14:05 local time -- if this were rendered with the
    // browser-locale-dependent .toLocaleString() it replaces, a US-locale
    // browser would show "8/5/2026, 2:05:00 PM" instead.
    const formatted = formatDateTime(new Date(2026, 7, 5, 14, 5, 0).toISOString())
    expect(formatted).toBe('05/08/26 14:05')
  })

  it('pads single-digit hours to 24-hour format instead of using AM/PM', () => {
    const formatted = formatDateTime(new Date(2026, 0, 1, 9, 0, 0).toISOString())
    expect(formatted).toBe('01/01/26 09:00')
  })

  it('accepts a plain Date object as well as an ISO string', () => {
    const date = new Date(2026, 11, 31, 23, 59, 0)
    expect(formatDateTime(date)).toBe('31/12/26 23:59')
  })
})
