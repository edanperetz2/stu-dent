import { Center, Paper, Stack, Title } from '@mantine/core'
import { Outlet } from 'react-router-dom'

export function AuthLayout() {
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
