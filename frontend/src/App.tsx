import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import '@mantine/dates/styles.css'

import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from './api/httpClient'
import { AuthProvider } from './auth/AuthContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import { RealtimeProvider } from './realtime/RealtimeContext'
import { AppRouter } from './router/AppRouter'
import { theme } from './theme'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // A 401 means the token is expired/invalid -- AuthContext's
      // unauthorized handler (see httpClient.ts) already logs the user out
      // on the first attempt, so retrying just makes them wait through 2
      // more identical failures before the "session expired" message even
      // has a chance to appear.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status === 401) && failureCount < 3,
    },
  },
})

function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="auto">
      {/* Every mutation's success/error toast (52+ call sites) already
          carries a real status message ("Patient created", "Failed to
          cancel entry", ...) -- making the container itself a live region
          is what gets those actually announced to screen readers, instead
          of adding a second, separate announcement mechanism that would
          have to be threaded through every one of those call sites. */}
      <Notifications aria-live="polite" role="status" />
      <ErrorBoundary>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RealtimeProvider>
              <AppRouter />
            </RealtimeProvider>
          </AuthProvider>
        </QueryClientProvider>
      </ErrorBoundary>
    </MantineProvider>
  )
}

export default App
