import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as patientsApi from '../../api/patients'
import type { User } from '../../api/types'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { PatientDetailPanel } from './PatientDetailPanel'

vi.mock('../../api/patients')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

const UNCONFIRMED_PATIENT: User = {
  id: 'patient-1',
  email: 'pat@example.com',
  full_name: 'Pat Ient',
  role: 'patient',
  is_active: true,
  owner_student_id: 'student-1',
  owner_student_name: null,
  owner_confirmed_at: null,
  contact_phone: null,
  preferred_time_of_day: null,
}

describe('PatientDetailPanel', () => {
  beforeEach(resetAuthTestState)

  it('shows a pending patient as unconfirmed and confirms them on click', async () => {
    const user = userEvent.setup()
    vi.mocked(patientsApi.confirmPatient).mockResolvedValue({
      ...UNCONFIRMED_PATIENT,
      owner_confirmed_at: '2026-01-01T00:00:00Z',
    })

    renderWithProviders(<PatientDetailPanel patient={UNCONFIRMED_PATIENT} />)

    expect(screen.getByText('Pending confirmation')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Confirm' }))

    await waitFor(() =>
      expect(patientsApi.confirmPatient).toHaveBeenCalledWith('test-token', 'patient-1'),
    )
  })

  it('submits edited fields via updatePatient', async () => {
    const user = userEvent.setup()
    vi.mocked(patientsApi.updatePatient).mockResolvedValue(UNCONFIRMED_PATIENT)

    renderWithProviders(<PatientDetailPanel patient={UNCONFIRMED_PATIENT} />)

    const nameInput = screen.getByLabelText('Full name')
    await user.clear(nameInput)
    await user.type(nameInput, 'Patricia Ient')
    await user.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(patientsApi.updatePatient).toHaveBeenCalledWith(
        'test-token',
        'patient-1',
        expect.objectContaining({ full_name: 'Patricia Ient' }),
      ),
    )
  })
})
