import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import '@mantine/dates/styles.css'

import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './auth/AuthContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import { RealtimeProvider } from './realtime/RealtimeContext'
import { AppRouter } from './router/AppRouter'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

function App() {
  return (
    <MantineProvider>
      <Notifications />
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
