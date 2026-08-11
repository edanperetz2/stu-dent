import { MantineProvider } from '@mantine/core'
import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SocialAuthButtons } from './SocialAuthButtons'

describe('SocialAuthButtons', () => {
  beforeEach(() => vi.useFakeTimers())

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  it('shows a stable loading state before leaving for Google', () => {
    const { unmount } = render(
      <MantineProvider>
        <SocialAuthButtons flow="login" />
      </MantineProvider>,
    )

    const button = screen.getByRole('link', { name: 'Sign in with Google' })
    expect(new URL(button.getAttribute('href')!).searchParams.get('color_scheme')).toBe('light')
    expect(button).not.toHaveAttribute('target')
    fireEvent.click(button)

    expect(screen.getByRole('link', { name: 'Opening Google sign-in' })).toBeInTheDocument()
    expect(screen.getByText('Opening Google…')).toBeInTheDocument()
    unmount()
  })
})
