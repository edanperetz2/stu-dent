import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import { askQuestion, generateReport, listReports } from './reports'

describe('reports api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('listReports requests GET /reports', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await listReports('tok')
    expect(lastFetchCall(fetchMock).url).toContain('/reports')
    expect(lastFetchCall(fetchMock).method).toBe('GET')
  })

  it('generateReport requests POST /reports/generate', async () => {
    const fetchMock = mockFetchOnce(200, [])
    await generateReport('tok')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/reports/generate')
    expect(call.method).toBe('POST')
  })

  it('askQuestion requests POST /reports/ask with the question in the body', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await askQuestion('tok', 'which room is underused?')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/reports/ask')
    expect(call.method).toBe('POST')
    expect(call.body).toEqual({ question: 'which room is underused?' })
  })
})
