import { Anchor, Button, PasswordInput, Stack, Text, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/httpClient'
import { useAuth } from '../../auth/AuthContext'

interface PatientLoginFormValues {
  email: string
  password: string
}

export function PatientLoginPage() {
  const { patientLogin } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<PatientLoginFormValues>({
    initialValues: { email: '', password: '' },
    validate: {
      email: (value) => (value.includes('@') ? null : 'Enter a valid email'),
      password: (value) => (value.length > 0 ? null : 'Password is required'),
    },
  })

  async function handleSubmit(values: PatientLoginFormValues) {
    setError(null)
    setSubmitting(true)
    try {
      await patientLogin(values.email, values.password)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <Text size="sm" c="dimmed">
          Patient login
        </Text>
        <TextInput label="Email" placeholder="you@example.com" {...form.getInputProps('email')} />
        <PasswordInput label="Password" {...form.getInputProps('password')} />
        {error && (
          <Text c="red" size="sm">
            {error}
          </Text>
        )}
        <Button type="submit" loading={submitting} fullWidth>
          Log in
        </Button>
        <Text size="sm" ta="center">
          Are you a student, attending, or admin?{' '}
          <Anchor component={Link} to="/login">
            Log in here
          </Anchor>
        </Text>
      </Stack>
    </form>
  )
}
