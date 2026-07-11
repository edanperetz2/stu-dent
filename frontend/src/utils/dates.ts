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
