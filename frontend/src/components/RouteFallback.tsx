import { Center, Loader } from '@mantine/core'

/** Shared loading placeholder for anything that blocks rendering a route:
 * a lazy-loaded page chunk (AppRouter's Suspense boundary) or the auth
 * bootstrap check (RequireAuth) -- previously RequireAuth returned `null`
 * during its loading window, producing a blank flash on a hard refresh of
 * any protected route instead of reusing this. */
export function RouteFallback() {
  return (
    <Center h="60vh">
      <Loader />
    </Center>
  )
}
