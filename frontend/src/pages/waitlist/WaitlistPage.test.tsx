import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { WaitlistEntry } from '../../api/types'
import * as waitlistApi from '../../api/waitlist'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { WaitlistPage } from './WaitlistPage'

vi.mock('../../api/waitlist')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

const ACTIVE_ENTRY: WaitlistEntry = {
  id: 'wl-1',
  student_id: 'test-user-id',
  patient_id: 'patient-1',
  attending_id: null,
  room_id: 'room-1',
  equipment_id: null,
  start_time: '2026-06-01T09:00:00Z',
  end_time: '2026-06-01T10:00:00Z',
  notes: null,
  status: 'active',
  resolved_at: null,
  resulting_appointment_id: null,
  resulting_appointment_status: null,
  conflicts: [{ resource_type: 'room', resource_id: 'room-1', resource_name: 'Room 1' }],
  student_name: 'Test User',
  patient_name: 'Pat Ient',
  attending_name: null,
  room_name: 'Room 1',
  equipment_name: null,
}

describe('WaitlistPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not the empty state, when the waitlist request fails', async () => {
    vi.mocked(waitlistApi.listWaitlistEntries).mockRejectedValue(new Error('network down'))

    renderWithProviders(<WaitlistPage />, { route: '/waitlist' })

    expect(await screen.findByText('Failed to load the waitlist.')).toBeInTheDocument()
    expect(screen.queryByText('Nothing on the waitlist.')).not.toBeInTheDocument()
  })

  it('lets the owning student cancel an active entry', async () => {
    const user = userEvent.setup()
    vi.mocked(waitlistApi.listWaitlistEntries).mockResolvedValue([ACTIVE_ENTRY])
    vi.mocked(waitlistApi.cancelWaitlistEntry).mockResolvedValue({
      ...ACTIVE_ENTRY,
      status: 'cancelled',
    })

    renderWithProviders(<WaitlistPage />, { route: '/waitlist' })

    expect(await screen.findByText('Room busy')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    await waitFor(() =>
      expect(waitlistApi.cancelWaitlistEntry).toHaveBeenCalledWith('test-token', 'wl-1'),
    )
  })
})
