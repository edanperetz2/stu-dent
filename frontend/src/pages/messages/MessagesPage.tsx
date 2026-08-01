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
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
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
import { ChatSkeleton, ListRowsSkeleton } from '../../components/Skeletons'
import { EmptyText, ErrorText } from '../../components/StateText'
import { formatDateTime } from '../../utils/dates'

interface Selection {
  target: MessageTarget
  label: string
}

const MESSAGE_PAGE_SIZE = 50

/** Unread threads first, then most-recent-activity first; threads with no
 * activity yet (e.g. a just-created group with no messages) sort last,
 * falling back to alphabetical by label so the order stays stable. A pure
 * module-level function (summaryByKey passed in, not read from a closure)
 * so it's directly unit-testable without mounting the page. */
export function sortByActivity(
  items: Selection[],
  summaryByKey: Map<string, ThreadSummary>,
): Selection[] {
  return [...items].sort((a, b) => {
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

  const {
    data: contacts,
    isLoading: contactsLoading,
    isError: contactsError,
    error: contactsErrorValue,
    refetch: refetchContacts,
  } = useQuery({
    queryKey: ['messages', 'contacts'],
    queryFn: () => listContacts(token),
  })

  const {
    data: groups,
    isLoading: groupsLoading,
    isError: groupsError,
    error: groupsErrorValue,
    refetch: refetchGroups,
  } = useQuery({
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

  const {
    data: messagesData,
    isLoading: messagesLoading,
    isError: messagesError,
    error: messagesErrorValue,
    refetch: refetchMessages,
    fetchPreviousPage,
    hasPreviousPage,
    isFetchingPreviousPage,
  } = useInfiniteQuery({
    queryKey: ['messages', 'thread', selectedKey],
    queryFn: ({ pageParam }) =>
      listMessages(token, selected!.target, { beforeSequence: pageParam, limit: MESSAGE_PAGE_SIZE }),
    enabled: !!selected,
    initialPageParam: undefined as number | undefined,
    // Each page arrives oldest-first (chat order) -- fetchPreviousPage
    // prepends an even-older page ahead of it, so pages.flat() stays in
    // the right order without any client-side re-sorting.
    getPreviousPageParam: (firstPage) =>
      firstPage.length === MESSAGE_PAGE_SIZE ? firstPage[0].sequence : undefined,
    getNextPageParam: () => undefined,
  })
  const messages = messagesData?.pages.flat()

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

  // Set right before an explicit "Mark unread" click, so the auto-mark-read
  // effect below (which also reacts to that same has_unread flag flipping
  // true) can tell "the user just asked for this" apart from "a live
  // message arrived" and skip re-marking it read out from under them --
  // without this it flipped back to read within one refetch cycle, every
  // time, since the button only renders while the thread is selected.
  const justMarkedUnreadRef = useRef(false)

  const markUnreadMutation = useMutation({
    mutationFn: (target: MessageTarget) => markUnread(token, target),
    onSuccess: () => {
      justMarkedUnreadRef.current = true
      queryClient.invalidateQueries({ queryKey: ['messages', 'unread-count'] })
      queryClient.invalidateQueries({ queryKey: ['messages', 'thread-summaries'] })
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to mark thread as unread'),
        color: 'red',
      }),
  })

  const selectedHasUnread = selectedKey ? (summaryByKey.get(selectedKey)?.has_unread ?? false) : false

  useEffect(() => {
    // Re-marks read both when the selected conversation changes AND when a
    // live incoming message (via the websocket -> thread-summaries
    // refetch) flips the *currently open* thread back to unread -- without
    // the second trigger, an actively-open conversation kept showing an
    // unread badge until the user navigated away and back.
    if (selected && selectedHasUnread) {
      if (justMarkedUnreadRef.current) {
        justMarkedUnreadRef.current = false
        return
      }
      markReadMutation.mutate(selected.target)
    }
    // Only re-run when the selected conversation or its live unread flag
    // changes -- not on every markReadMutation identity change (that would
    // re-fire on its own success/error callbacks).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey, selectedHasUnread])

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

  const contactItems: Selection[] = useMemo(
    () =>
      (contacts ?? []).map((c) =>
        isAdmin
          ? { target: { kind: 'admin', ownerId: c.id }, label: `${c.full_name} (${c.role})` }
          : { target: { kind: 'direct', otherUserId: c.id }, label: c.full_name },
      ),
    [contacts, isAdmin],
  )

  const groupItems: Selection[] = useMemo(
    () =>
      (groups ?? []).map((g) => ({
        target: { kind: 'group', conversationId: g.id },
        label: g.title,
      })),
    [groups],
  )

  const sortedContactItems = useMemo(
    () =>
      sortByActivity(
        isAdmin ? contactItems : [...contactItems, { target: { kind: 'admin' }, label: 'Admin' }],
        summaryByKey,
      ),
    [contactItems, isAdmin, summaryByKey],
  )
  const sortedGroupItems = useMemo(
    () => sortByActivity(groupItems, summaryByKey),
    [groupItems, summaryByKey],
  )

  const selectedGroupMembers = useMemo(() => {
    if (!selected || selected.target.kind !== 'group') return undefined
    const conversationId = selected.target.conversationId
    return groups?.find((g) => g.id === conversationId)?.participant_names
  }, [selected, groups])

  return (
    <Group align="flex-start" wrap="nowrap" h="calc(100vh - 120px)">
      {/* Below the "sm" breakpoint this is a single-pane master/detail view,
          not a permanent two-pane layout -- the fixed-width sidebar next to
          a flex-1 thread pane doesn't fit a phone screen. Once a thread is
          selected the contact list hides (and the "Back" button below
          reappears) so only one pane shows at a time; both stay visible
          side by side from "sm" up, unchanged from before. */}
      <Box w={{ base: '100%', sm: 260 }} h="100%" hiddenFrom={selected ? 'sm' : undefined}>
        <ScrollArea h="100%">
          <Stack gap={4}>
            <Text size="xs" fw={700} c="dimmed" mt="xs">
              CONTACTS
            </Text>
            {contactsError ? (
              <ErrorText onRetry={() => refetchContacts()}>
                {apiErrorMessage(contactsErrorValue, 'Failed to load contacts.')}
              </ErrorText>
            ) : contactsLoading ? (
              <ListRowsSkeleton />
            ) : (
              sortedContactItems.length === 0 && <EmptyText>No contacts yet.</EmptyText>
            )}
            {sortedContactItems.map((item) => (
              <NavLink
                key={targetKey(item.target)}
                label={item.label}
                active={targetKey(item.target) === selectedKey}
                onClick={() => setSelected(item)}
                rightSection={
                  summaryByKey.get(targetKey(item.target))?.has_unread ? (
                    <Badge size="xs" circle color="red" aria-label="Unread" />
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
            {groupsError ? (
              <ErrorText onRetry={() => refetchGroups()}>
                {apiErrorMessage(groupsErrorValue, 'Failed to load group chats.')}
              </ErrorText>
            ) : groupsLoading ? (
              <ListRowsSkeleton count={3} />
            ) : (
              sortedGroupItems.length === 0 && <EmptyText>No group chats yet.</EmptyText>
            )}
            {sortedGroupItems.map((item) => (
              <NavLink
                key={targetKey(item.target)}
                label={item.label}
                active={targetKey(item.target) === selectedKey}
                onClick={() => setSelected(item)}
                rightSection={
                  summaryByKey.get(targetKey(item.target))?.has_unread ? (
                    <Badge size="xs" circle color="red" aria-label="Unread" />
                  ) : undefined
                }
              />
            ))}
          </Stack>
        </ScrollArea>
      </Box>

      <Stack flex={1} h="100%" hiddenFrom={!selected ? 'sm' : undefined}>
        <Group justify="space-between" align="flex-start">
          <Group gap="xs" align="flex-start">
            {selected && (
              <Button size="xs" variant="subtle" hiddenFrom="sm" onClick={() => setSelected(null)}>
                ← Back
              </Button>
            )}
            <Stack gap={0}>
              <Title order={3}>{selected ? selected.label : 'Messages'}</Title>
              {selectedGroupMembers && (
                <Text size="sm" c="dimmed">
                  {selectedGroupMembers.join(', ')}
                </Text>
              )}
            </Stack>
          </Group>
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
                {messagesError ? (
                  <ErrorText onRetry={() => refetchMessages()}>
                    {apiErrorMessage(messagesErrorValue, 'Failed to load messages.')}
                  </ErrorText>
                ) : messagesLoading ? (
                  <ChatSkeleton />
                ) : (
                  messages?.length === 0 && <EmptyText>No messages yet.</EmptyText>
                )}
                {hasPreviousPage && (
                  <Button
                    variant="subtle"
                    size="xs"
                    onClick={() => fetchPreviousPage()}
                    loading={isFetchingPreviousPage}
                    // No Mantine shorthand for align-self.
                    style={{ alignSelf: 'center' }}
                  >
                    Load earlier messages
                  </Button>
                )}
                {messages?.map((message) => {
                  const isMine = message.sender_id === principal?.id
                  return (
                    <Paper
                      key={message.id}
                      withBorder
                      p="sm"
                      className="list-item-enter"
                      ml={isMine ? '20%' : 0}
                      mr={isMine ? 0 : '20%'}
                      bg={isMine ? 'var(--mantine-color-blue-0)' : undefined}
                    >
                      <Text size="xs" fw={600}>
                        {message.sender_name}
                      </Text>
                      <Text size="sm">{message.body}</Text>
                      <Text size="xs" c="dimmed">
                        {formatDateTime(message.created_at)}
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
        size="md"
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
