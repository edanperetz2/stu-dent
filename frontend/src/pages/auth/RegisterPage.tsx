import { Anchor, Button, PasswordInput, Select, Stack, Text, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/httpClient'
import type { Role } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'

interface RegisterFormValues {
  fullName: string
  email: string
  password: string
  role: Role
}

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'student', label: 'Student' },
  { value: 'attending', label: 'Attending' },
  { value: 'admin', label: 'Admin' },
]

export function RegisterPage() {
  const { registerUser } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm<RegisterFormValues>({
    initialValues: { fullName: '', email: '', password: '', role: 'student' },
    validate: {
      fullName: (value) => (value.trim().length > 0 ? null : 'Full name is required'),
      email: (value) => (value.includes('@') ? null : 'Enter a valid email'),
      password: (value) => (value.length >= 8 ? null : 'Password must be at least 8 characters'),
    },
  })

  async function handleSubmit(values: RegisterFormValues) {
    setError(null)
    setSubmitting(true)
    try {
      await registerUser(values.email, values.password, values.fullName, values.role)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Registration failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack>
        <TextInput label="Full name" {...form.getInputProps('fullName')} />
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
          Register
        </Button>
        <Text size="sm" ta="center">
          Already have an account?{' '}
          <Anchor component={Link} to="/login">
            Log in
          </Anchor>
        </Text>
      </Stack>
    </form>
  )
}
