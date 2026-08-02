import { MantineProvider } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EmptyText, ErrorText } from './StateText'

describe('EmptyText', () => {
  it('renders its children', () => {
    render(
      <MantineProvider>
        <EmptyText>No notifications.</EmptyText>
      </MantineProvider>,
    )
    expect(screen.getByText('No notifications.')).toBeInTheDocument()
  })
})

describe('ErrorText', () => {
  it('renders the message without a retry button when onRetry is omitted', () => {
    render(
      <MantineProvider>
        <ErrorText>Failed to load.</ErrorText>
      </MantineProvider>,
    )
    expect(screen.getByText('Failed to load.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('renders a working retry button when onRetry is given', async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(
      <MantineProvider>
        <ErrorText onRetry={onRetry}>Failed to load.</ErrorText>
      </MantineProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
