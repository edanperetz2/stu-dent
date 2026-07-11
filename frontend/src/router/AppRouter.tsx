import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '../layouts/AppLayout'
import { AuthLayout } from '../layouts/AuthLayout'
import { EquipmentPage } from '../pages/admin/EquipmentPage'
import { RoomsPage } from '../pages/admin/RoomsPage'
import { UsersPage } from '../pages/admin/UsersPage'
import { AppointmentDetailPage } from '../pages/appointments/AppointmentDetailPage'
import { AppointmentsListPage } from '../pages/appointments/AppointmentsListPage'
import { LoginPage } from '../pages/auth/LoginPage'
import { RegisterPage } from '../pages/auth/RegisterPage'
import { AvailabilityPage } from '../pages/availability/AvailabilityPage'
import { ForumListPage } from '../pages/forum/ForumListPage'
import { ForumPostPage } from '../pages/forum/ForumPostPage'
import { MessagesPage } from '../pages/messages/MessagesPage'
import { NotificationsPage } from '../pages/notifications/NotificationsPage'
import { PatientDetailPage } from '../pages/patients/PatientDetailPage'
import { PatientsListPage } from '../pages/patients/PatientsListPage'
import { PlaceholderPage } from '../pages/PlaceholderPage'
import { PreferencesPage } from '../pages/preferences/PreferencesPage'
import { WaitlistPage } from '../pages/waitlist/WaitlistPage'
import { RequireAuth } from './RequireAuth'

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>

        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<PlaceholderPage title="Dashboard" />} />
            <Route path="/patients" element={<PatientsListPage />} />
            <Route path="/patients/:patientId" element={<PatientDetailPage />} />
            <Route path="/appointments" element={<AppointmentsListPage />} />
            <Route path="/appointments/:appointmentId" element={<AppointmentDetailPage />} />
            <Route path="/availability" element={<AvailabilityPage />} />
            <Route path="/waitlist" element={<WaitlistPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="/messages" element={<MessagesPage />} />
            <Route path="/preferences" element={<PreferencesPage />} />

            <Route element={<RequireAuth roles={['student', 'admin']} />}>
              <Route path="/forum" element={<ForumListPage />} />
              <Route path="/forum/:postId" element={<ForumPostPage />} />
            </Route>

            <Route element={<RequireAuth roles={['admin']} />}>
              <Route path="/admin/users" element={<UsersPage />} />
              <Route path="/admin/rooms" element={<RoomsPage />} />
              <Route path="/admin/equipment" element={<EquipmentPage />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
