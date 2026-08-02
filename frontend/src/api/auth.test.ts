import { afterEach, describe, expect, it, vi } from 'vitest'
import { lastFetchCall, mockFetchOnce } from '../test/mockFetch'
import {
  confirmPasswordReset,
  getCurrentUser,
  login,
  registerUser,
  requestPasswordReset,
  updateCurrentUser,
} from './auth'

describe('auth api', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('registerUser requests POST /auth/register, omitting owner_student_id when not a patient', async () => {
    const fetchMock = mockFetchOnce(201, {})
    await registerUser('s@example.com', 'password123', 'Stu Dent', 'student')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/auth/register')
    expect(call.method).toBe('POST')
    expect(call.body).toEqual({
      email: 's@example.com',
      password: 'password123',
      full_name: 'Stu Dent',
      role: 'student',
    })
  })

  it('registerUser includes owner_student_id when given (patient self-registration)', async () => {
    const fetchMock = mockFetchOnce(201, {})
    await registerUser('p@example.com', 'password123', 'Pat Ient', 'patient', 'student-1')
    const call = lastFetchCall(fetchMock)
    expect(call.body).toMatchObject({ owner_student_id: 'student-1' })
  })

  it('login requests POST /auth/login, omitting role when not given', async () => {
    const fetchMock = mockFetchOnce(200, { access_token: 'tok', token_type: 'bearer' })
    await login('s@example.com', 'password123')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/auth/login')
    expect(call.body).toEqual({ email: 's@example.com', password: 'password123' })
  })

  it('getCurrentUser requests GET /users/me with the token', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await getCurrentUser('tok')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/users/me')
    expect(call.headers.Authorization).toBe('Bearer tok')
  })

  it('updateCurrentUser requests PATCH /users/me with the payload', async () => {
    const fetchMock = mockFetchOnce(200, {})
    await updateCurrentUser('tok', { contact_phone: '555-1234' })
    const call = lastFetchCall(fetchMock)
    expect(call.method).toBe('PATCH')
    expect(call.body).toEqual({ contact_phone: '555-1234' })
  })

  it('requestPasswordReset requests POST /auth/password-reset/request with the email', async () => {
    const fetchMock = mockFetchOnce(204, undefined)
    await requestPasswordReset('s@example.com')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/auth/password-reset/request')
    expect(call.body).toEqual({ email: 's@example.com' })
  })

  it('confirmPasswordReset requests POST /auth/password-reset/confirm with token + new_password', async () => {
    const fetchMock = mockFetchOnce(204, undefined)
    await confirmPasswordReset('reset-tok', 'newpassword456')
    const call = lastFetchCall(fetchMock)
    expect(call.url).toContain('/auth/password-reset/confirm')
    expect(call.body).toEqual({ token: 'reset-tok', new_password: 'newpassword456' })
  })
})
