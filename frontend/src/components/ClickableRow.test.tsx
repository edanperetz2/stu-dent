import { MantineProvider, Table } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ComponentProps } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ClickableRow } from './ClickableRow'

function renderRow(props: Partial<ComponentProps<typeof ClickableRow>> = {}) {
  const onToggle = props.onToggle ?? vi.fn()
  return {
    onToggle,
    ...render(
      <MantineProvider>
        <Table>
          <Table.Tbody>
            <ClickableRow onToggle={onToggle} expanded={false} expandLabel="Expand row" {...props}>
              <Table.Td>Row content</Table.Td>
            </ClickableRow>
          </Table.Tbody>
        </Table>
      </MantineProvider>,
    ),
  }
}

describe('ClickableRow', () => {
  it('renders its children and calls onToggle when the row itself is clicked', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    renderRow({ onToggle })

    expect(screen.getByText('Row content')).toBeInTheDocument()
    await user.click(screen.getByText('Row content'))

    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('calls onToggle exactly once (not twice) when the trailing icon button is clicked', async () => {
    const user = userEvent.setup()
    const onToggle = vi.fn()
    renderRow({ onToggle })

    // The button's own cell stops propagation to the row's onClick -- a
    // click here must not double-fire onToggle (once from the button,
    // once from the row it's nested inside).
    await user.click(screen.getByRole('button', { name: 'Expand row' }))

    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('reflects the expanded state via aria-expanded', () => {
    renderRow({ expanded: true })
    expect(screen.getByRole('button', { name: 'Expand row' })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })
})
