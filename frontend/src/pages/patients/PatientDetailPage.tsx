import {
  Badge,
  Button,
  Divider,
  Group,
  PasswordInput,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../../api/httpClient'
import {
  deletePatient,
  getPatient,
  setPatientCredentials,
  updatePatient,
  type PatientUpdateInput,
} from '../../api/patients'
import type { PreferredTimeOfDay } from '../../api/types'
import { useAuthToken } from '../../auth/useAuthToken'
import { ConfirmButton } from '../../components/ConfirmButton'

const PREFERRED_TIME_OPTIONS: { value: PreferredTimeOfDay; label: string }[] = [
  { value: 'morning', label: 'Morning' },
  { value: 'afternoon', label: 'Afternoon' },
  { value: 'evening', label: 'Evening' },
]

export function PatientDetailPage() {
  const { patientId } = useParams<{ patientId: string }>()
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data: patient, isLoading } = useQuery({
    queryKey: ['patients', patientId],
    queryFn: () => getPatient(token, patientId!),
    enabled: !!patientId,
  })

  const form = useForm<PatientUpdateInput>({
    initialValues: { full_name: '', contact_phone: '', preferred_time_of_day: null },
  })

  useEffect(() => {
    if (patient) {
      form.setValues({
        full_name: patient.full_name,
        contact_phone: patient.contact_phone ?? '',
        preferred_time_of_day: patient.preferred_time_of_day,
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-sync when the fetched patient changes
  }, [patient])

  const updateMutation = useMutation({
    mutationFn: (payload: PatientUpdateInput) => updatePatient(token, patientId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients', patientId] })
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      notifications.show({ message: 'Patient updated', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: err instanceof ApiError ? err.message : 'Failed to update patient',
        color: 'red',
      })
    },
  })

  const credentialsForm = useForm({ initialValues: { email: '', password: '' } })

  const credentialsMutation = useMutation({
    mutationFn: (values: { email: string; password: string }) =>
      setPatientCredentials(token, patientId!, values.email, values.password),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients', patientId] })
      notifications.show({ message: 'Login credentials set', color: 'green' })
      credentialsForm.reset()
    },
    onError: (err) => {
      notifications.show({
        message: err instanceof ApiError ? err.message : 'Failed to set credentials',
        color: 'red',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePatient(token, patientId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      notifications.show({ message: 'Patient deleted', color: 'green' })
      navigate('/patients')
    },
    onError: (err) => {
      notifications.show({
        message: err instanceof ApiError ? err.message : 'Failed to delete patient',
        color: 'red',
      })
    },
  })

  if (isLoading) return <Text>Loading...</Text>
  if (!patient) return <Text>Patient not found.</Text>

  return (
    <Stack maw={480}>
      <Group justify="space-between">
        <Title order={2}>{patient.full_name}</Title>
        <ConfirmButton
          label="Delete"
          message="This will deactivate the patient record. This can't be undone from here."
          onConfirm={() => deleteMutation.mutate()}
          loading={deleteMutation.isPending}
        />
      </Group>

      <form onSubmit={form.onSubmit((values) => updateMutation.mutate(values))}>
        <Stack>
          <TextInput label="Full name" {...form.getInputProps('full_name')} />
          <TextInput label="Contact phone" {...form.getInputProps('contact_phone')} />
          <Select
            label="Preferred time of day"
            data={PREFERRED_TIME_OPTIONS}
            clearable
            {...form.getInputProps('preferred_time_of_day')}
          />
          <Button type="submit" loading={updateMutation.isPending}>
            Save
          </Button>
        </Stack>
      </form>

      <Divider label="Login credentials" />
      <Group>
        <Text size="sm">Status:</Text>
        <Badge color={patient.email ? 'green' : 'gray'}>
          {patient.email ? `Provisioned (${patient.email})` : 'Not provisioned'}
        </Badge>
      </Group>
      <form onSubmit={credentialsForm.onSubmit((values) => credentialsMutation.mutate(values))}>
        <Stack>
          <TextInput label="Email" {...credentialsForm.getInputProps('email')} />
          <PasswordInput label="Password" {...credentialsForm.getInputProps('password')} />
          <Button type="submit" loading={credentialsMutation.isPending} variant="light">
            {patient.email ? 'Update credentials' : 'Provision login'}
          </Button>
        </Stack>
      </form>
    </Stack>
  )
}
