import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as roomsApi from '../../api/rooms'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { RoomsPage } from './RoomsPage'

vi.mock('../../api/rooms')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('admin')))

describe('RoomsPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state when the rooms request fails', async () => {
    vi.mocked(roomsApi.listAllRooms).mockRejectedValue(new Error('network down'))

    renderWithProviders(<RoomsPage />, { route: '/admin/rooms' })

    expect(await screen.findByText('Failed to load rooms.')).toBeInTheDocument()
  })
})
