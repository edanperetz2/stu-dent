import { Badge, Group, Select, Stack, Table, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
                      onChange={(value) =>
                        value &&
                        updateMutation.mutate({ userId: user.id, role: value as Role })
                      }
                    />
                  </Table.Td>
                  <Table.Td>
                    <Badge color={user.is_active ? 'blue' : 'gray'}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <ConfirmButton
                        label={user.is_active ? 'Deactivate' : 'Activate'}
                        color={user.is_active ? 'red' : 'green'}
                        message={`This will ${user.is_active ? 'deactivate' : 'activate'} ${user.full_name}'s account.`}
                        onConfirm={() =>
                          updateMutation.mutate({ userId: user.id, is_active: !user.is_active })
                        }
                        loading={updateMutation.isPending && updateMutation.variables?.userId === user.id}
                      />
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
    </Stack>
  )
}
