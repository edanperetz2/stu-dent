import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import {
  cancelWaitlistEntry,
  getWaitlistEntry,
  joinWaitlist,
  listWaitlistEntries,
  reactivateWaitlistEntry,
} from './waitlist'

describe('waitlist api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listWaitlistEntries requests GET /waitlist', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listWaitlistEntries('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/waitlist')
  })

  it('getWaitlistEntry requests GET /waitlist/:id', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await getWaitlistEntry('tok', 'wl-1')
    expect(lastFetchCall(fetchMock).url).toContain('/waitlist/wl-1')
  })

  it('joinWaitlist requests POST /waitlist with the appointment payload', async () => {
    const fetchMock = mockFetchOnce(201, {})
    const payload = { start_time: '2026-01-01T09:00:00Z', end_time: '2026-01-01T10:00:00Z' }
    await joinWaitlist('tok', payload)
    const call = lastFetchCall(fetchMock)
    expect(call.url).toMatch(/\/waitlist$/)
    expect(call.method).toBe('POST')
    expect(call.body).toEqual(payload)
  })

  it('cancelWaitlistEntry requests POST /waitlist/:id/cancel', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await cancelWaitlistEntry('tok', 'wl-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/waitlist/wl-1/cancel')
    expect(call.method).toBe('POST')
  })

  it('reactivateWaitlistEntry requests POST /waitlist/:id/reactivate', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await reactivateWaitlistEntry('tok', 'wl-1')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/waitlist/wl-1/reactivate')
    expect(call.method).toBe('POST')
  })
})
