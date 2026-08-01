import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as adminApi from '../../api/admin'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { UsersPage } from './UsersPage'

vi.mock('../../api/admin')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('admin')))

describe('UsersPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state when the users request fails', async () => {
    vi.mocked(adminApi.listAllUsers).mockRejectedValue(new Error('network down'))

    renderWithProviders(<UsersPage />, { route: '/admin/users' })

    expect(await screen.findByText('Failed to load users.')).toBeInTheDocument()
  })
})
