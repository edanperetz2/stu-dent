import { Center, Image, Paper, Stack, Title } from '@mantine/core'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { RouteFallback } from '../components/RouteFallback'

export function AuthLayout() {
  const { principal, isLoading } = useAuth()

  if (isLoading) return <RouteFallback />
  if (principal) return <Navigate to="/appointments" replace />

  return (
    <Center mih="100vh" p="md" bg="var(--mantine-color-gray-0)">
      {/* maw+w="100%" (not a fixed w) -- the very first screen every user
          sees was forcing horizontal scroll/clipping below 380px
          (iPhone SE and many Android phones). */}
      <Paper withBorder shadow="md" p="md" radius="md" maw={380} w="100%">
        <Stack align="stretch" gap="xs">
          <Image
            src="/stu-dent-logo.png"
            alt="Stu-Dent logo"
            w={300}
            h={300}
            mx="auto"
          />
          <Title order={2} ta="center">
            Stu-Dent
          </Title>
          <Outlet />
        </Stack>
      </Paper>
    </Center>
  )
}
