import { Anchor, Button, PasswordInput, Select, Stack, Text, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiErrorMessage } from '../../api/httpClient'
import type { Role } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'

interface LoginFormValues {
  email: string
  password: string
  role: Role | ''
}

const ROLE_OPTIONS: { value: Role | ''; label: string }[] = [
  { value: '', label: 'Any' },
  { value: 'student', label: 'Student' },
  { value: 'attending', label: 'Attending' },
  { value: 'admin', label: 'Admin' },
  { value: 'patient', label: 'Patient' },
]

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<LoginFormValues>({
    initialValues: { email: '', password: '', role: '' },
    validate: {
      email: (value) => (value.includes('@') ? null : 'Enter a valid email'),
      password: (value) => (value.length > 0 ? null : 'Password is required'),
    },
  })

  async function handleSubmit(values: LoginFormValues) {
    setError(null)
    setSubmitting(true)
    try {
      await login(values.email, values.password, values.role || undefined)
      navigate('/')
    } catch (err) {
      setError(apiErrorMessage(err, 'Login failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <TextInput label="Email" placeholder="you@example.com" {...form.getInputProps('email')} />
        <PasswordInput label="Password" {...form.getInputProps('password')} />
        <Select
          label="Role"
          data={ROLE_OPTIONS}
          allowDeselect={false}
          {...form.getInputProps('role')}
        />
        {error && (
          <Text c="red" size="sm">
            {error}
          </Text>
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
