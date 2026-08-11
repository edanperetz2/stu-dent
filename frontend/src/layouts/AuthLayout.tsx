import {
  ActionIcon,
  Box,
  Center,
  Image,
  Paper,
  Stack,
  Title,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { IconMoon, IconSun } from '@tabler/icons-react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { RouteFallback } from '../components/RouteFallback'

export function AuthLayout() {
  const { principal, isLoading } = useAuth()
  const { setColorScheme } = useMantineColorScheme()
  const computedColorScheme = useComputedColorScheme('light')

  if (isLoading) return <RouteFallback />
  if (principal) return <Navigate to="/appointments" replace />

  return (
    <Box component="main" mih="100dvh" className="auth-page">
      <ActionIcon
        pos="fixed"
        top="md"
        right="md"
        size="lg"
        variant="subtle"
        color="gray"
        aria-label={
          computedColorScheme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'
        }
        onClick={() => setColorScheme(computedColorScheme === 'dark' ? 'light' : 'dark')}
      >
        {computedColorScheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
      </ActionIcon>
      <Center mih="100dvh" p={{ base: 'md', sm: 'xl' }}>
        {/* Full-viewport shell, single centered surface: close to the
            original composition, with a little more breathing room and
            scheme-aware colors instead of a hardcoded light background. */}
        <Paper
          withBorder
          shadow="xl"
          p={{ base: 'lg', sm: 'xl' }}
          radius="lg"
          maw={440}
          w="100%"
          className="auth-card"
        >
          <Stack align="stretch" gap="lg">
            <Stack align="center" gap={4}>
              <Image src="/stu-dent-logo.png" alt="Stu-Dent logo" w={160} h={160} />
              <Title order={2}>Stu-Dent</Title>
            </Stack>
            <Outlet />
          </Stack>
        </Paper>
      </Center>
    </Box>
  )
}
