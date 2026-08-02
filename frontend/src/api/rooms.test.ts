import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { createRoom, listActiveRooms, listAllRooms, updateRoom } from './rooms'

describe('rooms api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listActiveRooms requests GET /rooms', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listActiveRooms('tok')
    expect(lastFetchCall(fetchMock).url).toMatch(/\/rooms$/)
  })

  it('listAllRooms requests GET /admin/rooms', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listAllRooms('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/admin/rooms')
  })

  it('createRoom requests POST /admin/rooms with the payload', async () => {
    const fetchMock = mockFetchOnce(201, {})
    await createRoom('tok', { name: 'Room 101' })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/admin/rooms')
    expect(call.method).toBe('POST')
    expect(call.body).toEqual({ name: 'Room 101' })
  })

  it('updateRoom requests PATCH /admin/rooms/:id with the payload', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await updateRoom('tok', 'room-1', { is_active: false })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/admin/rooms/room-1')
    expect(call.method).toBe('PATCH')
    expect(call.body).toEqual({ is_active: false })
  })
})
