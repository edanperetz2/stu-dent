import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { interpretSchedulingRequest } from './schedulingAssistant'

describe('schedulingAssistant api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('interpretSchedulingRequest requests POST /scheduling/interpret with the text in the body', async () => {
    const fetchMock = mockFetchOnce(200, { warnings: [] })
    await interpretSchedulingRequest('tok', 'book Jane friday afternoon')

    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/scheduling/interpret')
    expect(call.method).toBe('POST')
    expect(call.body).toEqual({ text: 'book Jane friday afternoon' })
  })
})
