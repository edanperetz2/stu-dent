import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import {
  getUnreadNotificationCount,
  listNotifications,
  markNotificationRead,
  markNotificationUnread,
} from './notifications'

describe('notifications api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listNotifications requests GET /notifications with unread_only/limit/offset as query params', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listNotifications('tok', true, { limit: 20, offset: 10 })

    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/notifications?')
    expect(call.url).toContain('unread_only=true')
    expect(call.url).toContain('limit=20')
    expect(call.url).toContain('offset=10')
  })

  it('getUnreadNotificationCount requests GET /notifications/unread-count', async () => {
    const fetchMock = mockFetchOnce(200, { count: 0 })
    await getUnreadNotificationCount('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/notifications/unread-count')
  })

  it('markNotificationRead requests POST /notifications/:id/read', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await markNotificationRead('tok', 'notif-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/notifications/notif-1/read')
    expect(call.method).toBe('POST')
  })

  it('markNotificationUnread requests POST /notifications/:id/unread', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await markNotificationUnread('tok', 'notif-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/notifications/notif-1/unread')
    expect(call.method).toBe('POST')
  })
})
