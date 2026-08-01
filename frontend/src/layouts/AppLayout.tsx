import {
  ActionIcon,
  AppShell,
  Badge,
  Burger,
  Button,
  Group,
  Image,
  NavLink,
  Text,
  UnstyledButton,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useQuery } from '@tanstack/react-query'
import {
  IconBell,
  IconCalendarEvent,
  IconClockHour4,
  IconDoorEnter,
  IconMessage,
  IconMessageCircle2,
  IconMessageReport,
  IconMoon,
  IconReportAnalytics,
  IconSettings,
  IconStethoscope,
  IconSun,
  IconUserCog,
  IconUsers,
  type Icon,
} from '@tabler/icons-react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { listPendingFeedback } from '../api/feedback'
import { getUnreadCount } from '../api/messages'
import { getUnreadNotificationCount } from '../api/notifications'
import { useAuth, type Principal } from '../auth/AuthContext'
import { useRealtime } from '../realtime/RealtimeContext'

type NavSection = 'Clinic' | 'Admin' | 'Community' | 'You'

interface NavItem {
  label: string
  to: string
  icon: Icon
  section: NavSection
}

const STUDENT_LINKS: NavItem[] = [
  { label: 'Appointments', to: '/appointments', icon: IconCalendarEvent, section: 'Clinic' },
  { label: 'Patients', to: '/patients', icon: IconUsers, section: 'Clinic' },
  { label: 'Waitlist', to: '/waitlist', icon: IconClockHour4, section: 'Clinic' },
  { label: 'Forum', to: '/forum', icon: IconMessageCircle2, section: 'Community' },
  { label: 'Messages', to: '/messages', icon: IconMessage, section: 'Community' },
  { label: 'Notifications', to: '/notifications', icon: IconBell, section: 'Community' },
  { label: 'Feedback', to: '/feedback', icon: IconMessageReport, section: 'You' },
  { label: 'Reports', to: '/reports', icon: IconReportAnalytics, section: 'You' },
]

const ATTENDING_LINKS: NavItem[] = [
  { label: 'Appointments', to: '/appointments', icon: IconCalendarEvent, section: 'Clinic' },
  { label: 'Messages', to: '/messages', icon: IconMessage, section: 'Community' },
  { label: 'Notifications', to: '/notifications', icon: IconBell, section: 'Community' },
  { label: 'Feedback', to: '/feedback', icon: IconMessageReport, section: 'You' },
  { label: 'Reports', to: '/reports', icon: IconReportAnalytics, section: 'You' },
]

const ADMIN_LINKS: NavItem[] = [
  { label: 'Appointments', to: '/appointments', icon: IconCalendarEvent, section: 'Clinic' },
  { label: 'Users', to: '/admin/users', icon: IconUserCog, section: 'Admin' },
  { label: 'Rooms', to: '/admin/rooms', icon: IconDoorEnter, section: 'Admin' },
  { label: 'Equipment', to: '/admin/equipment', icon: IconStethoscope, section: 'Admin' },
  { label: 'Forum', to: '/forum', icon: IconMessageCircle2, section: 'Community' },
  { label: 'Messages', to: '/messages', icon: IconMessage, section: 'Community' },
  { label: 'Notifications', to: '/notifications', icon: IconBell, section: 'Community' },
]

const PATIENT_LINKS: NavItem[] = [
  { label: 'My Appointments', to: '/appointments', icon: IconCalendarEvent, section: 'Clinic' },
  { label: 'Waitlist', to: '/waitlist', icon: IconClockHour4, section: 'Clinic' },
  { label: 'Messages', to: '/messages', icon: IconMessage, section: 'Community' },
  { label: 'Notifications', to: '/notifications', icon: IconBell, section: 'Community' },
  { label: 'Feedback', to: '/feedback', icon: IconMessageReport, section: 'You' },
  { label: 'Preferences', to: '/preferences', icon: IconSettings, section: 'You' },
]

function linksForPrincipal(principal: Principal | null): NavItem[] {
  if (!principal) return []
  if (principal.role === 'patient') return PATIENT_LINKS
  if (principal.role === 'student') return STUDENT_LINKS
  if (principal.role === 'attending') return ATTENDING_LINKS
  return ADMIN_LINKS
}

/** Groups by first-appearance order of `section`, not a fixed global order
 * -- each role's own link list already puts related items next to each
 * other, so this just reads that grouping off the array instead of
 * hardcoding a section order that has to be kept in sync separately. */
function groupBySection(items: NavItem[]): { section: NavSection; items: NavItem[] }[] {
  const groups: { section: NavSection; items: NavItem[] }[] = []
  for (const item of items) {
    let group = groups.find((g) => g.section === item.section)
    if (!group) {
      group = { section: item.section, items: [] }
      groups.push(group)
    }
    group.items.push(item)
  }
  return groups
}

function displayName(principal: Principal | null): string {
  if (!principal) return ''
  return principal.fullName
}

export function AppLayout() {
  const [opened, { toggle, close }] = useDisclosure()
  const { principal, logout } = useAuth()
  const { isConnected, reconnectExhausted, reconnect } = useRealtime()
  const navigate = useNavigate()
  const location = useLocation()
  const { setColorScheme } = useMantineColorScheme()
  // Resolves "auto" to the real light/dark it's currently showing, so the
  // toggle's own icon (and the scheme it switches to) reflects what's
  // actually on screen even before the user has ever picked one explicitly.
  const computedColorScheme = useComputedColorScheme('light')
  const links = linksForPrincipal(principal)
  const linkSections = groupBySection(links)
  const homePath = links[0]?.to ?? '/'

  const { data: unreadNotifications, isError: notificationsError } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => getUnreadNotificationCount(principal!.token),
    enabled: !!principal,
  })
  const unreadCount = unreadNotifications?.count ?? 0

  const { data: unreadMessages, isError: messagesError } = useQuery({
    queryKey: ['messages', 'unread-count'],
    queryFn: () => getUnreadCount(principal!.token),
    enabled: !!principal,
  })
  const unreadMessageCount = unreadMessages?.count ?? 0

  // Only a patient/attending has anything actionable on the Feedback page --
  // a student only ever receives, so no badge for them.
  const { data: pendingFeedback, isError: feedbackError } = useQuery({
    queryKey: ['feedback', 'pending'],
    queryFn: () => listPendingFeedback(principal!.token),
    enabled: !!principal && (principal.role === 'patient' || principal.role === 'attending'),
  })
  const pendingFeedbackCount = pendingFeedback?.length ?? 0

  return (
    <>
      {/* Invisible until focused (first Tab stop on the page) -- lets a
          keyboard user skip the header/nav entirely instead of tabbing
          through every nav item just to reach the page content. */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <AppShell
        header={{ height: 72 }}
        navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
        padding="md"
      >
        <AppShell.Header>
          <Group h="100%" px="md" justify="space-between">
            <Group gap="xs">
              <Burger
                opened={opened}
                onClick={toggle}
                hiddenFrom="sm"
                size="sm"
                aria-label="Toggle navigation"
              />
              <UnstyledButton
                component={Link}
                to={homePath}
                aria-label="Go to your home page"
                className="header-logo-link"
              >
                <Image
                  src="/stu-dent-logo-header.png"
                  alt="Stu-Dent logo"
                  w={68}
                  h={68}
                  fit="contain"
                />
              </UnstyledButton>
            </Group>
            <Group>
              {principal && !isConnected && (
                <Group gap={4} wrap="nowrap">
                  <Badge color={reconnectExhausted ? 'red' : 'orange'} variant="light">
                    {reconnectExhausted ? 'Disconnected' : 'Reconnecting…'}
                  </Badge>
                  <Button size="compact-xs" variant="light" onClick={reconnect}>
                    Refresh
                  </Button>
                </Group>
              )}
              <ActionIcon
                variant="subtle"
                color="gray"
                size="lg"
                aria-label={
                  computedColorScheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
                }
                onClick={() =>
                  setColorScheme(computedColorScheme === 'dark' ? 'light' : 'dark')
                }
              >
                {computedColorScheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
              </ActionIcon>
              <Text size="sm">{displayName(principal)}</Text>
              <Button
                variant="subtle"
                color="gray"
                size="xs"
                className="header-logout-button"
                onClick={() => {
                  logout()
                  navigate('/login')
                }}
              >
                Log out
              </Button>
            </Group>
          </Group>
        </AppShell.Header>
        <AppShell.Navbar p="md">
          {linkSections.map(({ section, items }, sectionIndex) => (
            <div key={section}>
              <Text
                size="xs"
                fw={700}
                c="dimmed"
                tt="uppercase"
                px="xs"
                pt={sectionIndex === 0 ? 0 : 'sm'}
                pb={4}
              >
                {section}
              </Text>
              {items.map((link) => {
                const isActive = location.pathname === link.to
                const badgeCount =
                  link.to === '/notifications'
                    ? unreadCount
                    : link.to === '/messages'
                      ? unreadMessageCount
                      : link.to === '/feedback'
                        ? pendingFeedbackCount
                        : 0
                // A failed badge fetch used to silently render as "no
                // badge", indistinguishable from genuinely zero unread --
                // shown instead as a distinct "count unavailable" marker
                // rather than a numeric one.
                const badgeError =
                  link.to === '/notifications'
                    ? notificationsError
                    : link.to === '/messages'
                      ? messagesError
                      : link.to === '/feedback'
                        ? feedbackError
                        : false
                return (
                  <NavLink
                    key={link.to}
                    component={Link}
                    to={link.to}
                    label={link.label}
                    leftSection={<link.icon size={18} />}
                    active={isActive}
                    aria-current={isActive ? 'page' : undefined}
                    className="app-nav-link"
                    // A real <a> now (via `component={Link}`), so this only
                    // needs to close the mobile drawer -- navigation itself
                    // is Link's job, not this handler's.
                    onClick={close}
                    rightSection={
                      badgeError ? (
                        <Badge
                          size="sm"
                          circle
                          color="gray"
                          aria-label={`${link.label} count unavailable`}
                        >
                          !
                        </Badge>
                      ) : badgeCount > 0 ? (
                        <Badge size="sm" circle color="red">
                          {badgeCount}
                        </Badge>
                      ) : undefined
                    }
                  />
                )
              })}
            </div>
          ))}
        </AppShell.Navbar>
        <AppShell.Main id="main-content">
          <Outlet />
        </AppShell.Main>
      </AppShell>
    </>
  )
}
