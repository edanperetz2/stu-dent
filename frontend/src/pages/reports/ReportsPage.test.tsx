import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Report } from '../../api/types'
import * as reportsApi from '../../api/reports'
import { authContextMock, fakePrincipal } from '../../test/authMocks'
import { renderWithProviders } from '../../test/renderWithProviders'
import { resetAuthTestState } from '../../test/resetAuthTestState'
import { ReportsPage } from './ReportsPage'

vi.mock('../../api/reports')
vi.mock('../../auth/AuthContext', () => authContextMock(fakePrincipal('student')))

const WEEKLY_REPORT: Report = {
  id: 'report-1',
  period_type: 'weekly',
  period_start: '2026-01-05T00:00:00Z',
  period_end: '2026-01-12T00:00:00Z',
  question: null,
  title: 'Weekly report (2026-01-05 - 2026-01-12)',
  content: 'Everything looks fine this week.',
  content_source: 'ai',
  created_at: '2026-01-12T08:00:00Z',
}

describe('ReportsPage', () => {
  beforeEach(resetAuthTestState)

  it('shows an error state, not the empty state, when the reports request fails', async () => {
    vi.mocked(reportsApi.listReports).mockRejectedValue(new Error('network down'))

    renderWithProviders(<ReportsPage />, { route: '/reports' })

    expect(await screen.findByText('Failed to load reports.')).toBeInTheDocument()
    expect(screen.queryByText('No reports yet.')).not.toBeInTheDocument()
  })

  it('renders a report with its content, source badge, and period range', async () => {
    vi.mocked(reportsApi.listReports).mockResolvedValue([WEEKLY_REPORT])

    renderWithProviders(<ReportsPage />, { route: '/reports' })

    expect(await screen.findByText('Everything looks fine this week.')).toBeInTheDocument()
    expect(screen.getByText('AI-narrated')).toBeInTheDocument()
    expect(screen.getByText('Weekly')).toBeInTheDocument()
    // The period range is now always shown, even when a report's content
    // is a non-answer (e.g. unresolved_date_range) -- proves that fix
    // actually renders, not just that the type accepts the field.
    expect(screen.getByText(/Period:/)).toBeInTheDocument()
  })

  it('shows the unresolved-date-range badge distinctly from a real answer', async () => {
    vi.mocked(reportsApi.listReports).mockResolvedValue([
      {
        ...WEEKLY_REPORT,
        id: 'report-2',
        period_type: 'ad_hoc',
        question: 'what happened yesterday?',
        title: 'what happened yesterday?',
        content: 'Couldn\'t understand the date range "yesterday" -- try a phrase like...',
        content_source: 'unresolved_date_range',
      },
    ])

    renderWithProviders(<ReportsPage />, { route: '/reports' })

    expect(await screen.findByText('Date range not understood')).toBeInTheDocument()
  })
})
