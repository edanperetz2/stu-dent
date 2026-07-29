import { Badge, Button, Group, Modal, Select, Stack, Table, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { deleteUser, listAllUsers, updateUser } from '../../api/admin'
import { apiErrorMessage } from '../../api/httpClient'
import type { Role } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { ConfirmButton } from '../../components/ConfirmButton'
import { LoadingText } from '../../components/StateText'

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'student', label: 'Student' },
  { value: 'attending', label: 'Attending' },
  { value: 'admin', label: 'Admin' },
  { value: 'patient', label: 'Patient' },
]

export function UsersPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [pendingRoleChange, setPendingRoleChange] = useState<{
    userId: string
    fullName: string
    newRole: Role
  } | null>(null)

  const { data: users, isLoading } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => listAllUsers(token),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })

  const updateMutation = useMutation({
    mutationFn: ({ userId, ...payload }: { userId: string; is_active?: boolean; role?: Role }) =>
      updateUser(token, userId, payload),
    onSuccess: invalidate,
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to update user'),
        color: 'red',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (userId: string) => deleteUser(token, userId),
    onSuccess: () => {
      invalidate()
      notifications.show({ message: 'User deleted', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to delete user'),
        color: 'red',
      })
    },
  })

  return (
    <Stack>
      <Title order={2}>Users</Title>

      {isLoading ? (
        <LoadingText />
      ) : (
        <Table.ScrollContainer minWidth={700}>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Name</Table.Th>
              <Table.Th>Email</Table.Th>
              <Table.Th>Role</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th />
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {users?.map((user) => {
              const isSelf = user.id === principal?.id
              return (
                <Table.Tr key={user.id}>
                  <Table.Td>{user.full_name}</Table.Td>
                  <Table.Td>{user.email}</Table.Td>
                  <Table.Td>
                    <Select
                      size="xs"
                      w={130}
                      data={ROLE_OPTIONS}
                      value={user.role}
                      allowDeselect={false}
                      disabled={isSelf}
                      onChange={(value) => {
                        if (value && value !== user.role) {
                          setPendingRoleChange({
                            userId: user.id,
                            fullName: user.full_name,
                            newRole: value as Role,
                          })
                        }
                      }}
                    />
                  </Table.Td>
                  <Table.Td>
                    <Badge color={user.is_active ? 'blue' : 'gray'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      {user.is_active ? (
                        <ConfirmButton
                          label="Deactivate"
                          color="red"
                          message={`This will deactivate ${user.full_name}'s account.`}
                          onConfirm={() =>
                            updateMutation.mutate({ userId: user.id, is_active: false })
                          }
                          loading={
                            updateMutation.isPending && updateMutation.variables?.userId === user.id
                          }
                        />
                      ) : (
                        <Button
                          size="xs"
                          variant="light"
                          color="green"
                          loading={
                            updateMutation.isPending && updateMutation.variables?.userId === user.id
                          }
                          onClick={() =>
                            updateMutation.mutate({ userId: user.id, is_active: true })
                          }
                        >
                          Activate
                        </Button>
                      )}
                      {!isSelf && (
                        <ConfirmButton
                          label="Delete"
                          message={`This will soft-delete ${user.full_name}'s account. This can't be undone from here.`}
                          onConfirm={() => deleteMutation.mutate(user.id)}
                          loading={deleteMutation.isPending && deleteMutation.variables === user.id}
                        />
                      )}
                    </Group>
                  </Table.Td>
                </Table.Tr>
              )
            })}
          </Table.Tbody>
        </Table>
        </Table.ScrollContainer>
      )}

      <Modal
        opened={!!pendingRoleChange}
        onClose={() => setPendingRoleChange(null)}
        title="Change role?"
      >
        <Stack>
          <Text size="sm">
            This will change {pendingRoleChange?.fullName}&apos;s role to{' '}
            <strong>{pendingRoleChange?.newRole}</strong>. They will immediately gain or lose
            whatever access that role has.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setPendingRoleChange(null)}>
              Cancel
            </Button>
            <Button
              color="red"
              loading={updateMutation.isPending}
              onClick={() => {
                if (pendingRoleChange) {
                  updateMutation.mutate({
                    userId: pendingRoleChange.userId,
                    role: pendingRoleChange.newRole,
                  })
                }
                setPendingRoleChange(null)
              }}
            >
              Change role
            </Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  )
}
