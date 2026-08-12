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

test('booking the same student into two overlapping slots surfaces the real conflict modal, not a raw error', async ({
  page,
}) => {
  const roomName = `E2E Conflict Room ${Date.now()}`

  const adminEmail = uniqueEmail('e2e-conflict-admin')
  await registerUser(page, {
    fullName: 'E2E Conflict Admin',
    email: adminEmail,
    password: 'password12345',
    role: 'admin',
  })
  await createRoom(page, roomName)
  await logout(page)

  await registerUser(page, {
    fullName: 'E2E Conflict Student',
    email: uniqueEmail('e2e-conflict-student'),
    password: 'password12345',
  })

  const patientName = `E2E Conflict Patient ${Date.now()}`
  await createPatient(page, {
    fullName: patientName,
    email: uniqueEmail('e2e-conflict-patient'),
    password: 'password12345',
  })

  const dateString = futureDateString(46)

  // First booking succeeds cleanly.
  await openNewAppointmentModal(page)
  await fillAppointmentWhenWhere(page, { patientName, roomName, dateString, time: '11:00' })
  await page.getByRole('button', { name: 'Request' }).click()
  // The real table cell specifically -- see appointments.spec.ts for why a
  // bare getByText(patientName) isn't reliable here.
  await expect(page.getByRole('cell', { name: patientName, exact: false })).toBeVisible()

  // A second, overlapping booking for the SAME student must be caught as a
  // real, named conflict -- backed by a real Postgres exclusion constraint,
  // not a generic/opaque failure -- and offer a real resolution, not just
  // an error toast.
  await openNewAppointmentModal(page)
  await fillAppointmentWhenWhere(page, { patientName, roomName, dateString, time: '11:00' })
  await page.getByRole('button', { name: 'Request' }).click()

  await expect(page.getByText("This request isn't available")).toBeVisible()
  await expect(page.getByRole('button', { name: 'Join waitlist' })).toBeVisible()
})
