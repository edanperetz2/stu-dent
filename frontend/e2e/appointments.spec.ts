import { expect, test } from '@playwright/test'
import {
  createPatient,
  createRoom,
  fillAppointmentWhenWhere,
  futureDateString,
  logout,
  openNewAppointmentModal,
  registerUser,
  uniqueEmail,
} from './helpers'

test('a student books an appointment for their patient in a real room, and it shows up in the list', async ({
  page,
}) => {
  const roomName = `E2E Room ${Date.now()}`

  // Rooms are admin-only -- create one as a fresh admin first, matching
  // real usage (this app has no seeded/global "default room").
  const adminEmail = uniqueEmail('e2e-admin')
  await registerUser(page, {
    fullName: 'E2E Admin',
    email: adminEmail,
    password: 'password12345',
    role: 'admin',
  })
  await createRoom(page, roomName)
  await logout(page)

  const studentEmail = uniqueEmail('e2e-student')
  await registerUser(page, {
    fullName: 'E2E Booking Student',
    email: studentEmail,
    password: 'password12345',
  })

  const patientName = `E2E Patient ${Date.now()}`
  await createPatient(page, {
    fullName: patientName,
    email: uniqueEmail('e2e-patient'),
    password: 'password12345',
  })

  await openNewAppointmentModal(page)
  await fillAppointmentWhenWhere(page, {
    patientName,
    roomName,
    dateString: futureDateString(45),
    time: '10:00',
  })
  await page.getByRole('button', { name: 'Request' }).click()

  // The real table cell specifically, not any other stray match --
  // Mantine keeps closed-modal content mounted-but-hidden by default, so a
  // bare getByText(patientName) can match the New Appointment modal's own
  // (now closed) Patient select too.
  await expect(page.getByRole('cell', { name: patientName, exact: false })).toBeVisible()
})
