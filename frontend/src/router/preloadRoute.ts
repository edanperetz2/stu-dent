const routeImports: Record<string, () => Promise<unknown>> = {
  '/admin/equipment': () => import('../pages/admin/EquipmentPage'),
  '/admin/rooms': () => import('../pages/admin/RoomsPage'),
  '/admin/users': () => import('../pages/admin/UsersPage'),
  '/appointments': () => import('../pages/appointments/AppointmentsListPage'),
  '/feedback': () => import('../pages/feedback/FeedbackPage'),
  '/forum': () => import('../pages/forum/ForumListPage'),
  '/messages': () => import('../pages/messages/MessagesPage'),
  '/notifications': () => import('../pages/notifications/NotificationsPage'),
  '/patients': () => import('../pages/patients/PatientsListPage'),
  '/preferences': () => import('../pages/preferences/PreferencesPage'),
  '/reports': () => import('../pages/reports/ReportsPage'),
  '/waitlist': () => import('../pages/waitlist/WaitlistPage'),
}

/** Begin fetching a code-split route as soon as a user shows intent to open
 * it. Dynamic imports are module-cached, so React.lazy reuses the same chunk
 * when navigation follows and subsequent calls have no extra network cost. */
export function preloadRoute(path: string): Promise<unknown> | undefined {
  return routeImports[path]?.()
}
