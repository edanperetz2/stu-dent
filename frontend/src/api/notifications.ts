import { request } from './httpClient'
import type { Notification } from './types'

export function listNotifications(
  token: string,
  unreadOnly = false,
  options: { limit?: number; offset?: number } = {},
) {
  return request<Notification[]>('/notifications', {
    token,
    query: { unread_only: unreadOnly, limit: options.limit, offset: options.offset },
  })
}

export function getUnreadNotificationCount(token: string) {
  return request<{ count: number }>('/notifications/unread-count', { token })
}

export function markNotificationRead(token: string, notificationId: string) {
  return request<Notification>(`/notifications/${notificationId}/read`, {
    method: 'POST',
    token,
  })
}

export function markNotificationUnread(token: string, notificationId: string) {
  return request<Notification>(`/notifications/${notificationId}/unread`, {
    method: 'POST',
    token,
  })
}
