import { MantineProvider } from '@mantine/core'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { describe, expect, it } from 'vitest'
import { CardListSkeleton, ChatSkeleton, FormSkeleton, ListRowsSkeleton, TableSkeleton } from './Skeletons'

function withProvider(ui: ReactElement) {
  return render(<MantineProvider>{ui}</MantineProvider>)
}

describe('Skeletons', () => {
  it('TableSkeleton renders the requested row/column grid', () => {
    const { container } = withProvider(<TableSkeleton columns={3} rows={4} />)
    expect(container.querySelectorAll('tr')).toHaveLength(4)
    expect(container.querySelectorAll('tr:first-child td')).toHaveLength(3)
  })

  it('CardListSkeleton renders the requested card count', () => {
    const { container } = withProvider(<CardListSkeleton count={5} />)
    expect(container.querySelectorAll('.mantine-Paper-root')).toHaveLength(5)
  })

  it('ListRowsSkeleton renders the requested row count', () => {
    const { container } = withProvider(<ListRowsSkeleton count={7} />)
    expect(container.querySelectorAll('.mantine-Skeleton-root')).toHaveLength(7)
  })

  it('ChatSkeleton renders the requested bubble count', () => {
    const { container } = withProvider(<ChatSkeleton count={3} />)
    expect(container.querySelectorAll('.mantine-Skeleton-root')).toHaveLength(3)
  })

  it('FormSkeleton renders one bar per field plus a submit-button bar', () => {
    const { container } = withProvider(<FormSkeleton fields={3} />)
    expect(container.querySelectorAll('.mantine-Skeleton-root')).toHaveLength(4)
  })
})
