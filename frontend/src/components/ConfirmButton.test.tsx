import { MantineProvider } from '@mantine/core'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmButton } from './ConfirmButton'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

describe('ConfirmButton', () => {
  it('opens a confirm modal instead of calling onConfirm immediately', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <MantineProvider>
        <ConfirmButton label="Delete" message="This will delete the thing." onConfirm={onConfirm} />
      </MantineProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('This will delete the thing.')).toBeInTheDocument()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('cancel closes the modal without calling onConfirm', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <MantineProvider>
        <ConfirmButton label="Delete" message="This will delete the thing." onConfirm={onConfirm} />
      </MantineProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    await screen.findByText('This will delete the thing.')
    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(onConfirm).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.queryByText('This will delete the thing.')).not.toBeInTheDocument())
  })

  it('waits for an async onConfirm to settle before closing the modal (the fix: loading must reflect the real request, not just the close transition)', async () => {
    const user = userEvent.setup()
    const { promise, resolve } = deferred<void>()
    const onConfirm = vi.fn(() => promise)
    render(
      <MantineProvider>
        <ConfirmButton label="Delete" message="This will delete the thing." onConfirm={onConfirm} />
      </MantineProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Delete' }))
    await screen.findByText('This will delete the thing.')
    await user.click(screen.getByRole('button', { name: 'Confirm' }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
    // Still open -- onConfirm's promise hasn't resolved yet, so the modal
    // must not have closed already (that was the pre-fix bug: close() ran
    // synchronously in the same handler that started the mutation).
    expect(screen.getByText('This will delete the thing.')).toBeInTheDocument()

    resolve()
    await waitFor(() => expect(screen.queryByText('This will delete the thing.')).not.toBeInTheDocument())
  })
})
