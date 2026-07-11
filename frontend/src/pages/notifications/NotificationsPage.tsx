import { Badge, Group, Paper, Stack, Switch, Text, Title } from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { listNotifications, markNotificationRead } from '../../api/notifications'
import { useAuthToken } from '../../auth/useAuthToken'

function formatType(notificationType: string): string {
  return notificationType
    .split('_')
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')
}

export function NotificationsPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const [unreadOnly, setUnreadOnly] = useState(false)

  const { data: items, isLoading } = useQuery({
    queryKey: ['notifications', unreadOnly],
    queryFn: () => listNotifications(token, unreadOnly),
  })

  const markReadMutation = useMutation({
    mutationFn: (notificationId: string) => markNotificationRead(token, notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Notifications</Title>
        <Switch
          label="Unread only"
          checked={unreadOnly}
          onChange={(e) => setUnreadOnly(e.currentTarget.checked)}
        />
      </Group>

      {isLoading ? (
        <Text>Loading...</Text>
      ) : items?.length === 0 ? (
        <Text c="dimmed">No notifications.</Text>
      ) : (
        <Stack gap="xs">
          {items?.map((item) => (
            <Paper
              key={item.id}
              withBorder
              p="sm"
              style={{ cursor: item.read_at ? 'default' : 'pointer' }}
              onClick={() => {
                if (!item.read_at) markReadMutation.mutate(item.id)
              }}
              bg={item.read_at ? undefined : 'var(--mantine-color-blue-0)'}
            >
              <Group justify="space-between" wrap="nowrap">
                <Stack gap={2}>
                  <Badge size="sm" color={item.read_at ? 'gray' : 'blue'}>
                    {formatType(item.notification_type)}
                  </Badge>
                  <Text size="sm">{item.message}</Text>
                </Stack>
                <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                  {new Date(item.created_at).toLocaleString()}
                </Text>
              </Group>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
