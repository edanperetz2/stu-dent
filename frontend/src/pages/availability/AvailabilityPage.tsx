import { ActionIcon, Button, Group, Select, Stack, Table, TextInput, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { IconTrash } from '@tabler/icons-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  getMyAvailability,
  replaceMyAvailability,
  type AvailabilityWindowInput,
} from '../../api/availability'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuthToken } from '../../auth/useAuthToken'
import { LoadingText } from '../../components/StateText'

const DAY_LABELS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
const DAY_OPTIONS = DAY_LABELS.map((label, index) => ({ value: String(index), label }))

export function AvailabilityPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['availability'],
    queryFn: () => getMyAvailability(token),
  })

  const [windows, setWindows] = useState<AvailabilityWindowInput[]>([])
  const [dayOfWeek, setDayOfWeek] = useState<string | null>('0')
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime] = useState('17:00')

  useEffect(() => {
    if (data) {
      setWindows(
        data.map((w) => ({
          day_of_week: w.day_of_week,
          start_time: w.start_time,
          end_time: w.end_time,
        })),
      )
    }
  }, [data])

  const saveMutation = useMutation({
    mutationFn: (payload: AvailabilityWindowInput[]) => replaceMyAvailability(token, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(['availability'], updated)
      notifications.show({ message: 'Availability saved', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to save availability'),
        color: 'red',
      })
    },
  })

  function addWindow() {
    if (dayOfWeek === null) return
    setWindows((prev) => [
      ...prev,
      { day_of_week: Number(dayOfWeek), start_time: `${startTime}:00`, end_time: `${endTime}:00` },
    ])
  }

  function removeWindow(index: number) {
    setWindows((prev) => prev.filter((_, i) => i !== index))
  }

  if (isLoading) return <LoadingText />

  return (
    <Stack maw={560}>
      <Title order={2}>Weekly Availability</Title>

      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Day</Table.Th>
            <Table.Th>Start</Table.Th>
            <Table.Th>End</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {windows.map((window, index) => (
            <Table.Tr key={`${window.day_of_week}-${window.start_time}-${index}`}>
              <Table.Td>{DAY_LABELS[window.day_of_week]}</Table.Td>
              <Table.Td>{window.start_time.slice(0, 5)}</Table.Td>
              <Table.Td>{window.end_time.slice(0, 5)}</Table.Td>
              <Table.Td>
                <ActionIcon
                  color="red"
                  variant="subtle"
                  onClick={() => removeWindow(index)}
                  aria-label="Remove availability window"
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Group align="flex-end">
        <Select label="Day" data={DAY_OPTIONS} value={dayOfWeek} onChange={setDayOfWeek} />
        <TextInput
          label="Start"
          type="time"
          value={startTime}
          onChange={(event) => setStartTime(event.currentTarget.value)}
        />
        <TextInput
          label="End"
          type="time"
          value={endTime}
          onChange={(event) => setEndTime(event.currentTarget.value)}
        />
        <Button onClick={addWindow}>Add window</Button>
      </Group>

      <Button onClick={() => saveMutation.mutate(windows)} loading={saveMutation.isPending}>
        Save
      </Button>
    </Stack>
  )
}
