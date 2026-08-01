import { Alert, Anchor, Button, PasswordInput, Stack, Text, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useState } from 'react'
import { Link, useLocation, useNavigate, type Location } from 'react-router-dom'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuth } from '../../auth/AuthContext'

interface LoginFormValues {
  email: string
  password: string
}

export function LoginPage() {
  const { login, sessionExpired } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const from = (location.state as { from?: Location } | null)?.from

  const form = useForm<LoginFormValues>({
    initialValues: { email: '', password: '' },
    validate: {
      email: (value) => (value.includes('@') ? null : 'Enter a valid email'),
      password: (value) => (value.length > 0 ? null : 'Password is required'),
    },
  })

  async function handleSubmit(values: LoginFormValues) {
    setError(null)
    setSubmitting(true)
    try {
      // No role picker -- the backend already validates the account's real
      // role server-side, so a frontend guess could only ever turn a valid
      // login into a spurious failure, never let someone log in under the
      // wrong role.
      await login(values.email, values.password)
      navigate(from ? `${from.pathname}${from.search}` : '/appointments', { replace: true })
    } catch (err) {
      setError(apiErrorMessage(err, 'Login failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        {sessionExpired && (
          <Alert color="yellow" role="alert">
            Your session expired. Log in again to continue where you left off.
          </Alert>
        )}
        <TextInput
          label="Email"
          placeholder="you@example.com"
          autoComplete="email"
          type="email"
          {...form.getInputProps('email')}
        />
        <PasswordInput
          label="Password"
          autoComplete="current-password"
          {...form.getInputProps('password')}
        />
        <Text size="sm" ta="right">
          <Anchor component={Link} to="/forgot-password">
            Forgot password?
          </Anchor>
        </Text>
        {error && (
          <Alert color="red" role="alert">
            {error}
          </Alert>
        )}
        <Button type="submit" loading={submitting} fullWidth>
          Log in
        </Button>
        <Text size="sm" ta="center">
          Don&apos;t have an account? <Anchor component={Link} to="/register">Register</Anchor>
        </Text>
      </Stack>
    </form>
  )
}
