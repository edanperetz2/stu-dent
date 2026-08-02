import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { deleteUser, getUser, listAllUsers, updateUser } from './admin'

describe('admin api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listAllUsers requests GET /admin/users', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listAllUsers('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/admin/users')
  })

  it('getUser requests GET /admin/users/:id', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await getUser('tok', 'user-1')
    expect(lastFetchCall(fetchMock).url).toContain('/admin/users/user-1')
  })

  it('updateUser requests PATCH /admin/users/:id with the payload', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await updateUser('tok', 'user-1', { role: 'attending' })
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/admin/users/user-1')
    expect(call.method).toBe('PATCH')
    expect(call.body).toEqual({ role: 'attending' })
  })

  it('deleteUser requests DELETE /admin/users/:id', async () => {
    const fetchMock = mockFetchOnce(204, undefined)
    await deleteUser('tok', 'user-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/admin/users/user-1')
    expect(call.method).toBe('DELETE')
  })
})
