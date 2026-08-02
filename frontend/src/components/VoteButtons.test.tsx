import { MantineProvider } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { VoteButtons } from './VoteButtons'

describe('VoteButtons', () => {
  it('renders the like/dislike counts and reflects the current vote via aria-pressed', () => {
    render(
      <MantineProvider>
        <VoteButtons likes={3} dislikes={1} myVote={1} onVote={vi.fn()} onRemoveVote={vi.fn()} />
      </MantineProvider>,
    )
    expect(screen.getByRole('button', { name: 'Like' })).toHaveTextContent('3')
    expect(screen.getByRole('button', { name: 'Dislike' })).toHaveTextContent('1')
    expect(screen.getByRole('button', { name: 'Like' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Dislike' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('calls onVote when clicking a direction that is not the current vote', async () => {
    const user = userEvent.setup()
    const onVote = vi.fn()
    const onRemoveVote = vi.fn()
    render(
      <MantineProvider>
        <VoteButtons
          likes={0}
          dislikes={0}
          myVote={null}
          onVote={onVote}
          onRemoveVote={onRemoveVote}
        />
      </MantineProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Like' }))
    expect(onVote).toHaveBeenCalledWith(1)
    expect(onRemoveVote).not.toHaveBeenCalled()
  })

  it('calls onRemoveVote (toggle off), not onVote, when clicking the already-active direction', async () => {
    const user = userEvent.setup()
    const onVote = vi.fn()
    const onRemoveVote = vi.fn()
    render(
      <MantineProvider>
        <VoteButtons likes={1} dislikes={0} myVote={1} onVote={onVote} onRemoveVote={onRemoveVote} />
      </MantineProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Like' }))
    expect(onRemoveVote).toHaveBeenCalledTimes(1)
    expect(onVote).not.toHaveBeenCalled()
  })

  it("stops the click from bubbling to a parent row's own onClick", async () => {
    const user = userEvent.setup()
    const onRowClick = vi.fn()
    render(
      <MantineProvider>
        {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
        <div onClick={onRowClick}>
          <VoteButtons likes={0} dislikes={0} myVote={null} onVote={vi.fn()} onRemoveVote={vi.fn()} />
        </div>
      </MantineProvider>,
    )

    await user.click(screen.getByRole('button', { name: 'Like' }))
    expect(onRowClick).not.toHaveBeenCalled()
  })
})
