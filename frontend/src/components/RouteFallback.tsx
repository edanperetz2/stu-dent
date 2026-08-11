import { Center, Loader } from '@mantine/core'
import { useEffect, useState } from 'react'

/** Shared loading placeholder for anything that blocks rendering a route:
 * a lazy-loaded page chunk (AppRouter's Suspense boundary) or the auth
 * bootstrap check (RequireAuth) -- previously RequireAuth returned `null`
 * during its loading window, producing a blank flash on a hard refresh of
 * any protected route instead of reusing this. */
export function RouteFallback({ delayed = false }: { delayed?: boolean }) {
  const [visible, setVisible] = useState(!delayed)

  useEffect(() => {
    if (!delayed) return
    const timer = window.setTimeout(() => setVisible(true), 120)
    return () => window.clearTimeout(timer)
  }, [delayed])

  if (!visible) return null

  return (
    <Center h="60vh" className="route-fallback">
      <Loader />
    </Center>
  )
}
