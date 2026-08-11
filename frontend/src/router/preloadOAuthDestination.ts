/** Preload the usual post-OAuth destination while `/auth/me` is resolving.
 * Vite reuses the same dynamic-import chunk AppRouter requests, so the app
 * route can replace the callback screen in one paint instead of briefly
 * showing the router-level fallback between them. Other destinations retain
 * the normal Suspense fallback and can be added here if they become common. */
export async function preloadOAuthDestination(path: string): Promise<void> {
  const pathname = path.split(/[?#]/, 1)[0]
  if (pathname === '/' || pathname === '/appointments') {
    await import('../pages/appointments/AppointmentsListPage')
  }
}
