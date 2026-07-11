import { Badge, Button, Group, Modal, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../../api/httpClient'
import { createPatient, listPatients, type PatientCreateInput } from '../../api/patients'
import { useAuthToken } from '../../auth/useAuthToken'

export function PatientsListPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [opened, { open, close }] = useDisclosure(false)

  const { data: patients, isLoading } = useQuery({
    queryKey: ['patients'],
    queryFn: () => listPatients(token),
  })

  const form = useForm<PatientCreateInput>({
    initialValues: { full_name: '', contact_phone: '' },
    validate: {
      full_name: (value) => (value.trim().length > 0 ? null : 'Full name is required'),
    },
  })

  const createMutation = useMutation({
    mutationFn: (payload: PatientCreateInput) => createPatient(token, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      notifications.show({ message: 'Patient created', color: 'green' })
      form.reset()
      close()
    },
    onError: (err) => {
      notifications.show({
        message: err instanceof ApiError ? err.message : 'Failed to create patient',
        color: 'red',
      })
    },
  })

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Patients</Title>
        <Button onClick={open}>New Patient</Button>
      </Group>

      {isLoading ? (
        <Text>Loading...</Text>
      ) : (
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Phone</Table.Th>
              <Table.Th>Login</Table.Th>
              <Table.Th>Status</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {patients?.map((patient) => (
              <Table.Tr
                key={patient.id}
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/patients/${patient.id}`)}
              >
                <Table.Td>{patient.full_name}</Table.Td>
                <Table.Td>{patient.contact_phone ?? '-'}</Table.Td>
                <Table.Td>
                  {patient.email ? (
                    <Badge color="green">Provisioned</Badge>
                  ) : (
                    <Badge color="gray">None</Badge>
                  )}
                </Table.Td>
                <Table.Td>
                  <Badge color={patient.is_active ? 'blue' : 'gray'}>
                    {patient.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}

      <Modal opened={opened} onClose={close} title="New Patient">
        <form onSubmit={form.onSubmit((values) => createMutation.mutate(values))}>
          <Stack>
            <TextInput label="Full name" {...form.getInputProps('full_name')} />
            <TextInput label="Contact phone" {...form.getInputProps('contact_phone')} />
            <Button type="submit" loading={createMutation.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
