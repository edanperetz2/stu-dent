import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { PreferencesPage } from './PreferencesPage'

vi.mock('../../api/auth')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

describe('PreferencesPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not the loading state forever, when the profile request fails', async () => {
    vi.mocked(authApi.getCurrentUser).mockRejectedValue(new Error('network down'))

    renderWithProviders(<PreferencesPage />, { route: '/preferences' })

    expect(await screen.findByText('Failed to load your preferences.')).toBeInTheDocument()
  })
})
