import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('redirects unauthenticated users to the login page', async () => {
    render(<App />)
    expect(await screen.findByText('Login')).toBeInTheDocument()
  })
})
