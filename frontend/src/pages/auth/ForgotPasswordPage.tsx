import { Anchor, Button, Stack, Text, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { requestPasswordReset } from '../../api/auth'
import { useMutationWithToast } from '../../hooks/useMutationWithToast'

interface ForgotPasswordFormValues {
  email: string
}

export function ForgotPasswordPage() {
  const [submitted, setSubmitted] = useState(false)

  const form = useForm<ForgotPasswordFormValues>({
    initialValues: { email: '' },
    validate: {
      email: (value) => (value.includes('@') ? null : 'Enter a valid email'),
    },
  })

  const requestMutation = useMutationWithToast({
    mutationFn: (email: string) => requestPasswordReset(email),
    invalidateKeys: [],
    errorFallback: 'Failed to request a password reset',
    onSuccess: () => setSubmitted(true),
  })

  // The backend gives no signal either way on whether the email matched a
  // real account (enumeration resistance) -- this same generic message
  // shows for both, so there's nothing to branch on here either.
  if (submitted) {
    return (
      <Stack>
        <Text ta="center">
          If that email has an account, we&apos;ve sent a link to reset the password.
        </Text>
        <Anchor component={Link} to="/login" ta="center">
          Back to login
        </Anchor>
      </Stack>
    )
  }

  return (
    <form onSubmit={form.onSubmit((values) => requestMutation.mutate(values.email))}>
      <Stack>
        <Text size="sm" c="dimmed">
          Enter your email and we&apos;ll send you a link to reset your password.
        </Text>
        <TextInput
          label="Email"
          placeholder="you@example.com"
          autoComplete="email"
          type="email"
          {...form.getInputProps('email')}
        />
        <Button type="submit" loading={requestMutation.isPending} fullWidth>
          Send reset link
        </Button>
        <Text size="sm" ta="center">
          <Anchor component={Link} to="/login">
            Back to login
          </Anchor>
        </Text>
      </Stack>
    </form>
  )
}
