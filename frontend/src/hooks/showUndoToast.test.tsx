import { MantineProvider } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { showUndoToast } from './showUndoToast'

vi.mock('@mantine/notifications', () => ({
  notifications: { show: vi.fn(), hide: vi.fn() },
}))

describe('showUndoToast', () => {
  beforeEach(() => {
    vi.mocked(notifications.show).mockClear()
    vi.mocked(notifications.hide).mockClear()
  })

  // notifications.show's `message` is JSX in this hook, not a plain string
  // -- render it directly (inside a real MantineProvider, same as a real
  // Mantine <Notifications /> host would provide) to interact with the
  // actual Undo button.
  function renderLastShownMessage() {
    const call = vi.mocked(notifications.show).mock.calls.at(-1)?.[0]
    render(<MantineProvider>{call?.message}</MantineProvider>)
    return call
  }

  it('shows the given message with an Undo button', () => {
    showUndoToast({ message: 'Entry cancelled.', onUndo: vi.fn() })
    renderLastShownMessage()
    expect(screen.getByText('Entry cancelled.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Undo' })).toBeInTheDocument()
  })

  it('supports a custom undoLabel', () => {
    showUndoToast({ message: 'Deactivated.', onUndo: vi.fn(), undoLabel: 'Restore' })
    renderLastShownMessage()
    expect(screen.getByRole('button', { name: 'Restore' })).toBeInTheDocument()
  })

  it('calls onUndo and hides the toast when Undo is clicked', async () => {
    const user = userEvent.setup()
    const onUndo = vi.fn()
    showUndoToast({ message: 'Entry cancelled.', onUndo })
    const call = renderLastShownMessage()

    await user.click(screen.getByRole('button', { name: 'Undo' }))

    expect(onUndo).toHaveBeenCalledTimes(1)
    expect(notifications.hide).toHaveBeenCalledWith(call?.id)
  })

  it('shows an error notification instead of an unhandled rejection when onUndo rejects', async () => {
    const user = userEvent.setup()
    const onUndo = vi.fn().mockRejectedValue(new Error('undo failed'))
    showUndoToast({ message: 'Entry cancelled.', onUndo })
    renderLastShownMessage()

    await user.click(screen.getByRole('button', { name: 'Undo' }))

    await waitFor(() =>
      expect(notifications.show).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Undo failed', color: 'red' }),
      ),
    )
  })
})
