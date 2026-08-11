import { Alert, Button, Stack } from '@mantine/core'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuth } from '../../auth/AuthContext'
import { GOOGLE_MINIMUM_SIGN_IN_MS } from '../../auth/signInTransition'
import { SigningInPanel } from '../../components/SigningInPanel'
import { preloadOAuthDestination } from '../../router/preloadOAuthDestination'

export function OAuthCallbackPage() {
  const { completeOAuth, isLoading } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(searchParams.get('error'))
  const started = useRef(false)

  useEffect(() => {
    if (isLoading || started.current) return
    started.current = true

    const fragment = new URLSearchParams(window.location.hash.slice(1))
    const token = fragment.get('token')
    const requestedNext = fragment.get('next') ?? '/appointments'
    const next =
      requestedNext.startsWith('/') && !requestedNext.startsWith('//')
        ? requestedNext
        : '/appointments'

    // Clear the token before making any request or rendering another route.
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)

    if (!token) {
      if (!searchParams.get('error')) setError('The sign-in response did not include a session.')
      return
    }

    // Fetch the destination chunk alongside the current-user request. The
    // callback screen remains mounted throughout both operations, avoiding
    // the auth-layout redirect and router fallback flashes that previously
    // appeared between Google and the application.
    const handoffStartedAt = window.performance.now()
    void (async () => {
      try {
        await Promise.all([
          completeOAuth(token, handoffStartedAt, GOOGLE_MINIMUM_SIGN_IN_MS),
          preloadOAuthDestination(next).catch(() => undefined),
        ])
        navigate(next, { replace: true })
      } catch (err: unknown) {
        setError(apiErrorMessage(err, 'Could not complete sign-in.'))
      }
    })()
  }, [completeOAuth, isLoading, navigate, searchParams])

  return (
    <Stack align="stretch" gap="md">
      {error ? (
        <>
          <Alert color="red" role="alert">
            {error}
          </Alert>
          <Button component={Link} to="/login" variant="light" fullWidth>
            Back to sign in
          </Button>
        </>
      ) : (
        <SigningInPanel />
      )}
    </Stack>
  )
}
