import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { listAttendings } from './attendings'

describe('attendings api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listAttendings requests GET /attendings with the token', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listAttendings('tok')

    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/attendings')
    expect(call.method).toBe('GET')
    expect(call.headers.Authorization).toBe('Bearer tok')
  })
})
