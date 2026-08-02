import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import {
  createGroup,
  getThreadSummaries,
  getUnreadCount,
  listContacts,
  listGroups,
  listMessages,
  markRead,
  markUnread,
  sendMessage,
  targetKey,
  type MessageTarget,
} from './messages'

describe('messages api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listContacts requests GET /messages/contacts', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listContacts('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/messages/contacts')
  })

  it('listGroups requests GET /messages/groups', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listGroups('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/messages/groups')
  })

  it('createGroup requests POST /messages/groups with title and participant_ids', async () => {
    const fetchMock = mockFetchOnce(201, {})
    await createGroup('tok', 'Case review', ['s1', 's2'])
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/messages/groups')
    expect(call.method).toBe('POST')
    expect(call.body).toEqual({ title: 'Case review', participant_ids: ['s1', 's2'] })
  })

  it('getUnreadCount requests GET /messages/unread-count', async () => {
    const fetchMock = mockFetchOnce(200, { count: 0 })
    await getUnreadCount('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/messages/unread-count')
  })

  it('getThreadSummaries requests GET /messages/thread-summaries', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await getThreadSummaries('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/messages/thread-summaries')
  })

  describe('per-target routing (direct / admin / group)', () => {
    const direct: MessageTarget = { kind: 'direct', otherUserId: 'user-1' }
    const adminSelf: MessageTarget = { kind: 'admin' }
    const adminInbox: MessageTarget = { kind: 'admin', ownerId: 'user-2' }
    const group: MessageTarget = { kind: 'group', conversationId: 'convo-1' }

    it('targetKey builds a distinct key per target kind', () => {
      expect(targetKey(direct)).toBe('direct:user-1')
      expect(targetKey(adminSelf)).toBe('admin:self')
      expect(targetKey(adminInbox)).toBe('admin:user-2')
      expect(targetKey(group)).toBe('group:convo-1')
    })

    it('listMessages resolves each target to the right path', async () => {
      const fetchMock = mockFetchOnce(200, [])
      await listMessages('tok', direct)
      expect(lastFetchCall(fetchMock).url).toContain('/messages/direct/user-1')

      await listMessages('tok', adminSelf)
      expect(lastFetchCall(fetchMock).url).toContain('/messages/admin')
      expect(lastFetchCall(fetchMock).url).not.toContain('/messages/admin-inbox')

      await listMessages('tok', adminInbox)
      expect(lastFetchCall(fetchMock).url).toContain('/messages/admin-inbox/user-2')

      await listMessages('tok', group)
      expect(lastFetchCall(fetchMock).url).toContain('/messages/groups/convo-1')
    })

    it('sendMessage posts the body to the resolved target path', async () => {
      const fetchMock = mockFetchOnce(201, {})
      await sendMessage('tok', direct, 'hello')
      const call = lastFetchCall(fetchMock)
      expect(call.url).toContain('/messages/direct/user-1')
      expect(call.method).toBe('POST')
      expect(call.body).toEqual({ body: 'hello' })
    })

    it('markRead / markUnread hit the target path with /read or /unread appended', async () => {
      const fetchMock = mockFetchOnce(200, { last_read_at: null })
      await markRead('tok', group)
      expect(lastFetchCall(fetchMock).url).toContain('/messages/groups/convo-1/read')

      await markUnread('tok', group)
      expect(lastFetchCall(fetchMock).url).toContain('/messages/groups/convo-1/unread')
    })
  })
})
