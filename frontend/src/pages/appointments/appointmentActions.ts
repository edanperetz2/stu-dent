import type { CSSProperties } from 'react'
import { humanizeFieldName } from '../../api/httpClient'
import type { Appointment, AppointmentStatus } from '../../api/types'
import type { Principal } from '../../auth/AuthContext'
import { BRAND_INK, hslToHex } from '../../theme'
import { maxLightnessForContrast } from '../../utils/colorContrast'

export type AppointmentActionName = 'accept' | 'approve' | 'reject' | 'cancel' | 'complete' | 'no_show'

export interface AppointmentAction {
  name: AppointmentActionName
  label: string
  color: string
}

export const TERMINAL_STATUSES: AppointmentStatus[] = ['cancelled', 'completed', 'no_show']

// One hue (+ saturation) per status -- both the pale badge background and
// the saturated calendar fill below are generated from this single table
// instead of being two independently hand-maintained hex maps for the same
// 7 statuses, which was the actual drift risk: a status added to one map
// and forgotten in the other, or a color nudged in one without its pair.
// Saturation 0 (proposed) is a neutral gray, where hue is irrelevant.
const STATUS_COLOR_SPEC: Record<AppointmentStatus, { hue: number; saturation: number }> = {
  proposed: { hue: 0, saturation: 0 },
  awaiting_confirmation: { hue: 45, saturation: 0.85 },
  confirmed: { hue: 132, saturation: 0.85 },
  cancelled: { hue: 4, saturation: 0.85 },
  completed: { hue: 212, saturation: 0.85 },
  no_show: { hue: 25, saturation: 0.85 },
  // Same hue as awaiting_confirmation -- both are "needs a decision" states.
  rescheduling_requested: { hue: 45, saturation: 0.85 },
}

const WHITE = '#ffffff'
const PALE_LIGHTNESS = 0.93

/** The highest lightness (at a fixed hue/saturation) that still clears AA
 * contrast against white text -- red and blue need very different
 * lightness for the same measured contrast, so one shared lightness across
 * every hue would either fail some statuses or be needlessly dark for
 * others. See utils/colorContrast.ts for the binary search itself, shared
 * with WaitlistPage.tsx's own (smaller) status-color table. */
function maxLightnessForWhiteText(hue: number, saturation: number): number {
  return maxLightnessForContrast(hue, saturation, hslToHex, WHITE)
}

/** Pale background per status; text is uniformly BRAND_INK for every one of
 * them (see statusBadgeStyle) rather than a matching dark shade per hue --
 * the previous approach (white text on Mantine's stock "yellow", i.e.
 * `<Badge color="yellow">`) measured at ~2.2:1 contrast, far under the
 * 4.5:1 WCAG AA minimum for normal text. A single dark ink color reliably
 * clears AA against any near-white background regardless of hue, which is
 * both simpler and more robust than re-deriving a passing shade per color. */
const STATUS_BADGE_BACKGROUND: Record<AppointmentStatus, string> = Object.fromEntries(
  Object.entries(STATUS_COLOR_SPEC).map(([status, { hue, saturation }]) => [
    status,
    hslToHex(hue, saturation, PALE_LIGHTNESS),
  ]),
) as Record<AppointmentStatus, string>

/** `colorScheme` defaults to 'light' for the (rare) caller that doesn't
 * have one handy, but every real call site passes the real
 * `useComputedColorScheme()` result -- without this, badges were
 * hardcoded to the pale/ink pairing regardless of theme, so every status
 * badge rendered as a bright near-white pill in dark mode. Dark mode
 * reuses STATUS_CALENDAR_COLOR (already generated + AA-verified against
 * white text below) as the badge fill instead of deriving a third color
 * set. */
export function statusBadgeStyle(
  status: AppointmentStatus,
  colorScheme: 'light' | 'dark' = 'light',
): CSSProperties {
  if (colorScheme === 'dark') {
    return { backgroundColor: STATUS_CALENDAR_COLOR[status], color: '#ffffff' }
  }
  return { backgroundColor: STATUS_BADGE_BACKGROUND[status], color: BRAND_INK }
}

export function statusLabel(status: AppointmentStatus): string {
  return humanizeFieldName(status)
}

/** The one saturated hex actually painted by react-big-calendar's
 * eventPropGetter (white event text needs real contrast against a solid
 * fill, unlike the pale badge tints above, which pair with dark text
 * instead) -- each status's lightness is the maximum that still clears
 * WCAG AA for white text (maxLightnessForWhiteText above), rather than
 * hand-picked per status. The original review finding (`#f59f00`, ~2.2:1
 * against white) was fixed by hand for exactly the two statuses it named;
 * that same fix turned out to be needed for `proposed` too (the shipped
 * `#868e96` measured ~3.3:1, short of AA, and had gone unverified) --
 * generating every status from one formula catches exactly this instead of
 * relying on each one being individually checked by hand. */
export const STATUS_CALENDAR_COLOR: Record<AppointmentStatus, string> = Object.fromEntries(
  Object.entries(STATUS_COLOR_SPEC).map(([status, { hue, saturation }]) => [
    status,
    hslToHex(hue, saturation, maxLightnessForWhiteText(hue, saturation)),
  ]),
) as Record<AppointmentStatus, string>

/**
 * Mirrors the authorization + status rules in
 * backend/app/api/routes/appointments.py exactly, so the UI never offers an
 * action the API would reject. Kept as a pure function (no rendering) so
 * it's directly unit-testable without mounting the page.
 */
export function getAvailableActions(
  appointment: Appointment,
  principal: Principal,
  now: Date = new Date(),
): AppointmentAction[] {
  const actions: AppointmentAction[] = []

  const isOwningStudent =
    principal.role === 'student' && appointment.student_id === principal.id
  const isAssignedAttending =
    principal.role === 'attending' && appointment.attending_id === principal.id
  const isSelfPatient = principal.role === 'patient' && appointment.patient_id === principal.id

  const isTerminal = TERMINAL_STATUSES.includes(appointment.status)

  if (isOwningStudent && appointment.status === 'proposed') {
    actions.push({ name: 'accept', label: 'Accept', color: 'green' })
  }

  if (
    isAssignedAttending &&
    (appointment.status === 'awaiting_confirmation' || appointment.status === 'rescheduling_requested')
  ) {
    actions.push({ name: 'approve', label: 'Approve', color: 'green' })
  }

  if (isAssignedAttending && !isTerminal) {
    actions.push({ name: 'reject', label: 'Reject', color: 'red' })
  }

  if ((isOwningStudent || isSelfPatient) && !isTerminal) {
    actions.push({ name: 'cancel', label: 'Cancel', color: 'red' })
  }

  if (
    isOwningStudent &&
    appointment.status === 'confirmed' &&
    now >= new Date(appointment.start_time)
  ) {
    actions.push({ name: 'complete', label: 'Complete', color: 'blue' })
    actions.push({ name: 'no_show', label: 'Mark No-Show', color: 'orange' })
  }

  return actions
}
