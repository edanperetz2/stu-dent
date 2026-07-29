import { describe, expect, it } from 'vitest'
import { hashResourceColor } from './AppointmentsListPage'

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
