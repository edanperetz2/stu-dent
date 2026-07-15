/**
 * Mantine's DateTimePicker onChange always emits a "YYYY-MM-DD HH:mm:ss"
 * local-time string (DatePickerValue<Type, DateStringValue> in
 * @mantine/dates' own types), never a Date object -- regardless of what
 * type a form field declares. These two helpers are the single conversion
 * point between that string and the ISO 8601 (UTC) strings the backend
 * expects, so no page has to get this conversion right by hand.
 */

/** Mantine local-time string -> ISO 8601 UTC string, for sending to the API. */
export function mantineDateTimeToIso(value: string): string {
  return new Date(value.replace(' ', 'T')).toISOString()
}

/** ISO 8601 string from the API -> Mantine's local-time string, for pre-filling a DateTimePicker. */
export function isoToMantineDateTime(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

/** "HH:mm" options every 30 minutes from startHour:startMinute through
 * endHour:endMinute inclusive -- backs the fixed time-of-day Select used by
 * AppointmentDateTimeInput, since free-typing an hour/minute into
 * DateTimePicker's spinner proved error-prone. */
function generateHalfHourOptions(
  startHour: number,
  startMinute: number,
  endHour: number,
  endMinute: number,
): string[] {
  const pad = (n: number) => String(n).padStart(2, '0')
  const options: string[] = []
  let hour = startHour
  let minute = startMinute
  while (hour < endHour || (hour === endHour && minute <= endMinute)) {
    options.push(`${pad(hour)}:${pad(minute)}`)
    minute += 30
    if (minute >= 60) {
      minute -= 60
      hour += 1
    }
  }
  return options
}

/** 08:00, 08:30, ..., 21:00 -- appointment start-time options. */
export const APPOINTMENT_START_TIME_OPTIONS = generateHalfHourOptions(8, 0, 21, 0)
/** 08:30, 09:00, ..., 21:30 -- appointment end-time options. */
export const APPOINTMENT_END_TIME_OPTIONS = generateHalfHourOptions(8, 30, 21, 30)
