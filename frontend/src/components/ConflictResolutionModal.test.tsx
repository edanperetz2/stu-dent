import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/renderWithProviders'
import { ConflictResolutionModal } from './ConflictResolutionModal'

const CONFLICTS = [
  { resource_type: 'room' as const, resource_id: 'r1', resource_name: 'Operatory 1' },
]

describe('ConflictResolutionModal', () => {
  it('offers a plain "Join waitlist" action and no cancel warning for a fresh create', () => {
    renderWithProviders(
      <ConflictResolutionModal
        opened
        onClose={() => {}}
        conflicts={CONFLICTS}
        onJoinWaitlist={() => {}}
      />,
    )

    expect(screen.getByText('Room Operatory 1 is already booked at this time.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Join waitlist' })).toBeInTheDocument()
    expect(screen.queryByText(/will cancel this appointment now/i)).not.toBeInTheDocument()
  })

  it('warns about cancelling the existing appointment and labels the button accordingly', () => {
    renderWithProviders(
      <ConflictResolutionModal
        opened
        onClose={() => {}}
        conflicts={CONFLICTS}
        onJoinWaitlist={() => {}}
        cancelsExistingAppointment
      />,
    )

    expect(screen.getByText(/will cancel this appointment now/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel & join waitlist' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Join waitlist' })).not.toBeInTheDocument()
  })

  it('calls onJoinWaitlist when the join button is clicked', async () => {
    const onJoinWaitlist = vi.fn()
    renderWithProviders(
      <ConflictResolutionModal
        opened
        onClose={() => {}}
        conflicts={CONFLICTS}
        onJoinWaitlist={onJoinWaitlist}
      />,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Join waitlist' }))
    expect(onJoinWaitlist).toHaveBeenCalledOnce()
  })
})
