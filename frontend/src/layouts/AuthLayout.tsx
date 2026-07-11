import { Center, Paper, Stack, Title } from '@mantine/core'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function AuthLayout() {
  const { principal, isLoading } = useAuth()

  if (isLoading) return null
  if (principal) return <Navigate to="/" replace />

  return (
    <Center mih="100vh" bg="var(--mantine-color-gray-0)">
      <Paper withBorder shadow="md" p="xl" radius="md" w={380}>
        <Stack>
          <Title order={2} ta="center">
            Stu-Dent
          </Title>
          <Outlet />
        </Stack>
      </Paper>
    </Center>
  )
}
