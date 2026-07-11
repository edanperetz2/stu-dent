import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '../layouts/AppLayout'
import { AuthLayout } from '../layouts/AuthLayout'
import { PlaceholderPage } from '../pages/PlaceholderPage'
import { RequireAuth } from './RequireAuth'

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<PlaceholderPage title="Login" />} />
          <Route path="/register" element={<PlaceholderPage title="Register" />} />
          <Route path="/patient-login" element={<PlaceholderPage title="Patient login" />} />
        </Route>

        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<PlaceholderPage title="Dashboard" />} />
            <Route path="/patients" element={<PlaceholderPage title="Patients" />} />
            <Route
              path="/patients/:patientId"
              element={<PlaceholderPage title="Patient detail" />}
            />
            <Route path="/appointments" element={<PlaceholderPage title="Appointments" />} />
            <Route
              path="/appointments/:appointmentId"
              element={<PlaceholderPage title="Appointment detail" />}
            />
            <Route path="/availability" element={<PlaceholderPage title="Availability" />} />
            <Route path="/waitlist" element={<PlaceholderPage title="Waitlist" />} />
            <Route path="/forum" element={<PlaceholderPage title="Forum" />} />
            <Route path="/forum/:postId" element={<PlaceholderPage title="Post" />} />
            <Route path="/notifications" element={<PlaceholderPage title="Notifications" />} />
            <Route path="/messages" element={<PlaceholderPage title="Messages" />} />
            <Route path="/preferences" element={<PlaceholderPage title="Preferences" />} />
            <Route path="/admin/users" element={<PlaceholderPage title="Users" />} />
            <Route path="/admin/rooms" element={<PlaceholderPage title="Rooms" />} />
            <Route path="/admin/equipment" element={<PlaceholderPage title="Equipment" />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
