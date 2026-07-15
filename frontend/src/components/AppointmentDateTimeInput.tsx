import { Group, Select, Stack, Text } from '@mantine/core'
import { DateInput } from '@mantine/dates'
import { useEffect, useState, type ReactNode } from 'react'

interface AppointmentDateTimeInputProps {
  label: string
  // Mantine's combined "YYYY-MM-DD HH:mm:ss" local-time string -- see
  // src/utils/dates.ts. Kept as the external value shape so this drops
  // into the same form fields (mantineDateTimeToIso/isoToMantineDateTime,
  // useForm validation) that DateTimePicker used.
  value?: string | null
  onChange: (value: string | null) => void
  error?: ReactNode
  // "HH:mm" options -- see APPOINTMENT_START_TIME_OPTIONS /
  // APPOINTMENT_END_TIME_OPTIONS in src/utils/dates.ts.
  timeOptions: string[]
}

function splitValue(value: string | null | undefined): { date: string | null; time: string | null } {
  if (!value) return { date: null, time: null }
  const [date, time] = value.split(' ')
  return { date, time: time ? time.slice(0, 5) : null }
}

function combine(date: string | null, time: string | null): string | null {
  if (!date || !time) return null
  return `${date} ${time}:00`
}

/** Date + time-of-day input for appointment start/end times, replacing
 * DateTimePicker's free-typed hour/minute spinner -- that was hard and
 * error-prone to use, since it required typing digits into a tiny segment
 * one at a time. The calendar date-picker is kept as-is (it was never the
 * problem); only the time-of-day is now a fixed half-hour Select.
 *
 * Date and time are picked one at a time, but the combined value only
 * exists once both are set -- so each half is tracked in its own local
 * state (synced from `value` only when the parent resets/pre-fills it)
 * rather than re-derived from `value` on every render, otherwise picking
 * the date first would round-trip through onChange(null) (no time yet)
 * and immediately forget the date the user just picked. */
export function AppointmentDateTimeInput({
  label,
  value,
  onChange,
  error,
  timeOptions,
}: AppointmentDateTimeInputProps) {
  const [date, setDate] = useState<string | null>(() => splitValue(value).date)
  const [time, setTime] = useState<string | null>(() => splitValue(value).time)

  useEffect(() => {
    const next = splitValue(value)
    setDate(next.date)
    setTime(next.time)
  }, [value])

  function handleDateChange(newDate: string | null) {
    setDate(newDate)
    onChange(combine(newDate, time))
  }

  function handleTimeChange(newTime: string | null) {
    setTime(newTime)
    onChange(combine(date, newTime))
  }

  return (
    <Stack gap={4}>
      <Group grow align="flex-start">
        <DateInput label={label} value={date} onChange={handleDateChange} valueFormat="DD/MM/YYYY" />
        <Select label="Time" data={timeOptions} value={time} onChange={handleTimeChange} searchable />
      </Group>
      {error && (
        <Text size="xs" c="red">
          {error}
        </Text>
      )}
    </Stack>
  )
}
