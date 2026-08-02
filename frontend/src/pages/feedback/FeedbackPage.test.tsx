import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as feedbackApi from '../../api/feedback'
import type { Feedback } from '../../api/types'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { FeedbackPage } from './FeedbackPage'

vi.mock('../../api/feedback')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

const FEEDBACK_ITEM: Feedback = {
  id: 'fb-1',
  appointment_id: 'appt-1',
  student_id: 'student-1',
  author_id: 'author-1',
  author_role: 'attending',
  went_well: 'Good chairside manner',
  could_improve: 'Faster setup',
  additional_comments: null,
  created_at: '2026-01-01T10:00:00Z',
  student_name: 'Stu Dent',
  author_name: 'Dr. Attending',
  patient_id: 'patient-1',
  patient_name: 'Pat Ient',
  appointment_start_time: '2026-01-01T09:00:00Z',
}

describe('FeedbackPage', () => {
  beforeEach(resetAuthTestState)

  it("shows an error state, not a blank page, when a student's received-feedback request fails", async () => {
    vi.mocked(feedbackApi.listFeedbackReceived).mockRejectedValue(new Error('network down'))

    renderWithProviders(<FeedbackPage />, { route: '/feedback' })

    expect(await screen.findByText('Failed to load feedback.')).toBeInTheDocument()
  })

  it('shows a student the feedback they received, grouped by patient', async () => {
    vi.mocked(feedbackApi.listFeedbackReceived).mockResolvedValue([FEEDBACK_ITEM])

    renderWithProviders(<FeedbackPage />, { route: '/feedback' })

    expect(await screen.findByText('Pat Ient')).toBeInTheDocument()
    expect(screen.getByText('Good chairside manner')).toBeInTheDocument()
    expect(screen.getByText('Faster setup')).toBeInTheDocument()
    // A student never sees the "give feedback" surfaces -- only their own
    // received feedback.
    expect(screen.queryByText('Pending feedback')).not.toBeInTheDocument()
  })
})
