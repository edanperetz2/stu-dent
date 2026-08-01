import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as authApi from '../../api/auth'
import { ApiError } from '../../api/httpClient'
import * as studentsApi from '../../api/students'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { RegisterPage } from './RegisterPage'

vi.mock('../../api/auth')
vi.mock('../../api/students')

describe('RegisterPage', () => {
  beforeEach(resetAuthTestState)

  it('registers then logs in with the same credentials', async () => {
    vi.mocked(authApi.registerUser).mockResolvedValue({
      id: 'u1',
      email: 'new@example.com',
      full_name: 'New Student',
      role: 'student',
      is_active: true,
      owner_student_id: null,
      owner_student_name: null,
      owner_confirmed_at: null,
      contact_phone: null,
      preferred_time_of_day: null,
    })
    vi.mocked(authApi.login).mockResolvedValue({ access_token: 'tok456', token_type: 'bearer' })
    vi.mocked(authApi.getCurrentUser).mockResolvedValue({
      id: 'u1',
      email: 'new@example.com',
      full_name: 'New Student',
      role: 'student',
      is_active: true,
      owner_student_id: null,
      owner_student_name: null,
      owner_confirmed_at: null,
      contact_phone: null,
      preferred_time_of_day: null,
    })

    renderWithProviders(<RegisterPage />, { route: '/register' })

    await userEvent.type(screen.getByLabelText('Full name'), 'New Student')
    await userEvent.type(screen.getByLabelText('Email'), 'new@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))

    await waitFor(() => {
      expect(authApi.registerUser).toHaveBeenCalledWith(
        'new@example.com',
        'password123',
        'New Student',
        'student',
        undefined,
      )
    })
    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith('new@example.com', 'password123', undefined)
    })
  })

  it('rejects a password shorter than 8 characters', async () => {
    renderWithProviders(<RegisterPage />, { route: '/register' })

    await userEvent.type(screen.getByLabelText('Full name'), 'New Student')
    await userEvent.type(screen.getByLabelText('Email'), 'new@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'short')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))

    expect(
      await screen.findByText('Password must be at least 8 characters'),
    ).toBeInTheDocument()
    expect(authApi.registerUser).not.toHaveBeenCalled()
  })

  it('registering as a patient shows a pending-confirmation message instead of logging in', async () => {
    vi.mocked(studentsApi.listStudents).mockResolvedValue([
      { id: 'stud-1', full_name: 'Dr. Mentor' },
    ])
    vi.mocked(authApi.registerUser).mockResolvedValue({
      id: 'p1',
      email: 'pat@example.com',
      full_name: 'New Patient',
      role: 'patient',
      is_active: true,
      owner_student_id: 'stud-1',
      owner_student_name: 'Dr. Mentor',
      owner_confirmed_at: null,
      contact_phone: null,
      preferred_time_of_day: null,
    })

    renderWithProviders(<RegisterPage />, { route: '/register' })

    await userEvent.type(screen.getByLabelText('Full name'), 'New Patient')
    await userEvent.type(screen.getByLabelText('Email'), 'pat@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    // Mantine's Select dropdown is positioned via Floating UI, which never
    // resolves to a visible `display` in jsdom -- the options are real and
    // clickable, just accessibility-hidden per RTL's default filtering, so
    // these queries opt in with `hidden: true`.
    await userEvent.click(screen.getByRole('combobox', { name: 'Role' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Patient', hidden: true }))

    const studentSelect = await screen.findByRole('combobox', { name: 'Choose your student' })
    await userEvent.click(studentSelect)
    await userEvent.click(await screen.findByRole('option', { name: 'Dr. Mentor', hidden: true }))

    await userEvent.click(screen.getByRole('button', { name: 'Register' }))

    await waitFor(() => {
      expect(authApi.registerUser).toHaveBeenCalledWith(
        'pat@example.com',
        'password123',
        'New Patient',
        'patient',
        'stud-1',
      )
    })
    expect(authApi.login).not.toHaveBeenCalled()
    expect(
      await screen.findByText(/Your student needs to confirm the connection/),
    ).toBeInTheDocument()
  })

  it('shows an error state, not "no students available", when the students request fails', async () => {
    vi.mocked(studentsApi.listStudents).mockRejectedValue(new Error('network down'))

    renderWithProviders(<RegisterPage />, { route: '/register' })

    await userEvent.click(screen.getByRole('combobox', { name: 'Role' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Patient', hidden: true }))

    expect(
      await screen.findByText('Failed to load the list of students.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('No students available yet')).not.toBeInTheDocument()
  })

  it('shows a real alert, not a plain red Text, when registration itself fails', async () => {
    vi.mocked(authApi.registerUser).mockRejectedValue(new ApiError(409, 'Email already registered'))

    renderWithProviders(<RegisterPage />, { route: '/register' })

    await userEvent.type(screen.getByLabelText('Full name'), 'New Student')
    await userEvent.type(screen.getByLabelText('Email'), 'taken@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'password123')
    await userEvent.click(screen.getByRole('button', { name: 'Register' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Email already registered')
  })
})
