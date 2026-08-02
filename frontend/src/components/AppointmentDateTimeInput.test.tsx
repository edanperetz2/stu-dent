import { MantineProvider } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AppointmentDateTimeInput } from './AppointmentDateTimeInput'

const TIME_OPTIONS = ['09:00', '09:30', '10:00']

describe('AppointmentDateTimeInput', () => {
  it('does not call onChange with a combined value until both date and time are set', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(
      <MantineProvider>
        <AppointmentDateTimeInput
          label="Start time"
          value={null}
          onChange={onChange}
          timeOptions={TIME_OPTIONS}
        />
      </MantineProvider>,
    )

    await user.type(screen.getByLabelText('Start time'), '15/06/2026')

    // Date alone is never enough for a real value -- every call so far
    // must have been null (no time picked yet).
    for (const call of onChange.mock.calls) {
      expect(call[0]).toBeNull()
    }
  })

  it('renders an externally-set combined value split correctly into date and time', () => {
    render(
      <MantineProvider>
        <AppointmentDateTimeInput
          label="Start time"
          value="2026-06-15 09:30:00"
          onChange={vi.fn()}
          timeOptions={TIME_OPTIONS}
        />
      </MantineProvider>,
    )

    expect(screen.getByLabelText('Start time')).toHaveValue('15/06/2026')
    expect(screen.getByRole('combobox', { name: 'Time' })).toHaveValue('09:30')
  })

  it('re-syncs from a new external value (e.g. a form reset) rather than keeping stale local state', () => {
    const { rerender } = render(
      <MantineProvider>
        <AppointmentDateTimeInput
          label="Start time"
          value="2026-06-15 09:30:00"
          onChange={vi.fn()}
          timeOptions={TIME_OPTIONS}
        />
      </MantineProvider>,
    )
    expect(screen.getByLabelText('Start time')).toHaveValue('15/06/2026')

    rerender(
      <MantineProvider>
        <AppointmentDateTimeInput
          label="Start time"
          value={null}
          onChange={vi.fn()}
          timeOptions={TIME_OPTIONS}
        />
      </MantineProvider>,
    )

    expect(screen.getByLabelText('Start time')).toHaveValue('')
    expect(screen.getByRole('combobox', { name: 'Time' })).toHaveValue('')
  })

  it('renders a passed error message', () => {
    render(
      <MantineProvider>
        <AppointmentDateTimeInput
          label="Start time"
          value={null}
          onChange={vi.fn()}
          timeOptions={TIME_OPTIONS}
          error="Start time is required"
        />
      </MantineProvider>,
    )
    expect(screen.getByText('Start time is required')).toBeInTheDocument()
  })
})
