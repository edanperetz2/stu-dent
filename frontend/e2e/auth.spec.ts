import { expect, test } from '@playwright/test'
import { login, logout, registerUser, uniqueEmail } from './helpers'

test('a new student can register, land in the app, log out, and log back in', async ({ page }) => {
  const email = uniqueEmail('e2e-auth')
  const password = 'password12345'

  await registerUser(page, { fullName: 'E2E Auth Student', email, password })
  await expect(page.getByRole('link', { name: 'Appointments' })).toBeVisible()

  await logout(page)

  await login(page, email, password)
  await expect(page.getByRole('link', { name: 'Appointments' })).toBeVisible()
})

test('a wrong password is rejected with a real error, not a silent failure', async ({ page }) => {
  const email = uniqueEmail('e2e-auth-wrong')
  await registerUser(page, { fullName: 'E2E Wrong Password', email, password: 'password12345' })
  await logout(page)

  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill('not-the-real-password')
  await page.getByRole('button', { name: 'Log in' }).click()

  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page).toHaveURL(/\/login/)
})
