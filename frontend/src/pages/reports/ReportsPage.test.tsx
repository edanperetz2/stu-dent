import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
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

function ReportsNavigationHarness() {
  const [showReports, setShowReports] = useState(true)

  return (
    <>
      <button type="button" onClick={() => setShowReports((current) => !current)}>
        {showReports ? 'Leave reports' : 'Return to reports'}
      </button>
      {showReports ? <ReportsPage /> : <div>Another page</div>}
    </>
  )
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
    expect(screen.getByText('Weekly', { selector: '.mantine-Badge-label' })).toBeInTheDocument()
    // The period range is now always shown, even when a report's content
    // is a non-answer (e.g. unresolved_date_range) -- proves that fix
    // actually renders, not just that the type accepts the field.
    expect(screen.getByText(/Period:/)).toBeInTheDocument()
  })

  it('generates the selected period and report format', async () => {
    vi.mocked(reportsApi.listReports).mockResolvedValue([])
    vi.mocked(reportsApi.generateReport).mockResolvedValue(WEEKLY_REPORT)

    renderWithProviders(<ReportsPage />, { route: '/reports' })

    await userEvent.click(screen.getByRole('combobox', { name: 'Report period' }))
    await userEvent.click(await screen.findByRole('option', { name: 'Monthly', hidden: true }))
    await userEvent.click(screen.getByRole('combobox', { name: 'Report format' }))
    await userEvent.click(
      await screen.findByRole('option', { name: 'Data summary', hidden: true }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Generate report' }))

    await waitFor(() => {
      expect(reportsApi.generateReport).toHaveBeenCalledWith(expect.any(String), {
        period_type: 'monthly',
        output_style: 'data_summary',
      })
    })
  })

  it('keeps the generation spinner active after leaving and returning', async () => {
    let finishGeneration: (report: Report) => void = () => undefined
    const pendingGeneration = new Promise<Report>((resolve) => {
      finishGeneration = resolve
    })
    vi.mocked(reportsApi.listReports).mockResolvedValue([])
    vi.mocked(reportsApi.generateReport).mockReturnValue(pendingGeneration)

    renderWithProviders(<ReportsNavigationHarness />, { route: '/reports' })

    await userEvent.click(screen.getByRole('button', { name: 'Generate report' }))
    expect(screen.getByRole('button', { name: 'Generate report' })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: 'Leave reports' }))
    expect(screen.queryByRole('button', { name: 'Generate report' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Return to reports' }))

    expect(screen.getByRole('button', { name: 'Generate report' })).toBeDisabled()

    finishGeneration(WEEKLY_REPORT)
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Generate report' })).toBeEnabled()
    })
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
