import { describe, expect, it } from 'vitest'
import { isoToMantineDateTime, mantineDateTimeToIso } from './dates'

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
