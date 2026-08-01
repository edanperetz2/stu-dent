import { MantineProvider } from '@mantine/core'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { authContextMock, fakePrincipal } from '../test/authMocks'
import { RealtimeProvider, useRealtime } from './RealtimeContext'

const handleSessionExpired = vi.fn()

vi.mock('../auth/AuthContext', () => {
  const mock = authContextMock(fakePrincipal('student'))
  return { ...mock, useAuth: () => ({ ...mock.useAuth(), handleSessionExpired }) }
})

class MockWebSocket {
  static instances: MockWebSocket[] = []
  url: string
  onopen: (() => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  sent: string[] = []
  closed = false

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close() {
    this.closed = true
  }
}

function Probe() {
  const { isConnected, reconnectExhausted, reconnect } = useRealtime()
  return (
    <div>
      <div data-testid="connected">{String(isConnected)}</div>
      <div data-testid="exhausted">{String(reconnectExhausted)}</div>
      <button onClick={reconnect}>manual-reconnect</button>
    </div>
  )
}

function renderRealtime() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <MantineProvider>
      <QueryClientProvider client={queryClient}>
        <RealtimeProvider>
          <Probe />
        </RealtimeProvider>
      </QueryClientProvider>
    </MantineProvider>,
  )
}

function latestSocket(): MockWebSocket {
  return MockWebSocket.instances[MockWebSocket.instances.length - 1]
}

describe('RealtimeProvider', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    handleSessionExpired.mockClear()
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('does not crash on a malformed message frame', async () => {
    renderRealtime()

    await act(async () => {
      latestSocket().onopen?.()
    })
    await act(async () => {
      latestSocket().onmessage?.({ data: 'not json{{{' })
    })

    // Still functioning afterwards -- a real "connected" ack right after
    // the bad frame is still processed normally.
    await act(async () => {
      latestSocket().onmessage?.({ data: JSON.stringify({ event: 'connected' }) })
    })
    expect(screen.getByTestId('connected').textContent).toBe('true')
  })

  it('routes the auth-failure close code (1008) into the shared session-expired flow instead of retrying', async () => {
    renderRealtime()
    const socketCountBefore = MockWebSocket.instances.length

    await act(async () => {
      latestSocket().onclose?.({ code: 1008 })
    })

    expect(handleSessionExpired).toHaveBeenCalledTimes(1)
    // No reconnect attempt was scheduled for an auth failure.
    expect(MockWebSocket.instances.length).toBe(socketCountBefore)
  })

  it('schedules a reconnect with backoff after a non-auth close, not immediately', async () => {
    vi.useFakeTimers()
    renderRealtime()
    const socketCountBefore = MockWebSocket.instances.length

    await act(async () => {
      latestSocket().onclose?.({ code: 1006 })
    })
    // Nothing new yet -- the very first backoff delay hasn't elapsed.
    expect(MockWebSocket.instances.length).toBe(socketCountBefore)
    expect(handleSessionExpired).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(MockWebSocket.instances.length).toBe(socketCountBefore + 1)
  })

  it('stops auto-reconnecting after too many consecutive failures, and a manual reconnect recovers', async () => {
    vi.useFakeTimers()
    renderRealtime()

    // Fail enough times in a row to exceed the cap -- each failure's
    // backoff delay is capped at 30s, so 35s per round is always enough to
    // trigger the next attempt.
    for (let i = 0; i < 9; i++) {
      await act(async () => {
        latestSocket().onclose?.({ code: 1006 })
        await vi.advanceTimersByTimeAsync(35_000)
      })
    }

    expect(screen.getByTestId('exhausted').textContent).toBe('true')
    const countWhenExhausted = MockWebSocket.instances.length

    vi.useRealTimers()
    await userEvent.click(screen.getByText('manual-reconnect'))

    expect(MockWebSocket.instances.length).toBe(countWhenExhausted + 1)
    expect(screen.getByTestId('exhausted').textContent).toBe('false')
  })
})
