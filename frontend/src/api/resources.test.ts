import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { getResourcesSchedule } from './resources'

describe('resources api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('getResourcesSchedule requests GET /resources/schedule with the token', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await getResourcesSchedule('tok')

    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/resources/schedule')
    expect(call.method).toBe('GET')
    expect(call.headers.Authorization).toBe('Bearer tok')
  })
})
