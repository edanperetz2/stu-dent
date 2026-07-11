import { request } from './httpClient'
import type { Notification } from './types'

export function listNotifications(token: string, unreadOnly = false) {
  return request<Notification[]>('/notifications', {
    token,
    query: { unread_only: unreadOnly },
  })
}

export function markNotificationRead(token: string, notificationId: string) {
  return request<Notification>(`/notifications/${notificationId}/read`, {
    method: 'POST',
    token,
  })
}
