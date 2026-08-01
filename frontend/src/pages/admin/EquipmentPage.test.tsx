import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as equipmentApi from '../../api/equipment'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { EquipmentPage } from './EquipmentPage'

vi.mock('../../api/equipment')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('admin')))

describe('EquipmentPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state when the equipment request fails', async () => {
    vi.mocked(equipmentApi.listAllEquipment).mockRejectedValue(new Error('network down'))

    renderWithProviders(<EquipmentPage />, { route: '/admin/equipment' })

    expect(await screen.findByText('Failed to load equipment.')).toBeInTheDocument()
  })
})
