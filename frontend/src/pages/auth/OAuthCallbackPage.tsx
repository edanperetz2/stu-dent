import { Alert, Loader, Stack, Text } from '@mantine/core'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuth } from '../../auth/AuthContext'

export function OAuthCallbackPage() {
  const { completeOAuth } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(searchParams.get('error'))

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1))
    const token = fragment.get('token')
    const next = fragment.get('next') ?? '/appointments'

    // Clear the token before making any request or rendering another route.
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
    if (!token) {
      if (!searchParams.get('error')) setError('The sign-in response did not include a session.')
      return
    }

    void completeOAuth(token)
      .then(() => navigate(next.startsWith('/') && !next.startsWith('//') ? next : '/appointments', { replace: true }))
      .catch((err: unknown) => setError(apiErrorMessage(err, 'Could not complete sign-in.')))
  }, [completeOAuth, navigate, searchParams])

  return (
    <Stack align="center">
      {error ? (
        <Alert color="red" role="alert">
          {error}
        </Alert>
      ) : (
        <>
          <Loader aria-label="Completing sign-in" />
          <Text size="sm">Completing sign-in…</Text>
        </>
      )}
    </Stack>
  )
}
