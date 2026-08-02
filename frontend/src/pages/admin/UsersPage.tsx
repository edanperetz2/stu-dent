import { Badge, Button, Group, Modal, Select, Stack, Table, Text, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type Dispatch, type SetStateAction } from 'react'
import { deleteUser, listAllUsers, updateUser } from '../../api/admin'
import { apiErrorMessage } from '../../api/httpClient'
import type { Role } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { ConfirmButton } from '../../components/ConfirmButton'
import { TableSkeleton } from '../../components/Skeletons'
import { ErrorText } from '../../components/StateText'
import { showUndoToast } from '../../hooks/showUndoToast'
import { useListQuery } from '../../hooks/useListQuery'

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'student', label: 'Student' },
  { value: 'attending', label: 'Attending' },
  { value: 'admin', label: 'Admin' },
  { value: 'patient', label: 'Patient' },
]

/** Adds/removes one id from a Set-valued state setter -- used to track
 * per-row pending state independently of `useMutation`'s own `isPending`/
 * `variables`, which reflect only the single most-recently-fired call. One
 * shared `updateMutation`/`deleteMutation` handles every row in this table,
 * so two rows mutated within moments of each other would otherwise show a
 * stale or wrong loading spinner -- each row's own membership in this Set
 * survives regardless of what any other row does concurrently. */
function togglePending(setPending: Dispatch<SetStateAction<Set<string>>>, id: string, present: boolean) {
  setPending((prev) => {
    const next = new Set(prev)
    if (present) next.add(id)
    else next.delete(id)
    return next
  })
}

export function UsersPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [pendingRoleChange, setPendingRoleChange] = useState<{
    userId: string
    fullName: string
    newRole: Role
  } | null>(null)
  const [pendingUpdateIds, setPendingUpdateIds] = useState<Set<string>>(new Set())
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Set<string>>(new Set())

  // isEmpty always false -- an empty user list still renders the (empty)
  // table, same reasoning as RoomsPage/EquipmentPage.
  const usersQuery = useListQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => listAllUsers(token),
    errorFallback: 'Failed to load users.',
    isEmpty: () => false,
  })
  const users = usersQuery.status === 'ready' ? usersQuery.data : undefined

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

      {usersQuery.status === 'error' ? (
        <ErrorText onRetry={usersQuery.retry}>{usersQuery.message}</ErrorText>
      ) : usersQuery.status === 'loading' ? (
        <TableSkeleton columns={5} />
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
                        <Button
                          size="xs"
                          variant="light"
                          color="red"
                          loading={pendingUpdateIds.has(user.id)}
                          onClick={() => {
                            // Undo awaits this exact request before re-mutating --
                            // otherwise a fast Undo click fires a second PATCH
                            // while the first is still in flight, and whichever
                            // response's cache-invalidation resolves last wins
                            // the displayed state, regardless of click order.
                            togglePending(setPendingUpdateIds, user.id, true)
                            const deactivating = updateMutation
                              .mutateAsync({ userId: user.id, is_active: false })
                              .finally(() => togglePending(setPendingUpdateIds, user.id, false))
                            showUndoToast({
                              message: `${user.full_name}'s account was deactivated.`,
                              onUndo: async () => {
                                await deactivating.catch(() => {})
                                togglePending(setPendingUpdateIds, user.id, true)
                                updateMutation.mutate(
                                  { userId: user.id, is_active: true },
                                  { onSettled: () => togglePending(setPendingUpdateIds, user.id, false) },
                                )
                              },
                            })
                          }}
                        >
                          Deactivate
                        </Button>
                      ) : (
                        <Button
                          size="xs"
                          variant="light"
                          color="green"
                          loading={pendingUpdateIds.has(user.id)}
                          onClick={() => {
                            togglePending(setPendingUpdateIds, user.id, true)
                            updateMutation.mutate(
                              { userId: user.id, is_active: true },
                              { onSettled: () => togglePending(setPendingUpdateIds, user.id, false) },
                            )
                          }}
                        >
                          Activate
                        </Button>
                      )}
                      {!isSelf && (
                        <ConfirmButton
                          label="Delete"
                          message={`This will soft-delete ${user.full_name}'s account. This can't be undone from here.`}
                          onConfirm={async () => {
                            // Returning the mutation's own promise (not
                            // fire-and-forget `.mutate`) lets ConfirmButton
                            // actually await it before closing -- otherwise
                            // the modal closes on the next microtask and the
                            // spinner never has anything to reflect.
                            togglePending(setPendingDeleteIds, user.id, true)
                            try {
                              await deleteMutation.mutateAsync(user.id)
                            } finally {
                              togglePending(setPendingDeleteIds, user.id, false)
                            }
                          }}
                          loading={pendingDeleteIds.has(user.id)}
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
        size="sm"
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
