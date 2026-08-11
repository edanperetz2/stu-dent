import { MantineProvider } from '@mantine/core'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppointmentsCalendarView } from './AppointmentsCalendarView'

function renderCalendar(props: Partial<ComponentProps<typeof AppointmentsCalendarView>> = {}) {
  const onNavigate = props.onNavigate ?? vi.fn()
  const result = render(
    <MantineProvider>
      <AppointmentsCalendarView
        events={[]}
        view="week"
        onViewChange={vi.fn()}
        date={new Date('2026-09-01T00:00:00.000Z')}
        onNavigate={onNavigate}
        selectable={false}
        onSelectSlot={vi.fn()}
        onSelectEvent={vi.fn()}
        isResourceLens={false}
        resourceColorNames={{}}
        {...props}
      />
    </MantineProvider>,
  )
  return { ...result, onNavigate }
}

/** window.matchMedia is globally stubbed to always return matches:false in
 * test/setup.ts -- override it per-test to simulate the narrow-screen case
 * Mantine's useMediaQuery reads from. */
function mockNarrowScreen(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }))
}

describe('AppointmentsCalendarView', () => {
  afterEach(() => {
    mockNarrowScreen(false)
  })

  it('offers Agenda as a view only below the narrow-screen breakpoint', async () => {
    mockNarrowScreen(true)
    renderCalendar()

    expect(await screen.findByRole('radio', { name: /agenda/i })).toBeInTheDocument()
  })

  it('does not offer Agenda at a normal screen width', async () => {
    mockNarrowScreen(false)
    renderCalendar()

    await waitFor(() => expect(screen.getByRole('radio', { name: /week/i })).toBeInTheDocument())
    expect(screen.queryByRole('radio', { name: /agenda/i })).not.toBeInTheDocument()
    expect(screen.getByRole('radiogroup', { name: 'Calendar timescale' })).not.toHaveAttribute(
      'data-with-items-borders',
    )
  })

  it('uses icon-assisted previous, today, and next navigation controls', async () => {
    const { onNavigate } = renderCalendar()
    const previousButton = screen.getByRole('button', { name: 'Previous period' })
    const todayButton = screen.getByRole('button', { name: 'Today' })
    const nextButton = screen.getByRole('button', { name: 'Next period' })

    expect(previousButton.querySelector('svg')).not.toBeNull()
    expect(todayButton.querySelector('svg')).not.toBeNull()
    expect(nextButton.querySelector('svg')).not.toBeNull()

    await userEvent.click(previousButton)
    await userEvent.click(todayButton)
    await userEvent.click(nextButton)

    expect(onNavigate).toHaveBeenNthCalledWith(1, expect.any(Date), 'week', 'PREV')
    expect(onNavigate).toHaveBeenNthCalledWith(2, expect.any(Date), 'week', 'TODAY')
    expect(onNavigate).toHaveBeenNthCalledWith(3, expect.any(Date), 'week', 'NEXT')
  })

  it('renders weekday and date as separate modern header elements', () => {
    const { container } = renderCalendar()
    const headers = container.querySelectorAll('.appointments-calendar-day-header')

    expect(headers).toHaveLength(7)
    for (const header of headers) {
      expect(header.querySelector('.appointments-calendar-day-header__weekday')).not.toBeNull()
      expect(header.querySelector('.appointments-calendar-day-header__date')).not.toBeNull()
      expect(header.textContent).not.toContain('/')
    }
  })

  it('marks today with a date-circle hook without selecting the whole column', () => {
    const { container } = renderCalendar({ date: new Date() })

    expect(container.querySelectorAll('.appointments-calendar-day-header[data-today]')).toHaveLength(
      1,
    )
  })

  it('derives the wrapper height from the viewport instead of a fixed 700px', () => {
    const originalHeight = window.innerHeight
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 900 })

    const { container } = renderCalendar()
    const wrapper = container.querySelector('.rbc-calendar')?.parentElement as HTMLElement

    // min(700, max(420, 900 - 260)) = 640
    expect(wrapper.style.height).toBe('640px')

    Object.defineProperty(window, 'innerHeight', { configurable: true, value: originalHeight })
  })
})
