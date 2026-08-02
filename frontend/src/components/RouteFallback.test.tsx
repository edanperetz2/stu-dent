import { MantineProvider } from '@mantine/core'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RouteFallback } from './RouteFallback'

describe('RouteFallback', () => {
  it('renders a loading indicator', () => {
    const { container } = render(
      <MantineProvider>
        <RouteFallback />
      </MantineProvider>,
    )
    expect(container.querySelector('.mantine-Loader-root')).toBeInTheDocument()
  })
})
