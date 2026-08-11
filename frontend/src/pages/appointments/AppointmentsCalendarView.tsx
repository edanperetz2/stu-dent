import 'react-big-calendar/lib/css/react-big-calendar.css'

import { ActionIcon, Button, Group, SegmentedControl, Text, Tooltip, useMantineTheme } from '@mantine/core'
import { useMediaQuery, useViewportSize } from '@mantine/hooks'
import {
  IconCalendarEvent,
  IconChevronLeft,
  IconChevronRight,
} from '@tabler/icons-react'
import dayjs from 'dayjs'
import {
  Calendar,
  dayjsLocalizer,
  type Formats,
  type HeaderProps,
  type SlotInfo,
  type ToolbarProps,
  type View,
} from 'react-big-calendar'
import { APPOINTMENT_END_TIME_OPTIONS, APPOINTMENT_START_TIME_OPTIONS } from '../../utils/dates'
import { STATUS_CALENDAR_COLOR } from './appointmentActions'
import { AGENDA_LENGTH_DAYS, type CalendarEventItem, type RESOURCE_COLOR_NAMES } from './resourceColors'

const localizer = dayjsLocalizer(dayjs)

/** react-big-calendar's Day/Week views only read the hour/minute off a
 * `min`/`max` Date, not its date part -- any day works as the carrier.
 * Built from the same "HH:mm" constants the booking form's time Selects
 * use (utils/dates.ts) so clinic hours can't drift between the two. */
function timeOptionToDate(time: string): Date {
  const [hour, minute] = time.split(':').map(Number)
  return dayjs().hour(hour).minute(minute).second(0).millisecond(0).toDate()
}

const CALENDAR_MIN_TIME = timeOptionToDate(APPOINTMENT_START_TIME_OPTIONS[0])
const CALENDAR_MAX_TIME = timeOptionToDate(APPOINTMENT_END_TIME_OPTIONS[APPOINTMENT_END_TIME_OPTIONS.length - 1])

// dayjsLocalizer's own defaults use dayjs's localized-time token ('LT'),
// which in the default English locale is 12-hour with AM/PM -- override
// with plain dd/mm + 24h tokens instead (Israel-based app). Agenda formats
// are included even though Agenda is only offered as a view below on
// narrow screens -- react-big-calendar reads these lazily per-view, so
// having them ready costs nothing.
const CALENDAR_FORMATS: Formats = {
  timeGutterFormat: 'HH:mm',
  dayFormat: 'ddd D MMM',
  dayHeaderFormat: 'dddd, D MMMM YYYY',
  dayRangeHeaderFormat: ({ start, end }, culture, localizer) =>
    `${localizer!.format(start, 'D MMM', culture)} – ${localizer!.format(end, 'D MMM YYYY', culture)}`,
  eventTimeRangeFormat: ({ start, end }, culture, localizer) =>
    `${localizer!.format(start, 'HH:mm', culture)} – ${localizer!.format(end, 'HH:mm', culture)}`,
  selectRangeFormat: ({ start, end }, culture, localizer) =>
    `${localizer!.format(start, 'HH:mm', culture)} – ${localizer!.format(end, 'HH:mm', culture)}`,
  agendaDateFormat: 'ddd, D MMM',
  agendaTimeFormat: 'HH:mm',
  agendaHeaderFormat: ({ start, end }, culture, localizer) =>
    `${localizer!.format(start, 'D MMM', culture)} – ${localizer!.format(end, 'D MMM YYYY', culture)}`,
}

const VIEW_LABELS: Partial<Record<View, string>> = {
  month: 'Month',
  week: 'Week',
  day: 'Day',
  agenda: 'Agenda',
}

function availableCalendarViews(views: ToolbarProps['views']): View[] {
  if (Array.isArray(views)) return views
  return (Object.keys(views) as View[]).filter((candidate) => Boolean(views[candidate]))
}

function CalendarToolbar({ label, onNavigate, onView, view, views }: ToolbarProps<CalendarEventItem>) {
  const viewOptions = availableCalendarViews(views).map((value) => ({
    value,
    label: VIEW_LABELS[value] ?? value,
  }))

  return (
    <div className="appointments-calendar-toolbar">
      <Group gap={4} wrap="nowrap">
        <Tooltip label="Previous period" openDelay={400}>
          <ActionIcon
            variant="subtle"
            color="gray"
            size="lg"
            radius="xl"
            aria-label="Previous period"
            onClick={() => onNavigate('PREV')}
          >
            <IconChevronLeft size={18} stroke={1.7} />
          </ActionIcon>
        </Tooltip>
        <Button
          variant="subtle"
          color="gray"
          size="compact-sm"
          radius="xl"
          leftSection={<IconCalendarEvent size={15} stroke={1.7} />}
          onClick={() => onNavigate('TODAY')}
        >
          Today
        </Button>
        <Tooltip label="Next period" openDelay={400}>
          <ActionIcon
            variant="subtle"
            color="gray"
            size="lg"
            radius="xl"
            aria-label="Next period"
            onClick={() => onNavigate('NEXT')}
          >
            <IconChevronRight size={18} stroke={1.7} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <Text className="appointments-calendar-toolbar__label">{label}</Text>

      <SegmentedControl
        aria-label="Calendar timescale"
        value={view}
        onChange={(value) => onView(value as View)}
        data={viewOptions}
        size="xs"
        radius="xl"
        className="appointments-segmented-control appointments-calendar-view-toggle"
        transitionDuration={180}
        withItemsBorders={false}
      />
    </div>
  )
}

function CalendarDayHeader({ date }: HeaderProps) {
  const label = dayjs(date).format('dddd, D MMMM')
  const isToday = dayjs(date).isSame(dayjs(), 'day')

  return (
    <span className="appointments-calendar-day-header" data-today={isToday || undefined}>
      <span className="appointments-calendar-day-header__weekday">{dayjs(date).format('ddd')}</span>
      <span className="appointments-calendar-day-header__date" aria-label={label}>
        {dayjs(date).format('D')}
      </span>
    </span>
  )
}

function CalendarMonthHeader({ date }: HeaderProps) {
  return (
    <span className="appointments-calendar-month-header">
      {dayjs(date).format('ddd')}
    </span>
  )
}

// Below this width the month/week grid views are cramped enough to be
// unusable (react-big-calendar lays out real day columns, which don't
// reflow) -- a scrollable Agenda list reads far better on a phone-sized
// screen, so it's added as a selectable view rather than replacing the
// grid views outright (a wide-screen user who resizes down keeps their
// current view; they just gain Agenda as an option).
const NARROW_SCREEN_QUERY = '(max-width: 48em)'

interface AppointmentsCalendarViewProps {
  events: CalendarEventItem[]
  view: View
  onViewChange: (view: View) => void
  date: Date
  onNavigate: (date: Date) => void
  selectable: boolean
  onSelectSlot: (slotInfo: SlotInfo) => void
  onSelectEvent: (event: CalendarEventItem) => void
  isResourceLens: boolean
  resourceColorNames: Record<string, (typeof RESOURCE_COLOR_NAMES)[number]>
}

/** One flat calendar for every lens -- the Resources lens colors events by
 * resource (via the filter chips in AppointmentsListPage) instead of
 * splitting into per-resource lanes, so every room/equipment's bookings
 * are visible together without any horizontal scrolling. */
export function AppointmentsCalendarView({
  events,
  view,
  onViewChange,
  date,
  onNavigate,
  selectable,
  onSelectSlot,
  onSelectEvent,
  isResourceLens,
  resourceColorNames,
}: AppointmentsCalendarViewProps) {
  const theme = useMantineTheme()
  const isNarrow = useMediaQuery(NARROW_SCREEN_QUERY)
  // Leaves room for the page header/toolbar above the calendar instead of a
  // flat 700px regardless of screen size -- clamped so a short phone
  // viewport still gets a usable scroll area, and a very tall monitor
  // doesn't stretch the grid pointlessly past its original 700px.
  const { height: viewportHeight } = useViewportSize()
  const calendarHeight = Math.min(700, Math.max(420, viewportHeight - 260))
  const views: View[] = isNarrow ? ['month', 'week', 'day', 'agenda'] : ['month', 'week', 'day']

  return (
    <div className="appointments-calendar-shell" style={{ height: calendarHeight }}>
      <Calendar
        localizer={localizer}
        formats={CALENDAR_FORMATS}
        events={events}
        views={views}
        view={view}
        onView={onViewChange}
        date={date}
        onNavigate={onNavigate}
        min={CALENDAR_MIN_TIME}
        max={CALENDAR_MAX_TIME}
        scrollToTime={CALENDAR_MIN_TIME}
        // Agenda's own default window is 30 days -- must match
        // getCalendarViewRange's 'agenda' case (resourceColors.ts) exactly,
        // or Agenda visually spans more days than were actually fetched,
        // silently rendering as "no appointments" for the un-fetched ones.
        length={AGENDA_LENGTH_DAYS}
        selectable={selectable}
        onSelectSlot={onSelectSlot}
        onSelectEvent={onSelectEvent}
        components={{
          toolbar: CalendarToolbar,
          day: { header: CalendarDayHeader },
          week: { header: CalendarDayHeader },
          month: { header: CalendarMonthHeader },
        }}
        eventPropGetter={(event) => {
          const color =
            isResourceLens && event.resourceId
              ? theme.colors[resourceColorNames[event.resourceId]][6]
              : event.resource
                ? STATUS_CALENDAR_COLOR[event.resource.status]
                : theme.colors.gray[6]
          return { style: { backgroundColor: color } }
        }}
        // react-big-calendar's own `style` prop, not a Mantine component --
        // no shorthand prop applies here.
        style={{ height: '100%' }}
      />
    </div>
  )
}
