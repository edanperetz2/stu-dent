import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../auth/AuthContext'
import { API_BASE_URL } from '../api/httpClient'
import type { RealtimeEvent } from '../api/types'

interface RealtimeContextValue {
  isConnected: boolean
}

const RealtimeContext = createContext<RealtimeContextValue>({ isConnected: false })

const RECONNECT_DELAY_MS = 3000

function wsUrl(token: string): string {
  const base = API_BASE_URL.replace(/^http/, 'ws')
  return `${base}/ws?token=${encodeURIComponent(token)}`
}

/**
 * Opens the backend's /ws?token= connection (Phase 4) once authenticated and
 * relays events by invalidating the matching TanStack Query cache key, so a
 * push just triggers a normal refetch rather than needing a second,
 * separate state layer.
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
      const socket = new WebSocket(wsUrl(principal.token))
      socketRef.current = socket

      socket.onopen = () => setIsConnected(true)

      socket.onclose = () => {
        setIsConnected(false)
        if (!cancelled) {
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
        }
      }

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data) as RealtimeEvent
        if (data.event === 'notification') {
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
