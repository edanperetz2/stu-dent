import { Badge, Button, Group, Modal, Stack, Table, TextInput, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createEquipment,
  listAllEquipment,
  updateEquipment,
  type EquipmentCreateInput,
} from '../../api/equipment'
import { apiErrorMessage } from '../../api/httpClient'
import { useAuthToken } from '../../auth/useAuthToken'
import { LoadingText } from '../../components/StateText'

export function EquipmentPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const [opened, { open, close }] = useDisclosure(false)

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

  const toggleActiveMutation = useMutation({
    mutationFn: ({ equipmentId, is_active }: { equipmentId: string; is_active: boolean }) =>
      updateEquipment(token, equipmentId, { is_active }),
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

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Equipment</Title>
        <Button onClick={open}>New Equipment</Button>
      </Group>

      {isLoading ? (
        <LoadingText />
      ) : (
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
                </Table.Td>
                <Table.Td>
                  <Button
                    size="xs"
                    variant="light"
                    color={item.is_active ? 'red' : 'green'}
                    loading={toggleActiveMutation.isPending}
                    onClick={() =>
                      toggleActiveMutation.mutate({
                        equipmentId: item.id,
                        is_active: !item.is_active,
                      })
                    }
                  >
                    {item.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
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
    </Stack>
  )
}
