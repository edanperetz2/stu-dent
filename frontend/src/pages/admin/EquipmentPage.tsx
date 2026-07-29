import { Badge, Button, Group, Modal, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  createEquipment,
  listAllEquipment,
  updateEquipment,
  type EquipmentCreateInput,
} from '../../api/equipment'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuthToken } from '../../auth/useAuthToken'
import { AppointmentDateTimeInput } from '../../components/AppointmentDateTimeInput'
import { LoadingText } from '../../components/StateText'
import { FULL_DAY_HALF_HOUR_OPTIONS, formatDateTime, mantineDateTimeToIso } from '../../utils/dates'

export function EquipmentPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const [opened, { open, close }] = useDisclosure(false)
  const [deactivateOpened, { open: openDeactivate, close: closeDeactivate }] = useDisclosure(false)
  const [deactivatingId, setDeactivatingId] = useState<string | null>(null)
  const [reactivateAt, setReactivateAt] = useState<string | null>(null)

  const { data: equipment, isLoading } = useQuery({
    queryKey: ['admin', 'equipment'],
    queryFn: () => listAllEquipment(token),
  })

  const form = useForm<EquipmentCreateInput>({
    initialValues: { name: '', equipment_type: '' },
    validate: {
      name: (value) => (value.trim().length > 0 ? null : 'Name is required'),
    },
  })

  const createMutation = useMutation({
    mutationFn: (payload: EquipmentCreateInput) => createEquipment(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'equipment'] })
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
      notifications.show({ message: 'Equipment created', color: 'green' })
      form.reset()
      close()
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to create equipment'),
        color: 'red',
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({
      equipmentId,
      ...payload
    }: {
      equipmentId: string
      is_active?: boolean
      inactive_until?: string | null
    }) => updateEquipment(token, equipmentId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'equipment'] })
      queryClient.invalidateQueries({ queryKey: ['equipment'] })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to update equipment'),
        color: 'red',
      })
    },
  })

  function handleDeactivateClick(equipmentId: string) {
    setDeactivatingId(equipmentId)
    setReactivateAt(null)
    openDeactivate()
  }

  function confirmDeactivate() {
    if (!deactivatingId) return
    updateMutation.mutate({
      equipmentId: deactivatingId,
      is_active: false,
      inactive_until: reactivateAt ? mantineDateTimeToIso(reactivateAt) : null,
    })
    closeDeactivate()
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Equipment</Title>
        <Button onClick={open}>New Equipment</Button>
      </Group>

      {isLoading ? (
        <LoadingText />
      ) : (
        <Table.ScrollContainer minWidth={500}>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Type</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {equipment?.map((item) => (
              <Table.Tr key={item.id}>
                <Table.Td>{item.name}</Table.Td>
                <Table.Td>{item.equipment_type ?? '-'}</Table.Td>
                <Table.Td>
                  <Badge color={item.is_active ? 'blue' : 'gray'}>
                    {item.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                  {!item.is_active && item.inactive_until && (
                    <Text size="xs" c="dimmed">
                      Reactivates {formatDateTime(item.inactive_until)}
                    </Text>
                  )}
                </Table.Td>
                <Table.Td>
                  <Button
                    size="xs"
                    variant="light"
                    color={item.is_active ? 'red' : 'green'}
                    loading={
                      updateMutation.isPending && updateMutation.variables?.equipmentId === item.id
                    }
                    onClick={() =>
                      item.is_active
                        ? handleDeactivateClick(item.id)
                        : updateMutation.mutate({ equipmentId: item.id, is_active: true })
                    }
                  >
                    {item.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      )}

      <Modal opened={opened} onClose={close} title="New Equipment">
        <form onSubmit={form.onSubmit((values) => createMutation.mutate(values))}>
          <Stack>
            <TextInput label="Name" {...form.getInputProps('name')} />
            <TextInput label="Type (optional)" {...form.getInputProps('equipment_type')} />
            <Button type="submit" loading={createMutation.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={deactivateOpened} onClose={closeDeactivate} title="Deactivate equipment">
        <Stack>
          <Text size="sm" c="dimmed">
            Students booking a future appointment using this equipment will be notified.
          </Text>
          <AppointmentDateTimeInput
            label="Automatically reactivate on (optional)"
            value={reactivateAt}
            onChange={setReactivateAt}
            timeOptions={FULL_DAY_HALF_HOUR_OPTIONS}
          />
          <Button color="red" loading={updateMutation.isPending} onClick={confirmDeactivate}>
            Deactivate
          </Button>
        </Stack>
      </Modal>
    </Stack>
  )
}
