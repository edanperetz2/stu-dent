import { describe, expect, it } from 'vitest'
import { contrastRatio, maxLightnessForContrast, MIN_AA_CONTRAST } from './colorContrast'

describe('contrastRatio', () => {
  it('returns 21:1 for pure black against pure white (the WCAG maximum)', () => {
    expect(contrastRatio('#000000', '#ffffff')).toBeCloseTo(21, 0)
  })

  it('returns 1:1 for a color against itself', () => {
    expect(contrastRatio('#3388ff', '#3388ff')).toBeCloseTo(1, 5)
  })

  it('is symmetric regardless of argument order', () => {
    const ab = contrastRatio('#123456', '#fedcba')
    const ba = contrastRatio('#fedcba', '#123456')
    expect(ab).toBeCloseTo(ba, 10)
  })
})

describe('maxLightnessForContrast', () => {
  // A trivial toHex stand-in: ignores hue/saturation, maps lightness
  // linearly to a gray shade -- lets this test the binary search's own
  // convergence logic without depending on the real HSL-to-hex conversion.
  function grayAtLightness(_hue: number, _saturation: number, lightness: number): string {
    const channel = Math.round(lightness * 255)
      .toString(16)
      .padStart(2, '0')
    return `#${channel}${channel}${channel}`
  }

  it('finds a lightness whose contrast against white meets the target ratio', () => {
    const lightness = maxLightnessForContrast(0, 0, grayAtLightness, '#ffffff')
    const achieved = contrastRatio(grayAtLightness(0, 0, lightness), '#ffffff')
    expect(achieved).toBeGreaterThanOrEqual(MIN_AA_CONTRAST)
  })

  it('returns the highest lightness that still clears the ratio, not an overly conservative one', () => {
    const lightness = maxLightnessForContrast(0, 0, grayAtLightness, '#ffffff')
    // One step lighter should just barely fail (or be very close to
    // failing) -- proves the binary search converges near the boundary
    // instead of stopping arbitrarily early.
    const oneStepLighter = Math.min(lightness + 0.01, 1)
    const achieved = contrastRatio(grayAtLightness(0, 0, oneStepLighter), '#ffffff')
    expect(achieved).toBeLessThan(MIN_AA_CONTRAST + 0.5)
  })

  it('never loops forever or returns an out-of-range lightness (0.05-0.6 search bounds)', () => {
    const lightness = maxLightnessForContrast(0, 0, grayAtLightness, '#ffffff', 100)
    expect(lightness).toBeGreaterThanOrEqual(0.05)
    expect(lightness).toBeLessThanOrEqual(0.6)
  })
})
