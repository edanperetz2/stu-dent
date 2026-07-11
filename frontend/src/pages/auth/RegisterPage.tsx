import { Anchor, Button, PasswordInput, Select, Stack, Text, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listStudents } from '../../api/students'
import { ApiError } from '../../api/httpClient'
import type { Role } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'

interface RegisterFormValues {
  fullName: string
  email: string
  password: string
  role: Role
  ownerStudentId: string
}

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'student', label: 'Student' },
  { value: 'attending', label: 'Attending' },
  { value: 'admin', label: 'Admin' },
  { value: 'patient', label: 'Patient' },
]

export function RegisterPage() {
  const { registerUser } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [pendingConfirmation, setPendingConfirmation] = useState(false)

  const form = useForm<RegisterFormValues>({
    initialValues: { fullName: '', email: '', password: '', role: 'student', ownerStudentId: '' },
    validate: {
      fullName: (value) => (value.trim().length > 0 ? null : 'Full name is required'),
      email: (value) => (value.includes('@') ? null : 'Enter a valid email'),
      password: (value) => (value.length >= 8 ? null : 'Password must be at least 8 characters'),
      ownerStudentId: (value, values) =>
        values.role === 'patient' && !value ? 'Choose your student' : null,
    },
  })

  const { data: students } = useQuery({
    queryKey: ['students'],
    queryFn: listStudents,
    enabled: form.values.role === 'patient',
  })

  async function handleSubmit(values: RegisterFormValues) {
    setError(null)
    setSubmitting(true)
    try {
      await registerUser(
        values.email,
        values.password,
        values.fullName,
        values.role,
        values.role === 'patient' ? values.ownerStudentId : undefined,
      )
      if (values.role === 'patient') {
        setPendingConfirmation(true)
      } else {
        navigate('/')
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Registration failed')
    } finally {
      setSubmitting(false)
    }
  }

  if (pendingConfirmation) {
    return (
      <Stack>
        <Text ta="center">
          Your account was created. Your student needs to confirm the connection before you can
          book appointments or send messages.
        </Text>
        <Anchor component={Link} to="/login" ta="center">
          Go to login
        </Anchor>
      </Stack>
    )
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
        {form.values.role === 'patient' && (
          <Select
            label="Choose your student"
            placeholder="Select a student"
            data={(students ?? []).map((s) => ({ value: s.id, label: s.full_name }))}
            {...form.getInputProps('ownerStudentId')}
          />
        )}
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
