import { Button, MantineProvider } from '@mantine/core'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PageHeader } from './PageHeader'

describe('PageHeader', () => {
  it('renders the title', () => {
    render(
      <MantineProvider>
        <PageHeader title="Appointments" />
      </MantineProvider>,
    )
    expect(screen.getByRole('heading', { name: 'Appointments' })).toBeInTheDocument()
  })

  it('renders the actions slot when given', () => {
    render(
      <MantineProvider>
        <PageHeader title="Appointments" actions={<Button>New</Button>} />
      </MantineProvider>,
    )
    expect(screen.getByRole('button', { name: 'New' })).toBeInTheDocument()
  })
})
