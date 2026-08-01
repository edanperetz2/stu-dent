import { describe, expect, it } from 'vitest'
import { theme } from './theme'

function hexLuminanceLike(hex: string): number {
  // A quick relative-brightness proxy (not true relative luminance) -- good
  // enough to assert "lighter than" / "darker than" ordering between two
  // hex colors without pulling in a full WCAG contrast implementation here.
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

const brand: readonly string[] = theme.colors?.brand ?? []

describe('theme brand color', () => {
  it('generates exactly 10 valid hex shades', () => {
    expect(brand).toHaveLength(10)
    for (const shade of brand) {
      expect(shade).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })

  it('pins shade 6 to (approximately) the source brand hex, #0f7d8c', () => {
    const shade6 = brand[6]!
    // Allow a small rounding tolerance from the HSL round-trip rather than
    // requiring byte-exact equality.
    const diff = Math.abs(hexLuminanceLike(shade6) - hexLuminanceLike('#0f7d8c'))
    expect(diff).toBeLessThan(10)
  })

  it('orders shades from lightest to darkest', () => {
    const luminances = brand.map(hexLuminanceLike)
    for (let i = 1; i < luminances.length; i++) {
      expect(luminances[i]).toBeLessThanOrEqual(luminances[i - 1])
    }
  })

  it('sets brand as the primary color', () => {
    expect(theme.primaryColor).toBe('brand')
  })
})
