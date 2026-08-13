import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as adminApi from '../../api/admin'
import type { User } from '../../api/types'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { roleOptionsFor, UsersPage } from './UsersPage'

vi.mock('../../api/admin')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('admin')))

function fakeUser(overrides: Partial<User>): User {
  return {
    id: 'user-id',
    email: 'user@example.com',
    full_name: 'Test User',
    role: 'student',
    is_active: true,
    owner_student_id: null,
    owner_student_name: null,
    owner_confirmed_at: null,
    contact_phone: null,
    preferred_time_of_day: null,
    ...overrides,
  }
}

describe('UsersPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state when the users request fails', async () => {
    vi.mocked(adminApi.listAllUsers).mockRejectedValue(new Error('network down'))

    renderWithProviders(<UsersPage />, { route: '/admin/users' })

    expect(await screen.findByText('Failed to load users.')).toBeInTheDocument()
  })

  it('never offers "Patient" for a non-patient row, and only "Patient" for a patient row -- the backend always rejects any other role change into/out of patient', () => {
    const nonPatientOptions = roleOptionsFor('student')
    expect(nonPatientOptions.map((o) => o.value)).toEqual(['student', 'attending', 'admin'])

    const patientOptions = roleOptionsFor('patient')
    expect(patientOptions.map((o) => o.value)).toEqual(['patient'])
  })

  it('disables the role Select entirely for a patient row', async () => {
    vi.mocked(adminApi.listAllUsers).mockResolvedValue([
      fakeUser({ id: 'student-1', full_name: 'A Student', role: 'student' }),
      fakeUser({ id: 'patient-1', full_name: 'A Patient', role: 'patient' }),
    ])

    renderWithProviders(<UsersPage />, { route: '/admin/users' })
    await screen.findByText('A Student')

    const roleSelects = screen.getAllByRole('combobox')
    const patientSelect = roleSelects.find(
      (el) => (el as HTMLInputElement).value === 'Patient',
    ) as HTMLElement
    expect(patientSelect).toBeDisabled()
  })
})
