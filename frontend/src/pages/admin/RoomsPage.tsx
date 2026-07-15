import { Badge, Button, Group, Modal, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { DateTimePicker } from '@mantine/dates'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { apiErrorMessage } from '../../api/httpClient'
import { createRoom, listAllRooms, updateRoom, type RoomCreateInput } from '../../api/rooms'
import { useAuthToken } from '../../auth/useAuthToken'
import { LoadingText } from '../../components/StateText'
import { formatDateTime, mantineDateTimeToIso } from '../../utils/dates'

export function RoomsPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const [opened, { open, close }] = useDisclosure(false)
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')
  const [deactivateOpened, { open: openDeactivate, close: closeDeactivate }] = useDisclosure(false)
  const [deactivatingRoomId, setDeactivatingRoomId] = useState<string | null>(null)
  const [reactivateAt, setReactivateAt] = useState<string | null>(null)

  const { data: rooms, isLoading } = useQuery({
    queryKey: ['admin', 'rooms'],
    queryFn: () => listAllRooms(token),
  })

  const form = useForm<RoomCreateInput>({
    initialValues: { name: '' },
    validate: {
      name: (value) => (value.trim().length > 0 ? null : 'Name is required'),
    },
  })

  const createMutation = useMutation({
    mutationFn: (payload: RoomCreateInput) => createRoom(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'rooms'] })
      queryClient.invalidateQueries({ queryKey: ['rooms'] })
      notifications.show({ message: 'Room created', color: 'green' })
      form.reset()
      close()
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to create room'),
        color: 'red',
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      roomId,
      ...payload
    }: {
      roomId: string
      name?: string
      is_active?: boolean
      inactive_until?: string | null
    }) => updateRoom(token, roomId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'rooms'] })
      queryClient.invalidateQueries({ queryKey: ['rooms'] })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to update room'),
        color: 'red',
      })
    },
  })

  function handleDeactivateClick(roomId: string) {
    setDeactivatingRoomId(roomId)
    setReactivateAt(null)
    openDeactivate()
  }

  function confirmDeactivate() {
    if (!deactivatingRoomId) return
    updateMutation.mutate({
      roomId: deactivatingRoomId,
      is_active: false,
      inactive_until: reactivateAt ? mantineDateTimeToIso(reactivateAt) : null,
    })
    closeDeactivate()
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Rooms</Title>
        <Button onClick={open}>New Room</Button>
      </Group>

      {isLoading ? (
        <LoadingText />
      ) : (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rooms?.map((room) => (
              <Table.Tr key={room.id}>
                <Table.Td>
                  {renamingId === room.id ? (
                    <TextInput
                      size="xs"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.currentTarget.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && renameValue.trim()) {
                          updateMutation.mutate({ roomId: room.id, name: renameValue.trim() })
                          setRenamingId(null)
                        }
                        if (e.key === 'Escape') setRenamingId(null)
                      }}
                      autoFocus
                    />
                  ) : (
                    <Text
                      style={{ cursor: 'pointer' }}
                      onClick={() => {
                        setRenamingId(room.id)
                        setRenameValue(room.name)
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setRenamingId(room.id)
                          setRenameValue(room.name)
                        }
                      }}
                      tabIndex={0}
                      role="button"
                    >
                      {room.name}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Badge color={room.is_active ? 'blue' : 'gray'}>
                    {room.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                  {!room.is_active && room.inactive_until && (
                    <Text size="xs" c="dimmed">
                      Reactivates {formatDateTime(room.inactive_until)}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Button
                    size="xs"
                    variant="light"
                    color={room.is_active ? 'red' : 'green'}
                    loading={updateMutation.isPending}
                    onClick={() =>
                      room.is_active
                        ? handleDeactivateClick(room.id)
                        : updateMutation.mutate({ roomId: room.id, is_active: true })
                    }
                  >
                    {room.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="New Room">
        <form onSubmit={form.onSubmit((values) => createMutation.mutate(values))}>
          <Stack>
            <TextInput label="Name" {...form.getInputProps('name')} />
            <Button type="submit" loading={createMutation.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={deactivateOpened} onClose={closeDeactivate} title="Deactivate room">
        <Stack>
          <Text size="sm" c="dimmed">
            Students booking a future appointment in this room will be notified.
          </Text>
          <DateTimePicker
            label="Automatically reactivate on (optional)"
            clearable
            value={reactivateAt}
            onChange={setReactivateAt}
          />
          <Button color="red" loading={updateMutation.isPending} onClick={confirmDeactivate}>
            Deactivate
          </Button>
        </Stack>
      </Modal>
    </Stack>
  )
}
