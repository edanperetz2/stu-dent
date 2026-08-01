import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { notifications } from '@mantine/notifications'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { API_BASE_URL } from '../api/httpClient'
import type { NotificationType, RealtimeEvent } from '../api/types'

interface RealtimeContextValue {
  isConnected: boolean
  // True once auto-reconnect has given up after too many consecutive
  // failures in a row -- the UI should offer a manual way back in rather
  // than silently doing nothing forever.
  reconnectExhausted: boolean
  reconnect: () => void
}

const RealtimeContext = createContext<RealtimeContextValue>({
  isConnected: false,
  reconnectExhausted: false,
  reconnect: () => {},
})

const BASE_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 30_000
const MAX_CONSECUTIVE_FAILURES = 8
// The backend closes with this code (see api/routes/websocket.py) only when
// the token itself was rejected -- malformed, expired, or the user no
// longer exists/is active. Retrying with the same dead token would just
// fail identically forever, so this routes into the shared session-expired
// flow instead of the reconnect loop.
const AUTH_FAILURE_CLOSE_CODE = 1008

// Worth interrupting with a toast, not just a quiet badge update -- these
// document something time-sensitive that a user not currently on the
// relevant page would otherwise have no way to notice (a waitlist entry
// auto-booked into a real slot, an appointment rejected/cancelled/approved,
// a resource pulled out from under a booking, something newly needing
// review). Left out on purpose: appointment_reminder/appointment_expired/
// feedback_reminder/patient_registration_request -- routine enough, or
// already visible via the existing nav badges, that a toast for every one
// would just be noise.
const TOAST_NOTIFICATION_TYPES = new Set<NotificationType>([
  'waitlist_slot_available',
  'appointment_status_changed',
  'appointment_created',
  'resource_deactivated',
  'appointment_needs_resolution',
])

function wsUrl(): string {
  const base = API_BASE_URL.replace(/^http/, 'ws')
  return `${base}/ws`
}

/** Invalidated both on a live push (per event type, below) and here on
 * (re)connect -- a gap while disconnected can hide a real change (an
 * auto-promoted waitlist entry, a cancellation) that no later unrelated
 * push would surface, so catching up can't wait for the next push either. */
function invalidateCoreQueries(queryClient: QueryClient): void {
  queryClient.invalidateQueries({ queryKey: ['appointments'] })
  queryClient.invalidateQueries({ queryKey: ['waitlist'] })
  queryClient.invalidateQueries({ queryKey: ['resources'] })
  queryClient.invalidateQueries({ queryKey: ['notifications'] })
}

/**
 * Opens the backend's /ws connection (Phase 4) once authenticated,
 * authenticating via a first message rather than a query param, and relays
 * events by invalidating the matching TanStack Query cache key, so a push
 * just triggers a normal refetch rather than needing a second, separate
 * state layer.
 */
export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { principal, handleSessionExpired } = useAuth()
  const queryClient = useQueryClient()
  const [isConnected, setIsConnected] = useState(false)
  const [reconnectExhausted, setReconnectExhausted] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)
  // A ref, not state -- read/reset from inside WebSocket callbacks without
  // needing the connect effect to re-run on every attempt.
  const failureCountRef = useRef(0)
  const connectRef = useRef<() => void>(() => {})

  useEffect(() => {
    if (!principal) {
      setIsConnected(false)
      setReconnectExhausted(false)
      return
    }

    let cancelled = false
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    failureCountRef.current = 0
    setReconnectExhausted(false)

    function scheduleReconnect() {
      failureCountRef.current += 1
      if (failureCountRef.current > MAX_CONSECUTIVE_FAILURES) {
        setReconnectExhausted(true)
        return
      }
      // Exponential backoff with jitter, capped -- a fixed 3s retry against
      // a backend that's down or restarting meant every open tab hammered
      // it roughly once every 1.5s on average, precisely while it's trying
      // to come back up.
      const delay = Math.min(
        BASE_RECONNECT_DELAY_MS * 2 ** (failureCountRef.current - 1),
        MAX_RECONNECT_DELAY_MS,
      )
      const jitter = delay * (0.5 + Math.random() * 0.5)
      reconnectTimer = setTimeout(connect, jitter)
    }

    function connect() {
      if (cancelled || !principal) return
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      setReconnectExhausted(false)
      const socket = new WebSocket(wsUrl())
      socketRef.current = socket

      // The token is sent as the first message instead of a `?token=`
      // query param -- a query string ends up in access logs/proxy logs/
      // browser history, and a leaked log line would be a replayable
      // bearer token for the rest of its life. `isConnected` isn't flipped
      // true here -- the socket is accepted before the server has
      // authenticated it, so a bad token still opens the socket and only
      // gets closed a moment later; onmessage below waits for the
      // server's own "connected" ack instead.
      socket.onopen = () => {
        socket.send(JSON.stringify({ token: principal.token }))
      }

      socket.onclose = (event) => {
        setIsConnected(false)
        if (cancelled) return
        if (event.code === AUTH_FAILURE_CLOSE_CODE) {
          handleSessionExpired()
          return
        }
        scheduleReconnect()
      }

      socket.onmessage = (event) => {
        let data: RealtimeEvent
        try {
          data = JSON.parse(event.data) as RealtimeEvent
        } catch {
          // A malformed frame (a future/mismatched server version, a
          // truncated message) used to throw straight out of this handler
          // -- degrade to a no-op instead of taking the socket down with it.
          return
        }
        if (data.event === 'connected') {
          setIsConnected(true)
          failureCountRef.current = 0
          invalidateCoreQueries(queryClient)
        } else if (data.event === 'notification') {
          const notificationType = data.notification_type as NotificationType | undefined
          const message = data.message as string | undefined
          if (notificationType && message && TOAST_NOTIFICATION_TYPES.has(notificationType)) {
            notifications.show({ message, color: 'blue' })
          }
          // A notification can document a change to an appointment the
          // recipient didn't make themselves -- a reminder, an expiry, or
          // (see services/waitlist.py) a waitlist entry auto-promoted into
          // a brand-new appointment. Without this, a student/patient/
          // attending with /appointments open wouldn't see it appear until
          // a manual refresh.
          invalidateCoreQueries(queryClient)
          // A feedback_reminder notification means a completed appointment
          // just became pending-feedback -- keep the nav badge and Feedback
          // page's pending list fresh without a manual refresh.
          queryClient.invalidateQueries({ queryKey: ['feedback'] })
        } else if (data.event === 'message') {
          // Broad prefix match: also refreshes the contacts/groups sidebar
          // lists, not just the open thread, since a new message can be the
          // first one in a not-yet-listed conversation.
          queryClient.invalidateQueries({ queryKey: ['messages'] })
        }
      }
    }

    connectRef.current = connect
    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [principal, queryClient, handleSessionExpired])

  const reconnect = useCallback(() => {
    // Doubles as the "manual refresh" action while disconnected -- kicks a
    // fresh connection attempt immediately (bypassing whatever backoff
    // delay is pending) and refetches the core lists right away rather than
    // waiting for the socket to actually reconnect first.
    failureCountRef.current = 0
    setReconnectExhausted(false)
    connectRef.current()
    invalidateCoreQueries(queryClient)
  }, [queryClient])

  return (
    <RealtimeContext.Provider value={{ isConnected, reconnectExhausted, reconnect }}>
      {children}
    </RealtimeContext.Provider>
  )
}

export function useRealtime(): RealtimeContextValue {
  return useContext(RealtimeContext)
}
