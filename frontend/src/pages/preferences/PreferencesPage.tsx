import { Button, Select, Stack, Text, TextInput, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { getCurrentUser, updateCurrentUser, type UserSelfUpdateInput } from '../../api/auth'
import { apiErrorMessage } from '../../api/httpClient'
import type { PreferredTimeOfDay } from '../../api/types'
import { useAuthToken } from '../../auth/useAuthToken'
import { LoadingText } from '../../components/StateText'

const PREFERRED_TIME_OPTIONS: { value: PreferredTimeOfDay; label: string }[] = [
  { value: 'morning', label: 'Morning' },
  { value: 'afternoon', label: 'Afternoon' },
  { value: 'evening', label: 'Evening' },
]

export function PreferencesPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()

  const { data: user, isLoading } = useQuery({
    queryKey: ['users', 'me'],
    queryFn: () => getCurrentUser(token),
  })

  const form = useForm<UserSelfUpdateInput>({
    initialValues: { contact_phone: '', preferred_time_of_day: null },
  })

  useEffect(() => {
    if (user) {
      form.setValues({
        contact_phone: user.contact_phone ?? '',
        preferred_time_of_day: user.preferred_time_of_day,
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-sync when the fetched user changes
  }, [user])

  const updateMutation = useMutation({
    mutationFn: (payload: UserSelfUpdateInput) => updateCurrentUser(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users', 'me'] })
      notifications.show({ message: 'Preferences saved', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to save preferences'),
        color: 'red',
      })
    },
  })

  if (isLoading) return <LoadingText />

  return (
    <Stack maw={420}>
      <Title order={2}>Preferences</Title>
      {user?.owner_student_id && (
        <Text size="sm" c="dimmed">
          In-charge student: {user.owner_student_name ?? 'Unknown'}
          {!user.owner_confirmed_at && ' (pending confirmation)'}
        </Text>
      )}
      <form onSubmit={form.onSubmit((values) => updateMutation.mutate(values))}>
        <Stack>
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
    </Stack>
  )
}
