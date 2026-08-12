import { expect, type Page } from '@playwright/test'

// Real, self-service registration is genuinely how every account in this
// app gets created (see the "no admin gating on signup" known limitation) --
// so E2E specs create their own fresh accounts/rooms/patients per run
// rather than depending on seeded demo data. This makes each spec
// independently repeatable and avoids any shared-fixture ordering issues.
export function uniqueEmail(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 100000)}@example.com`
}

export async function registerUser(
  page: Page,
  options: { fullName: string; email: string; password: string; role?: 'student' | 'admin' },
): Promise<void> {
  await page.goto('/register')
  await page.getByLabel('Full name').fill(options.fullName)
  if (options.role && options.role !== 'student') {
    await page.getByRole('combobox', { name: 'Role' }).click()
    await page.getByRole('option', { name: options.role, exact: false }).click()
  }
  await page.getByLabel('Email', { exact: true }).fill(options.email)
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(options.password)
  await page.getByRole('button', { name: 'Register' }).click()
  await expect(page).toHaveURL(/\/appointments/)
}

export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page).toHaveURL(/\/appointments/)
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login/)
}

export async function createRoom(page: Page, name: string): Promise<void> {
  await page.goto('/admin/rooms')
  await page.getByRole('button', { name: 'New Room' }).click()
  await page.getByLabel('Name').fill(name)
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText(name)).toBeVisible()
}

export async function createPatient(
  page: Page,
  options: { fullName: string; email: string; password: string },
): Promise<void> {
  await page.goto('/patients')
  await page.getByRole('button', { name: 'New Patient' }).click()
  await page.getByLabel('Full name').fill(options.fullName)
  await page.getByLabel('Email').fill(options.email)
  await page.getByRole('textbox', { name: 'Password', exact: true }).fill(options.password)
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByText(options.fullName)).toBeVisible()
}

/** DD/MM/YYYY string N days from today -- far enough out to never collide
 * with "today" edge cases (past-time rejection, etc.) across time zones. */
export function futureDateString(daysFromNow: number): string {
  const date = new Date()
  date.setDate(date.getDate() + daysFromNow)
  const dd = String(date.getDate()).padStart(2, '0')
  const mm = String(date.getMonth() + 1).padStart(2, '0')
  const yyyy = date.getFullYear()
  return `${dd}/${mm}/${yyyy}`
}

export async function openNewAppointmentModal(page: Page): Promise<void> {
  await page.goto('/appointments')
  await page.getByRole('button', { name: 'New Appointment' }).click()
}

export async function fillAppointmentWhenWhere(
  page: Page,
  options: { patientName: string; roomName: string; dateString: string; time: string },
): Promise<void> {
  await page.getByRole('combobox', { name: 'Patient' }).click()
  await page.getByRole('option', { name: options.patientName }).click()

  // Mantine's DateInput needs real keystroke events (its internal mask
  // parses as you type) -- a bulk .fill() sets the DOM value without
  // firing them, so the field never actually registers a date and
  // "Start time is required" silently blocks submission later. No Escape
  // key either: the date popover isn't necessarily open after typing, so
  // Escape would instead bubble up to Mantine's Modal, which listens for
  // it globally and closes the whole "New Appointment" dialog. Clicking
  // straight into the Time select both blurs/commits the typed date and
  // moves focus, without risking that.
  const startTimeInput = page.getByLabel('Start time')
  await startTimeInput.click()
  await startTimeInput.pressSequentially(options.dateString)
  await page.getByRole('combobox', { name: 'Time' }).click()
  await page.getByRole('option', { name: options.time }).click()

  await page.getByRole('combobox', { name: 'Room' }).click()
  await page.getByRole('option', { name: options.roomName }).click()
}
