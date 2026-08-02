import { MantineProvider } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ErrorBoundary } from './ErrorBoundary'

function Bomb(): never {
  throw new Error('boom')
}

describe('ErrorBoundary', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // React logs the caught error to console.error itself (in addition to
    // this component's own componentDidCatch log) -- expected noise for
    // this specific test, not a real assertion failure.
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('renders its children normally when nothing throws', () => {
    render(
      <MantineProvider>
        <ErrorBoundary>
          <div>real content</div>
        </ErrorBoundary>
      </MantineProvider>,
    )
    expect(screen.getByText('real content')).toBeInTheDocument()
  })

  it('renders a fallback UI instead of a blank screen when a child throws', () => {
    render(
      <MantineProvider>
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>
      </MantineProvider>,
    )

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
    expect(screen.queryByText('real content')).not.toBeInTheDocument()
  })
})
