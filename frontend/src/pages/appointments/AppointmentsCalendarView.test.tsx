import { MantineProvider } from '@mantine/core'
import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AppointmentsCalendarView } from './AppointmentsCalendarView'

function renderCalendar() {
  return render(
    <MantineProvider>
      <AppointmentsCalendarView
        events={[]}
        view="week"
        onViewChange={vi.fn()}
        date={new Date('2026-09-01T00:00:00.000Z')}
        onNavigate={vi.fn()}
        selectable={false}
        onSelectSlot={vi.fn()}
        onSelectEvent={vi.fn()}
        isResourceLens={false}
        resourceColorNames={{}}
      />
    </MantineProvider>,
  )
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

    expect(await screen.findByRole('button', { name: /agenda/i })).toBeInTheDocument()
  })

  it('does not offer Agenda at a normal screen width', async () => {
    mockNarrowScreen(false)
    renderCalendar()

    await waitFor(() => expect(screen.getByRole('button', { name: /week/i })).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /agenda/i })).not.toBeInTheDocument()
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
