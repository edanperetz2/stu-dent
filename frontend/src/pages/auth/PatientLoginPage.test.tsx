import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { renderWithProviders } from '../../test/renderWithProviders'
import { PatientLoginPage } from './PatientLoginPage'

vi.mock('../../api/auth')

describe('PatientLoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('logs in a patient and persists the session', async () => {
    vi.mocked(authApi.patientLogin).mockResolvedValue({
      access_token: 'ptok789',
      token_type: 'bearer',
    })
    vi.mocked(authApi.getCurrentPatient).mockResolvedValue({
      id: 'p1',
      owner_student_id: 's1',
      full_name: 'Pat Patient',
      contact_phone: null,
      email: 'pat@example.com',
      is_active: true,
      preferred_time_of_day: null,
    })

    renderWithProviders(<PatientLoginPage />, { route: '/patient-login' })

    await userEvent.type(screen.getByLabelText('Email'), 'pat@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    await waitFor(() => {
      expect(authApi.patientLogin).toHaveBeenCalledWith('pat@example.com', 'password123')
    })
    expect(JSON.parse(localStorage.getItem('stu_dent_auth')!)).toEqual({
      kind: 'patient',
      token: 'ptok789',
    })
  })
})
