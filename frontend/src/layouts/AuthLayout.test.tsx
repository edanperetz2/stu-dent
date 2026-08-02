import { MantineProvider } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { fakePrincipal } from '../test/authMocks'
import { useAuth } from '../auth/AuthContext'
import { AuthLayout } from './AuthLayout'

vi.mock('../auth/AuthContext', () => ({ useAuth: vi.fn() }))

function renderAuthLayout() {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<div>login form content</div>} />
          </Route>
          <Route path="/appointments" element={<div>appointments page</div>} />
        </Routes>
      </MemoryRouter>
    </MantineProvider>,
  )
}

describe('AuthLayout', () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReset()
  })

  it('shows the route fallback while the auth bootstrap check is still loading', () => {
    vi.mocked(useAuth).mockReturnValue({
      principal: null,
      isLoading: true,
      sessionExpired: false,
      clearSessionExpired: vi.fn(),
      handleSessionExpired: vi.fn(),
      login: vi.fn(),
      registerUser: vi.fn(),
      logout: vi.fn(),
    })

    const { container } = renderAuthLayout()
    expect(container.querySelector('.mantine-Loader-root')).toBeInTheDocument()
    expect(screen.queryByText('login form content')).not.toBeInTheDocument()
  })

  it('redirects an already-authenticated user away to /appointments', () => {
    vi.mocked(useAuth).mockReturnValue({
      principal: fakePrincipal('student'),
      isLoading: false,
      sessionExpired: false,
      clearSessionExpired: vi.fn(),
      handleSessionExpired: vi.fn(),
      login: vi.fn(),
      registerUser: vi.fn(),
      logout: vi.fn(),
    })

    renderAuthLayout()
    expect(screen.getByText('appointments page')).toBeInTheDocument()
    expect(screen.queryByText('login form content')).not.toBeInTheDocument()
  })

  it('renders the branded auth shell and the routed content for an unauthenticated visitor', () => {
    vi.mocked(useAuth).mockReturnValue({
      principal: null,
      isLoading: false,
      sessionExpired: false,
      clearSessionExpired: vi.fn(),
      handleSessionExpired: vi.fn(),
      login: vi.fn(),
      registerUser: vi.fn(),
      logout: vi.fn(),
    })

    renderAuthLayout()
    expect(screen.getByText('Stu-Dent')).toBeInTheDocument()
    expect(screen.getByText('login form content')).toBeInTheDocument()
  })
})
