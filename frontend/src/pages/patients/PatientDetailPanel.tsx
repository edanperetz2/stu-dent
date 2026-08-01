import { Badge, Button, Divider, Group, Select, Stack, Text, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { apiErrorMessage } from '../../api/httpClient'
import { confirmPatient, deletePatient, updatePatient, type PatientUpdateInput } from '../../api/patients'
import type { PreferredTimeOfDay, User } from '../../api/types'
import { useAuthToken } from '../../auth/useAuthToken'
import { ConfirmButton } from '../../components/ConfirmButton'

const PREFERRED_TIME_OPTIONS: { value: PreferredTimeOfDay; label: string }[] = [
  { value: 'morning', label: 'Morning' },
  { value: 'afternoon', label: 'Afternoon' },
  { value: 'evening', label: 'Evening' },
]

interface PatientDetailPanelProps {
  patient: User
}

/** Inline expanded detail for a patient row -- takes the already-fetched
 * list object as a prop rather than re-fetching by id (listPatients already
 * returns every field this needs), same shape as ForumPostCard. */
export function PatientDetailPanel({ patient }: PatientDetailPanelProps) {
  const token = useAuthToken()
  const queryClient = useQueryClient()

  const form = useForm<PatientUpdateInput>({
    initialValues: {
      full_name: patient.full_name,
      contact_phone: patient.contact_phone ?? '',
      preferred_time_of_day: patient.preferred_time_of_day,
    },
    validate: {
      full_name: (value) => (value?.trim().length ? null : 'Full name is required'),
    },
  })

  useEffect(() => {
    form.setValues({
      full_name: patient.full_name,
      contact_phone: patient.contact_phone ?? '',
      preferred_time_of_day: patient.preferred_time_of_day,
    })
    // Re-sync only when these specific fields change (e.g. after a
    // successful save elsewhere), not on every refetch triggered by a
    // window-focus/background refetch returning a new-but-equal object --
    // depending on the whole `patient` object clobbered an in-progress
    // edit whenever that happened, same fix as ForumPostCard.tsx.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patient.full_name, patient.contact_phone, patient.preferred_time_of_day])

  const invalidatePatients = () => queryClient.invalidateQueries({ queryKey: ['patients'] })

  const updateMutation = useMutation({
    mutationFn: (payload: PatientUpdateInput) => updatePatient(token, patient.id, payload),
    onSuccess: () => {
      invalidatePatients()
      notifications.show({ message: 'Patient updated', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to update patient'),
        color: 'red',
      })
    },
  })

  const confirmMutation = useMutation({
    mutationFn: () => confirmPatient(token, patient.id),
    onSuccess: () => {
      invalidatePatients()
      notifications.show({ message: 'Patient confirmed', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to confirm patient'),
        color: 'red',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => deletePatient(token, patient.id),
    onSuccess: () => {
      invalidatePatients()
      notifications.show({ message: 'Patient deleted', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to delete patient'),
        color: 'red',
      })
    },
  })

  return (
    <Stack maw={480}>
      <Group justify="flex-end">
        <ConfirmButton
          label="Delete"
          message="This will deactivate the patient record. This can't be undone from here."
          onConfirm={() => deleteMutation.mutate()}
          loading={deleteMutation.isPending}
        />
      </Group>

      <form onSubmit={form.onSubmit((values) => updateMutation.mutate(values))}>
        <Stack>
          <TextInput label="Full name" autoComplete="name" {...form.getInputProps('full_name')} />
          <TextInput
            label="Contact phone"
            type="tel"
            autoComplete="tel"
            {...form.getInputProps('contact_phone')}
          />
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

      <Divider label="Account" />
      <Group>
        <Text size="sm">Email:</Text>
        <Text size="sm">{patient.email}</Text>
      </Group>
      <Group justify="space-between">
        <Group>
          <Text size="sm">Confirmation:</Text>
          <Badge color={patient.owner_confirmed_at ? 'green' : 'yellow'}>
            {patient.owner_confirmed_at ? 'Confirmed' : 'Pending confirmation'}
          </Badge>
        </Group>
        {!patient.owner_confirmed_at && (
          <Button
            variant="light"
            loading={confirmMutation.isPending}
            onClick={() => confirmMutation.mutate()}
          >
            Confirm
          </Button>
        )}
      </Group>
    </Stack>
  )
}
