import {
  Badge,
  Box,
  Button,
  Collapse,
  Group,
  Modal,
  PasswordInput,
  Stack,
  Table,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Fragment, useState } from 'react'
import { apiErrorMessage } from '../../api/httpClient'
import { createPatient, listPatients, type PatientCreateInput } from '../../api/patients'
import { useAuthToken } from '../../auth/useAuthToken'
import { ClickableRow } from '../../components/ClickableRow'
import { TableSkeleton } from '../../components/Skeletons'
import { EmptyText, ErrorText } from '../../components/StateText'
import { useListQuery } from '../../hooks/useListQuery'
import { PatientDetailPanel } from './PatientDetailPanel'

export function PatientsListPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const [opened, { open, close }] = useDisclosure(false)
  const [expandedPatientId, setExpandedPatientId] = useState<string | null>(null)

  const patientsQuery = useListQuery({
    queryKey: ['patients'],
    queryFn: () => listPatients(token),
    errorFallback: 'Failed to load patients.',
  })

  const form = useForm<PatientCreateInput>({
    initialValues: { full_name: '', email: '', password: '', contact_phone: '' },
    validate: {
      full_name: (value) => (value.trim().length > 0 ? null : 'Full name is required'),
      email: (value) => (value.includes('@') ? null : 'Enter a valid email'),
      password: (value) => (value.length >= 8 ? null : 'Password must be at least 8 characters'),
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
        message: apiErrorMessage(err, 'Failed to create patient'),
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

      {patientsQuery.status === 'error' ? (
        <ErrorText onRetry={patientsQuery.retry}>{patientsQuery.message}</ErrorText>
      ) : patientsQuery.status === 'loading' ? (
        <TableSkeleton columns={5} />
      ) : patientsQuery.status === 'empty' ? (
        <EmptyText>No patients yet. Click "New Patient" to add one.</EmptyText>
      ) : (
        <Table.ScrollContainer minWidth={500}>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Phone</Table.Th>
              <Table.Th>Confirmation</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {patientsQuery.data.map((patient) => {
              const expanded = expandedPatientId === patient.id
              const toggle = () =>
                setExpandedPatientId((current) => (current === patient.id ? null : patient.id))
              return (
                <Fragment key={patient.id}>
                  <ClickableRow
                    onToggle={toggle}
                    expanded={expanded}
                    expandLabel={`Toggle details for ${patient.full_name}`}
                  >
                    <Table.Td>{patient.full_name}</Table.Td>
                    <Table.Td>{patient.contact_phone ?? '-'}</Table.Td>
                    <Table.Td>
                      {patient.owner_confirmed_at ? (
                        <Badge color="green">Confirmed</Badge>
                      ) : (
                        <Badge color="yellow">Pending confirmation</Badge>
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Badge color={patient.is_active ? 'blue' : 'gray'}>
                        {patient.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </Table.Td>
                  </ClickableRow>
                  <Table.Tr>
                    <Table.Td colSpan={5} p={0}>
                      <Collapse expanded={expanded} keepMounted={false}>
                        <Box p="md">
                          <PatientDetailPanel patient={patient} />
                        </Box>
                      </Collapse>
                    </Table.Td>
                  </Table.Tr>
                </Fragment>
              )
            })}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      )}

      <Modal opened={opened} onClose={close} title="New Patient" size="md">
        <form onSubmit={form.onSubmit((values) => createMutation.mutate(values))}>
          <Stack>
            <TextInput label="Full name" autoComplete="name" {...form.getInputProps('full_name')} />
            <TextInput
              label="Email"
              placeholder="patient@example.com"
              type="email"
              autoComplete="email"
              {...form.getInputProps('email')}
            />
            <PasswordInput
              label="Password"
              autoComplete="new-password"
              {...form.getInputProps('password')}
            />
            <TextInput
              label="Contact phone"
              type="tel"
              autoComplete="tel"
              {...form.getInputProps('contact_phone')}
            />
            <Button type="submit" loading={createMutation.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
