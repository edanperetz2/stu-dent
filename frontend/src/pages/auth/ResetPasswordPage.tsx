import { Alert, Anchor, Button, PasswordInput, Stack, Text } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { confirmPasswordReset } from '../../api/auth'
import { apiErrorMessage } from '../../api/httpClient'
import { useMutationWithToast } from '../../hooks/useMutationWithToast'

interface ResetPasswordFormValues {
  newPassword: string
}

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [error, setError] = useState<string | null>(null)
  const [succeeded, setSucceeded] = useState(false)

  const form = useForm<ResetPasswordFormValues>({
    initialValues: { newPassword: '' },
    validate: {
      newPassword: (value) =>
        value.length >= 8 ? null : 'Password must be at least 8 characters',
    },
  })

  const confirmMutation = useMutationWithToast({
    mutationFn: (newPassword: string) => confirmPasswordReset(token ?? '', newPassword),
    invalidateKeys: [],
    errorFallback: 'Failed to reset your password',
    onSuccess: () => setSucceeded(true),
    onError: (err) => {
      // Shown inline (below), not as a toast -- an invalid/expired-link
      // failure needs a next step (request a new link), not a message
      // that can disappear before the user acts on it.
      setError(apiErrorMessage(err, 'Failed to reset your password'))
      return true
    },
  })

  if (!token) {
    return (
      <Stack>
        <Alert color="red" role="alert">
          This reset link is missing its token. Request a new one.
        </Alert>
        <Anchor component={Link} to="/forgot-password" ta="center">
          Request a new link
        </Anchor>
      </Stack>
    )
  }

  if (succeeded) {
    return (
      <Stack>
        <Text ta="center">Your password has been reset.</Text>
        <Anchor component={Link} to="/login" ta="center">
          Go to login
        </Anchor>
      </Stack>
    )
  }

  return (
    <form
      onSubmit={form.onSubmit((values) => {
        setError(null)
        confirmMutation.mutate(values.newPassword)
      })}
    >
      <Stack>
        <PasswordInput
          label="New password"
          autoComplete="new-password"
          {...form.getInputProps('newPassword')}
        />
        {error && (
          <Alert color="red" role="alert">
            {error}
          </Alert>
        )}
        <Button type="submit" loading={confirmMutation.isPending} fullWidth>
          Reset password
        </Button>
      </Stack>
    </form>
  )
}
