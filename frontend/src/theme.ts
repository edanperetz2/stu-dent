import { createTheme, Modal, type MantineColorsTuple } from '@mantine/core'

// The brand ink navy, from the logo -- also reused directly (not through
// the theme) as the text color for status badges (see
// pages/appointments/appointmentActions.ts) since it reliably passes WCAG
// AA against any pale badge background regardless of hue, unlike trying to
// pick a matching dark shade per status color individually.
export const BRAND_INK = '#103f5c'

function hexToHsl(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16) / 255
  const g = parseInt(hex.slice(3, 5), 16) / 255
  const b = parseInt(hex.slice(5, 7), 16) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  const d = max - min
  let h = 0
  let s = 0
  if (d !== 0) {
    s = d / (1 - Math.abs(2 * l - 1))
    if (max === r) h = ((g - b) / d) % 6
    else if (max === g) h = (b - r) / d + 2
    else h = (r - g) / d + 4
    h *= 60
    if (h < 0) h += 360
  }
  return [h, s, l]
}

/** Exported for appointmentActions.ts's status-color generation (one hue
 * per status -> both the pale badge and saturated calendar shades), so
 * that code doesn't need its own copy of the same HSL->hex conversion. */
export function hslToHex(h: number, s: number, l: number): string {
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = l - c / 2
  let [r, g, b] = [0, 0, 0]
  if (h < 60) [r, g, b] = [c, x, 0]
  else if (h < 120) [r, g, b] = [x, c, 0]
  else if (h < 180) [r, g, b] = [0, c, x]
  else if (h < 240) [r, g, b] = [0, x, c]
  else if (h < 300) [r, g, b] = [x, 0, c]
  else [r, g, b] = [c, 0, x]
  const toHex = (v: number) =>
    Math.round((v + m) * 255)
      .toString(16)
      .padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

/** Derives a full 10-shade Mantine color tuple from a single brand hex,
 * instead of hand-picking 10 approximate values -- shade 6 (Mantine's
 * default light-mode `primaryShade`) is pinned to the exact input lightness
 * so the color actually shown in normal UI (buttons, links, focus rings)
 * matches the logo precisely, not an approximation of it. */
function generateShades(baseHex: string): MantineColorsTuple {
  const [h, s, baseL] = hexToHsl(baseHex)
  const clamp = (l: number) => Math.min(0.97, Math.max(0.06, l))
  const lightnesses = [
    0.95,
    0.88,
    0.78,
    0.66,
    0.54,
    0.44,
    baseL,
    baseL * 0.78,
    baseL * 0.6,
    baseL * 0.42,
  ]
  return lightnesses.map((l) => hslToHex(h, s, clamp(l))) as unknown as MantineColorsTuple
}

const brand = generateShades('#0f7d8c')

export const theme = createTheme({
  primaryColor: 'brand',
  colors: { brand },
  headings: { fontWeight: '600' },
  components: {
    // Mantine's own Modal close button ships with no aria-label by
    // default (confirmed by inspecting the rendered DOM -- it's just an
    // unlabeled icon button) -- a screen reader announces it as nothing
    // more than "button". Set once here instead of on all 16 <Modal>
    // call sites individually.
    Modal: Modal.extend({ defaultProps: { closeButtonProps: { 'aria-label': 'Close' } } }),
  },
})
