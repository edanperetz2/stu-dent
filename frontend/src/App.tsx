import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import '@mantine/dates/styles.css'
import 'react-big-calendar/lib/css/react-big-calendar.css'

import { MantineProvider } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './auth/AuthContext'
import { RealtimeProvider } from './realtime/RealtimeContext'
import { AppRouter } from './router/AppRouter'

const queryClient = new QueryClient()

function App() {
  return (
    <MantineProvider>
      <Notifications />
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <RealtimeProvider>
            <AppRouter />
          </RealtimeProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MantineProvider>
  )
}

export default App
