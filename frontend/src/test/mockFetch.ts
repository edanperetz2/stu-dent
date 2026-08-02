import { vi } from 'vitest'

/** Stubs global fetch to resolve once with a given status/body -- shared
 * by every `src/api/*.test.ts` file so each can assert the exact URL,
 * method, and body/query it produces against a mocked `fetch`, not just
 * that it delegates to `request()` (which would only prove internal
 * consistency, not that the URL actually matches a real backend route).
 * Callers must reset via `vi.unstubAllGlobals()` in their own afterEach. */
export function mockFetchOnce(status = 200, body: unknown = {}) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: 'OK',
    json: async () => body,
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** The URL + init object `fetch` was actually called with, decomposed for
 * easy assertions (`expect(lastFetchCall(mock).method).toBe('POST')`
 * reads better than indexing into `mock.calls.at(-1)` by hand everywhere). */
export function lastFetchCall(fetchMock: ReturnType<typeof vi.fn>) {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit]
  return {
    url,
    method: init.method,
    body: init.body ? JSON.parse(init.body as string) : undefined,
    headers: init.headers as Record<string, string>,
  }
}
