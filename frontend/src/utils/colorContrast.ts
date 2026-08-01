/** WCAG relative-luminance + contrast-ratio math, plus a binary search for
 * the highest lightness (at a fixed hue/saturation) that still clears a
 * target contrast ratio against white text. Shared by appointmentActions.ts
 * (7-status hue table) and WaitlistPage.tsx (3-status hue table) so both
 * generate their dark-mode saturated badge shade the same, AA-verified way
 * instead of each hand-picking one -- the earlier hand-fix (#f59f00 ->
 * #8a6100 for exactly two statuses) missed that `proposed`'s own shipped
 * color also failed AA, precisely because it wasn't generated/verified by
 * one shared routine. */

export const MIN_AA_CONTRAST = 4.5

function relativeLuminance(hex: string): number {
  const channel = (v: number) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

export function contrastRatio(hexA: string, hexB: string): number {
  const [lighter, darker] = [relativeLuminance(hexA), relativeLuminance(hexB)].sort((a, b) => b - a)
  return (lighter + 0.05) / (darker + 0.05)
}

/** Binary search over lightness, 30 iterations, run once at module load per
 * status -- not per render. */
export function maxLightnessForContrast(
  hue: number,
  saturation: number,
  toHex: (h: number, s: number, l: number) => string,
  against: string,
  minRatio: number = MIN_AA_CONTRAST,
): number {
  let lo = 0.05
  let hi = 0.6
  for (let i = 0; i < 30; i++) {
    const mid = (lo + hi) / 2
    if (contrastRatio(toHex(hue, saturation, mid), against) >= minRatio) lo = mid
    else hi = mid
  }
  return lo
}
