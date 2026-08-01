import { Badge, Button, Group, Paper, Stack, Switch, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listNotifications,
  markNotificationRead,
  markNotificationUnread,
} from '../../api/notifications'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuthToken } from '../../auth/useAuthToken'
import { CardListSkeleton } from '../../components/Skeletons'
import { EmptyText, ErrorText } from '../../components/StateText'
import { formatDateTime } from '../../utils/dates'

function formatType(notificationType: string): string {
  return notificationType
    .split('_')
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')
}

const PAGE_SIZE = 30

export function NotificationsPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [unreadOnly, setUnreadOnly] = useState(false)

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['notifications', unreadOnly],
    queryFn: ({ pageParam }) =>
      listNotifications(token, unreadOnly, { limit: PAGE_SIZE, offset: pageParam }),
    initialPageParam: 0,
    // A page shorter than PAGE_SIZE means the server had nothing left to
    // give -- offset for the next page is just how many rows loaded so far.
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === PAGE_SIZE
        ? allPages.reduce((sum, page) => sum + page.length, 0)
        : undefined,
  })
  const items = data?.pages.flat()

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

      {isError ? (
        <ErrorText onRetry={() => refetch()}>
          {apiErrorMessage(error, 'Failed to load notifications.')}
        </ErrorText>
      ) : isLoading ? (
        <CardListSkeleton count={6} />
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
              className={isLinkable ? 'list-item-enter cursor-pointer' : 'list-item-enter'}
              bg={item.read_at ? undefined : 'var(--mantine-color-blue-0)'}
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
                  <Text size="xs" c="dimmed" className="text-nowrap">
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
          {hasNextPage && (
            <Button
              variant="subtle"
              onClick={() => fetchNextPage()}
              loading={isFetchingNextPage}
              // No Mantine shorthand for align-self.
              style={{ alignSelf: 'center' }}
            >
              Load more
            </Button>
          )}
        </Stack>
      )}
    </Stack>
  )
}
