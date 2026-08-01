import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as patientsApi from '../../api/patients'
import type { User } from '../../api/types'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { PatientsListPage } from './PatientsListPage'

vi.mock('../../api/patients')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

const PATIENT: User = {
  id: 'patient-1',
  email: 'patient@example.com',
  full_name: 'Jane Patient',
  role: 'patient',
  is_active: true,
  owner_student_id: 'student-1',
  owner_student_name: null,
  owner_confirmed_at: '2026-01-01T00:00:00Z',
  contact_phone: null,
  preferred_time_of_day: null,
}

describe('PatientsListPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not the empty state, when the patients request fails', async () => {
    vi.mocked(patientsApi.listPatients).mockRejectedValue(new Error('network down'))

    renderWithProviders(<PatientsListPage />, { route: '/patients' })

    expect(await screen.findByText('Failed to load patients.')).toBeInTheDocument()
    expect(screen.queryByText(/No patients yet/)).not.toBeInTheDocument()
  })

  it('expands a row via a real focusable control, without overriding the row role', async () => {
    vi.mocked(patientsApi.listPatients).mockResolvedValue([PATIENT])

    renderWithProviders(<PatientsListPage />, { route: '/patients' })

    const row = await screen.findByText('Jane Patient')
    const tableRow = row.closest('tr')
    // The table row keeps its implicit `row` semantics -- no `role="button"`
    // hack overriding it.
    expect(tableRow).not.toHaveAttribute('role')

    const expandButton = screen.getByRole('button', {
      name: 'Toggle details for Jane Patient',
    })
    await userEvent.click(expandButton)

    expect(expandButton).toHaveAttribute('aria-expanded', 'true')
  })
})
