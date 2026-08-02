import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { listStudents } from './students'

describe('students api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listStudents requests GET /students with no auth header (public endpoint)', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listStudents()

    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/students')
    expect(call.method).toBe('GET')
    expect(call.headers.Authorization).toBeUndefined()
  })
})
