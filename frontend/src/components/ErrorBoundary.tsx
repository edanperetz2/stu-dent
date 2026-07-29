import { Button, Stack, Text, Title } from '@mantine/core'
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

/** Top-level safety net -- React error boundaries have no hook
 * equivalent, so this has to be a class component. Without this, any
 * uncaught render/effect error anywhere in the app (e.g. AuthContext's
 * bootstrap effect hitting malformed localStorage JSON) was a permanent
 * white screen with no way back to even /login. */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled error caught by ErrorBoundary:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <Stack align="center" justify="center" h="100vh" gap="sm">
          <Title order={3}>Something went wrong</Title>
          <Text c="dimmed">
            An unexpected error occurred. Reloading the page usually fixes this.
          </Text>
          <Button onClick={() => window.location.reload()}>Reload</Button>
        </Stack>
      )
    }
    return this.props.children
  }
}
