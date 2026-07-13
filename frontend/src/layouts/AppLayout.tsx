import {
  AppShell,
  Badge,
  Burger,
  Button,
  Group,
  Image,
  NavLink,
  Text,
  UnstyledButton,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { useQuery } from '@tanstack/react-query'
import { Link, Outlet, useNavigate } from 'react-router-dom'
import { listNotifications } from '../api/notifications'
import { useAuth, type Principal } from '../auth/AuthContext'

interface NavItem {
  label: string
  to: string
}

const STUDENT_LINKS: NavItem[] = [
  { label: 'Dashboard', to: '/' },
  { label: 'Patients', to: '/patients' },
  { label: 'Appointments', to: '/appointments' },
  { label: 'Availability', to: '/availability' },
  { label: 'Waitlist', to: '/waitlist' },
  { label: 'Forum', to: '/forum' },
  { label: 'Messages', to: '/messages' },
  { label: 'Notifications', to: '/notifications' },
  { label: 'Reports', to: '/reports' },
]

const ATTENDING_LINKS: NavItem[] = [
  { label: 'Dashboard', to: '/' },
  { label: 'Appointments', to: '/appointments' },
  { label: 'Messages', to: '/messages' },
  { label: 'Notifications', to: '/notifications' },
  { label: 'Reports', to: '/reports' },
]

const ADMIN_LINKS: NavItem[] = [
  { label: 'Users', to: '/admin/users' },
  { label: 'Rooms', to: '/admin/rooms' },
  { label: 'Equipment', to: '/admin/equipment' },
  { label: 'Appointments', to: '/appointments' },
  { label: 'Forum', to: '/forum' },
  { label: 'Messages', to: '/messages' },
  { label: 'Notifications', to: '/notifications' },
]

const PATIENT_LINKS: NavItem[] = [
  { label: 'My Appointments', to: '/appointments' },
  { label: 'Messages', to: '/messages' },
  { label: 'Notifications', to: '/notifications' },
  { label: 'Preferences', to: '/preferences' },
]

function linksForPrincipal(principal: Principal | null): NavItem[] {
  if (!principal) return []
  if (principal.role === 'patient') return PATIENT_LINKS
  if (principal.role === 'student') return STUDENT_LINKS
  if (principal.role === 'attending') return ATTENDING_LINKS
  return ADMIN_LINKS
}

function displayName(principal: Principal | null): string {
  if (!principal) return ''
  return principal.fullName
}

export function AppLayout() {
  const [opened, { toggle }] = useDisclosure()
  const { principal, logout } = useAuth()
  const navigate = useNavigate()
  const links = linksForPrincipal(principal)
  const homePath = links[0]?.to ?? '/'

  const { data: unreadNotifications } = useQuery({
    queryKey: ['notifications', true],
    queryFn: () => listNotifications(principal!.token, true),
    enabled: !!principal,
  })
  const unreadCount = unreadNotifications?.length ?? 0

  return (
    <AppShell
      header={{ height: 72 }}
      navbar={{ width: 220, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="xs">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
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
        {links.map((link) => (
          <NavLink
            key={link.to}
            label={link.label}
            className="app-nav-link"
            onClick={() => navigate(link.to)}
            rightSection={
              link.to === '/notifications' && unreadCount > 0 ? (
                <Badge size="sm" circle color="red">
                  {unreadCount}
                </Badge>
              ) : undefined
            }
          />
        ))}
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
