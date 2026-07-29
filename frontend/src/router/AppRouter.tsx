import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { RouteFallback } from '../components/RouteFallback'
import { AppLayout } from '../layouts/AppLayout'
import { AuthLayout } from '../layouts/AuthLayout'
import { RequireAuth } from './RequireAuth'

// Lazy-loaded so each route ships as its own chunk instead of all ~19 pages
// (including admin/role-gated ones most users never visit) in one bundle.
// .then(...) maps each page's named export to the default export
// React.lazy() requires, so no page file needs to change its export style.
const EquipmentPage = lazy(() =>
  import('../pages/admin/EquipmentPage').then((m) => ({ default: m.EquipmentPage })),
)
const RoomsPage = lazy(() =>
  import('../pages/admin/RoomsPage').then((m) => ({ default: m.RoomsPage })),
)
const UsersPage = lazy(() =>
  import('../pages/admin/UsersPage').then((m) => ({ default: m.UsersPage })),
)
const AppointmentsListPage = lazy(() =>
  import('../pages/appointments/AppointmentsListPage').then((m) => ({
    default: m.AppointmentsListPage,
  })),
)
const LoginPage = lazy(() =>
  import('../pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })),
)
const RegisterPage = lazy(() =>
  import('../pages/auth/RegisterPage').then((m) => ({ default: m.RegisterPage })),
)
const FeedbackPage = lazy(() =>
  import('../pages/feedback/FeedbackPage').then((m) => ({ default: m.FeedbackPage })),
)
const ForumListPage = lazy(() =>
  import('../pages/forum/ForumListPage').then((m) => ({ default: m.ForumListPage })),
)
const MessagesPage = lazy(() =>
  import('../pages/messages/MessagesPage').then((m) => ({ default: m.MessagesPage })),
)
const NotificationsPage = lazy(() =>
  import('../pages/notifications/NotificationsPage').then((m) => ({
    default: m.NotificationsPage,
  })),
)
const PatientsListPage = lazy(() =>
  import('../pages/patients/PatientsListPage').then((m) => ({ default: m.PatientsListPage })),
)
const PreferencesPage = lazy(() =>
  import('../pages/preferences/PreferencesPage').then((m) => ({ default: m.PreferencesPage })),
)
const ReportsPage = lazy(() =>
  import('../pages/reports/ReportsPage').then((m) => ({ default: m.ReportsPage })),
)
const WaitlistPage = lazy(() =>
  import('../pages/waitlist/WaitlistPage').then((m) => ({ default: m.WaitlistPage })),
)

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteFallback />}>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>

          <Route element={<RequireAuth />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Navigate to="/appointments" replace />} />
              <Route path="/patients" element={<PatientsListPage />} />
              <Route path="/appointments" element={<AppointmentsListPage />} />
              <Route path="/waitlist" element={<WaitlistPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/messages" element={<MessagesPage />} />
              <Route path="/preferences" element={<PreferencesPage />} />

              <Route element={<RequireAuth roles={['student', 'admin']} />}>
                <Route path="/forum" element={<ForumListPage />} />
              </Route>

              <Route element={<RequireAuth roles={['student', 'attending']} />}>
                <Route path="/reports" element={<ReportsPage />} />
              </Route>

              <Route element={<RequireAuth roles={['student', 'attending', 'patient']} />}>
                <Route path="/feedback" element={<FeedbackPage />} />
              </Route>

              <Route element={<RequireAuth roles={['admin']} />}>
                <Route path="/admin/users" element={<UsersPage />} />
                <Route path="/admin/rooms" element={<RoomsPage />} />
                <Route path="/admin/equipment" element={<EquipmentPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/appointments" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
