import { Badge, Button, Group, Paper, Stack, Switch, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listNotifications,
  markNotificationRead,
  markNotificationUnread,
} from '../../api/notifications'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuthToken } from '../../auth/useAuthToken'
import { EmptyText, LoadingText } from '../../components/StateText'
import { formatDateTime } from '../../utils/dates'

function formatType(notificationType: string): string {
  return notificationType
    .split('_')
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')
}

export function NotificationsPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
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
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to mark notification as read'),
        color: 'red',
      })
    },
  })

  const markUnreadMutation = useMutation({
    mutationFn: (notificationId: string) => markNotificationUnread(token, notificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to mark notification as unread'),
        color: 'red',
      })
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
        <LoadingText />
      ) : items?.length === 0 ? (
        <EmptyText>No notifications.</EmptyText>
      ) : (
        <Stack gap="xs">
          {items?.map((item) => {
            const isLinkable = !!item.related_appointment_id
            const goToAppointment = () => {
              if (!item.related_appointment_id) return
              if (!item.read_at) markReadMutation.mutate(item.id)
              navigate(`/appointments?appointment=${item.related_appointment_id}`)
            }
            return (
            <Paper
              key={item.id}
              withBorder
              p="sm"
              bg={item.read_at ? undefined : 'var(--mantine-color-blue-0)'}
              style={isLinkable ? { cursor: 'pointer' } : undefined}
              onClick={isLinkable ? goToAppointment : undefined}
              onKeyDown={
                isLinkable
                  ? (e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        goToAppointment()
                      }
                    }
                  : undefined
              }
              tabIndex={isLinkable ? 0 : undefined}
              role={isLinkable ? 'button' : undefined}
            >
              <Group justify="space-between" wrap="nowrap" align="flex-start">
                <Stack gap={2}>
                  <Badge size="sm" color={item.read_at ? 'gray' : 'blue'}>
                    {formatType(item.notification_type)}
                  </Badge>
                  <Text size="sm">{item.message}</Text>
                </Stack>
                <Stack gap={4} align="flex-end">
                  <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                    {formatDateTime(item.created_at)}
                  </Text>
                  {item.read_at ? (
                    <Button
                      size="compact-xs"
                      variant="subtle"
                      loading={markUnreadMutation.isPending}
                      onClick={(e) => {
                        e.stopPropagation()
                        markUnreadMutation.mutate(item.id)
                      }}
                    >
                      Mark unread
                    </Button>
                  ) : (
                    <Button
                      size="compact-xs"
                      variant="light"
                      loading={markReadMutation.isPending}
                      onClick={(e) => {
                        e.stopPropagation()
                        markReadMutation.mutate(item.id)
                      }}
                    >
                      Mark read
                    </Button>
                  )}
                </Stack>
              </Group>
            </Paper>
            )
          })}
        </Stack>
      )}
    </Stack>
  )
}
