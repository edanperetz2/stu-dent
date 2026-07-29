import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { notifications } from '@mantine/notifications'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { API_BASE_URL } from '../api/httpClient'
import type { NotificationType, RealtimeEvent } from '../api/types'

interface RealtimeContextValue {
  isConnected: boolean
}

const RealtimeContext = createContext<RealtimeContextValue>({ isConnected: false })

const RECONNECT_DELAY_MS = 3000

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

/**
 * Opens the backend's /ws connection (Phase 4) once authenticated,
 * authenticating via a first message rather than a query param, and relays
 * events by invalidating the matching TanStack Query cache key, so a push
 * just triggers a normal refetch rather than needing a second, separate
 * state layer.
 */
export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [isConnected, setIsConnected] = useState(false)
  const socketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    if (!principal) {
      setIsConnected(false)
      return
    }

    let cancelled = false
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    function connect() {
      if (cancelled || !principal) return
      const socket = new WebSocket(wsUrl())
      socketRef.current = socket

      // The token is sent as the first message instead of a `?token=`
      // query param -- a query string ends up in access logs/proxy logs/
      // browser history, and a leaked log line would be a replayable
      // bearer token for the rest of its life.
      socket.onopen = () => {
        socket.send(JSON.stringify({ token: principal.token }))
        setIsConnected(true)
      }

      socket.onclose = () => {
        setIsConnected(false)
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
        }
      }

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data) as RealtimeEvent
        if (data.event === 'notification') {
          const notificationType = data.notification_type as NotificationType | undefined
          const message = data.message as string | undefined
          if (notificationType && message && TOAST_NOTIFICATION_TYPES.has(notificationType)) {
            notifications.show({ message, color: 'blue' })
          }
          queryClient.invalidateQueries({ queryKey: ['notifications'] })
          // A notification can document a change to an appointment the
          // recipient didn't make themselves -- a reminder, an expiry, or
          // (see services/waitlist.py) a waitlist entry auto-promoted into
          // a brand-new appointment. Without this, a student/patient/
          // attending with /appointments open wouldn't see it appear until
          // a manual refresh.
          queryClient.invalidateQueries({ queryKey: ['appointments'] })
          queryClient.invalidateQueries({ queryKey: ['waitlist'] })
          queryClient.invalidateQueries({ queryKey: ['resources'] })
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

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [principal, queryClient])

  return (
    <RealtimeContext.Provider value={{ isConnected }}>{children}</RealtimeContext.Provider>
  )
}

export function useRealtime(): RealtimeContextValue {
  return useContext(RealtimeContext)
}
