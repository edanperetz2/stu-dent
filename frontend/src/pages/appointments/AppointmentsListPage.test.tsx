import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as appointmentsApi from '../../api/appointments'
import * as equipmentApi from '../../api/equipment'
import * as roomsApi from '../../api/rooms'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { AppointmentsListPage } from './AppointmentsListPage'

vi.mock('../../api/appointments')
vi.mock('../../api/rooms')
vi.mock('../../api/equipment')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('attending')))

describe('AppointmentsListPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not the empty state, when the appointments request fails', async () => {
    vi.mocked(roomsApi.listActiveRooms).mockResolvedValue([])
    vi.mocked(equipmentApi.listActiveEquipment).mockResolvedValue([])
    vi.mocked(appointmentsApi.listAppointments).mockRejectedValue(new Error('network down'))

    renderWithProviders(<AppointmentsListPage />, { route: '/appointments' })

    expect(await screen.findByText('Failed to load appointments.')).toBeInTheDocument()
    expect(screen.queryByText(/No appointments yet/)).not.toBeInTheDocument()
  })
})
