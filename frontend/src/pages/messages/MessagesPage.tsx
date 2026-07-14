import {
  Badge,
  Box,
  Button,
  Divider,
  Group,
  Modal,
  MultiSelect,
  NavLink,
  Paper,
  ScrollArea,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { listAttendings } from '../../api/attendings'
import { apiErrorMessage } from '../../api/httpClient'
import {
  createGroup,
  getThreadSummaries,
  listContacts,
  listGroups,
  listMessages,
  markRead,
  markUnread,
  sendMessage,
  targetKey,
  type MessageTarget,
  type ThreadSummary,
} from '../../api/messages'
import { listStudents } from '../../api/students'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { EmptyText, LoadingText } from '../../components/StateText'

interface Selection {
  target: MessageTarget
  label: string
}

export function MessagesPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [body, setBody] = useState('')
  const [selected, setSelected] = useState<Selection | null>(null)
  const [groupModalOpened, groupModalHandlers] = useDisclosure(false)

  const isAdmin = principal?.role === 'admin'
  const canCreateGroup = principal?.role === 'student' || principal?.role === 'attending'
  const selectedKey = selected ? targetKey(selected.target) : null

  const { data: contacts, isLoading: contactsLoading } = useQuery({
    queryKey: ['messages', 'contacts'],
    queryFn: () => listContacts(token),
  })

  const { data: groups, isLoading: groupsLoading } = useQuery({
    queryKey: ['messages', 'groups'],
    queryFn: () => listGroups(token),
  })

  const { data: threadSummaries } = useQuery({
    queryKey: ['messages', 'thread-summaries'],
    queryFn: () => getThreadSummaries(token),
  })
  const summaryByKey = useMemo(() => {
    const map = new Map<string, ThreadSummary>()
    for (const summary of threadSummaries ?? []) map.set(summary.target_key, summary)
    return map
  }, [threadSummaries])

  const { data: messages, isLoading: messagesLoading } = useQuery({
    queryKey: ['messages', 'thread', selectedKey],
    queryFn: () => listMessages(token, selected!.target),
    enabled: !!selected,
  })

  const markReadMutation = useMutation({
    mutationFn: (target: MessageTarget) => markRead(token, target),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages', 'unread-count'] })
      queryClient.invalidateQueries({ queryKey: ['messages', 'thread-summaries'] })
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to mark thread as read'),
        color: 'red',
      }),
  })

  const markUnreadMutation = useMutation({
    mutationFn: (target: MessageTarget) => markUnread(token, target),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages', 'unread-count'] })
      queryClient.invalidateQueries({ queryKey: ['messages', 'thread-summaries'] })
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to mark thread as unread'),
        color: 'red',
      }),
  })

  useEffect(() => {
    if (selected) {
      markReadMutation.mutate(selected.target)
    }
    // Only re-run when the selected conversation itself changes -- not on
    // every markReadMutation identity change (that would re-fire on its
    // own success/error callbacks).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey])

  const sendMutation = useMutation({
    mutationFn: (text: string) => sendMessage(token, selected!.target, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages'] })
      setBody('')
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to send message'),
        color: 'red',
      }),
  })

  const { data: allStudents } = useQuery({
    queryKey: ['students'],
    queryFn: () => listStudents(),
    enabled: groupModalOpened,
  })
  const { data: allAttendings } = useQuery({
    queryKey: ['attendings'],
    queryFn: () => listAttendings(token),
    enabled: groupModalOpened,
  })

  const groupForm = useForm({ initialValues: { title: '', participant_ids: [] as string[] } })

  const createGroupMutation = useMutation({
    mutationFn: () => createGroup(token, groupForm.values.title, groupForm.values.participant_ids),
    onSuccess: (group) => {
      queryClient.invalidateQueries({ queryKey: ['messages', 'groups'] })
      groupModalHandlers.close()
      groupForm.reset()
      setSelected({ target: { kind: 'group', conversationId: group.id }, label: group.title })
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to create group'),
        color: 'red',
      }),
  })

  const participantOptions = useMemo(() => {
    const students = (allStudents ?? [])
      .filter((s) => s.id !== principal?.id)
      .map((s) => ({ value: s.id, label: `${s.full_name} (student)` }))
    const attendings = (allAttendings ?? [])
      .filter((a) => a.id !== principal?.id)
      .map((a) => ({ value: a.id, label: `${a.full_name} (attending)` }))
    return [...students, ...attendings]
  }, [allStudents, allAttendings, principal])

  const contactItems: Selection[] = (contacts ?? []).map((c) =>
    isAdmin
      ? { target: { kind: 'admin', ownerId: c.id }, label: `${c.full_name} (${c.role})` }
      : { target: { kind: 'direct', otherUserId: c.id }, label: c.full_name },
  )

  const groupItems: Selection[] = (groups ?? []).map((g) => ({
    target: { kind: 'group', conversationId: g.id },
    label: g.title,
  }))

  // Unread threads first, then most-recent-activity first; threads with no
  // activity yet (e.g. a just-created group with no messages) sort last,
  // falling back to alphabetical by label so the order stays stable.
  const sortByActivity = (items: Selection[]): Selection[] =>
    [...items].sort((a, b) => {
      const summaryA = summaryByKey.get(targetKey(a.target))
      const summaryB = summaryByKey.get(targetKey(b.target))
      const unreadA = summaryA?.has_unread ?? false
      const unreadB = summaryB?.has_unread ?? false
      if (unreadA !== unreadB) return unreadA ? -1 : 1

      const timeA = summaryA?.last_message_at ? new Date(summaryA.last_message_at).getTime() : null
      const timeB = summaryB?.last_message_at ? new Date(summaryB.last_message_at).getTime() : null
      if (timeA !== null && timeB !== null) return timeB - timeA
      if (timeA !== null) return -1
      if (timeB !== null) return 1
      return a.label.localeCompare(b.label)
    })

  const sortedContactItems = sortByActivity(
    isAdmin ? contactItems : [...contactItems, { target: { kind: 'admin' }, label: 'Admin' }],
  )
  const sortedGroupItems = sortByActivity(groupItems)

  const selectedGroupMembers = useMemo(() => {
    if (!selected || selected.target.kind !== 'group') return undefined
    const conversationId = selected.target.conversationId
    return groups?.find((g) => g.id === conversationId)?.participant_names
  }, [selected, groups])

  return (
    <Group align="flex-start" wrap="nowrap" h="calc(100vh - 120px)">
      <Box w={260} h="100%">
        <ScrollArea h="100%">
          <Stack gap={4}>
            <Text size="xs" fw={700} c="dimmed" mt="xs">
              CONTACTS
            </Text>
            {contactsLoading && <LoadingText />}
            {!contactsLoading && sortedContactItems.length === 0 && (
              <EmptyText>No contacts yet.</EmptyText>
            )}
            {sortedContactItems.map((item) => (
              <NavLink
                key={targetKey(item.target)}
                label={item.label}
                active={targetKey(item.target) === selectedKey}
                onClick={() => setSelected(item)}
                rightSection={
                  summaryByKey.get(targetKey(item.target))?.has_unread ? (
                    <Badge size="xs" circle color="red" />
                  ) : undefined
                }
              />
            ))}

            <Divider my="xs" />
            <Group justify="space-between" mt="xs">
              <Text size="xs" fw={700} c="dimmed">
                GROUP CHATS
              </Text>
              {canCreateGroup && (
                <Button size="compact-xs" variant="subtle" onClick={groupModalHandlers.open}>
                  + New
                </Button>
              )}
            </Group>
            {groupsLoading && <LoadingText />}
            {!groupsLoading && sortedGroupItems.length === 0 && (
              <EmptyText>No group chats yet.</EmptyText>
            )}
            {sortedGroupItems.map((item) => (
              <NavLink
                key={targetKey(item.target)}
                label={item.label}
                active={targetKey(item.target) === selectedKey}
                onClick={() => setSelected(item)}
                rightSection={
                  summaryByKey.get(targetKey(item.target))?.has_unread ? (
                    <Badge size="xs" circle color="red" />
                  ) : undefined
                }
              />
            ))}
          </Stack>
        </ScrollArea>
      </Box>

      <Stack flex={1} h="100%">
        <Group justify="space-between" align="flex-start">
          <Stack gap={0}>
            <Title order={3}>{selected ? selected.label : 'Messages'}</Title>
            {selectedGroupMembers && (
              <Text size="sm" c="dimmed">
                {selectedGroupMembers.join(', ')}
              </Text>
            )}
          </Stack>
          {selected && (
            <Group gap="xs">
              <Button
                size="xs"
                variant="subtle"
                loading={markUnreadMutation.isPending}
                onClick={() => markUnreadMutation.mutate(selected.target)}
              >
                Mark unread
              </Button>
            </Group>
          )}
        </Group>

        {!selected ? (
          <EmptyText>Select a contact or group chat to start messaging.</EmptyText>
        ) : (
          <>
            <ScrollArea flex={1}>
              <Stack gap="xs">
                {messagesLoading && <LoadingText />}
                {!messagesLoading && messages?.length === 0 && (
                  <EmptyText>No messages yet.</EmptyText>
                )}
                {messages?.map((message) => {
                  const isMine = message.sender_id === principal?.id
                  return (
                    <Paper
                      key={message.id}
                      withBorder
                      p="sm"
                      ml={isMine ? '20%' : 0}
                      mr={isMine ? 0 : '20%'}
                      bg={isMine ? 'var(--mantine-color-blue-0)' : undefined}
                    >
                      <Text size="xs" fw={600}>
                        {message.sender_name}
                      </Text>
                      <Text size="sm">{message.body}</Text>
                      <Text size="xs" c="dimmed">
                        {new Date(message.created_at).toLocaleString()}
                      </Text>
                    </Paper>
                  )
                })}
              </Stack>
            </ScrollArea>

            <Group align="flex-end">
              <Textarea
                flex={1}
                placeholder="Type a message..."
                value={body}
                onChange={(e) => setBody(e.currentTarget.value)}
              />
              <Button
                loading={sendMutation.isPending}
                disabled={!body.trim()}
                onClick={() => sendMutation.mutate(body)}
              >
                Send
              </Button>
            </Group>
          </>
        )}
      </Stack>

      <Modal
        opened={groupModalOpened}
        onClose={groupModalHandlers.close}
        title="New group chat"
      >
        <form onSubmit={groupForm.onSubmit(() => createGroupMutation.mutate())}>
          <Stack>
            <TextInput
              label="Title"
              required
              {...groupForm.getInputProps('title')}
            />
            <MultiSelect
              label="Participants"
              placeholder="Choose students and attendings"
              data={participantOptions}
              searchable
              {...groupForm.getInputProps('participant_ids')}
            />
            <Button type="submit" loading={createGroupMutation.isPending}>
              Create
            </Button>
          </Stack>
        </form>
      </Modal>
    </Group>
  )
}
