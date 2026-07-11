import { Button, Group, Paper, Select, Stack, Text, Textarea, Title } from '@mantine/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { listMessages, markMessageRead, sendMessage } from '../../api/directMessages'
import { apiErrorMessage } from '../../api/httpClient'
import { notifications } from '@mantine/notifications'
import { listPatients } from '../../api/patients'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'

export function MessagesPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [body, setBody] = useState('')

  const isStudent = principal?.role === 'student'
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(
    isStudent ? null : (principal?.id ?? null),
  )

  const { data: patients } = useQuery({
    queryKey: ['patients'],
    queryFn: () => listPatients(token),
    enabled: isStudent,
  })

  useEffect(() => {
    if (isStudent && !selectedPatientId && patients && patients.length > 0) {
      setSelectedPatientId(patients[0].id)
    }
  }, [isStudent, patients, selectedPatientId])

  const patientId = isStudent ? selectedPatientId : principal?.id

  const { data: messages } = useQuery({
    queryKey: ['messages', patientId],
    queryFn: () => listMessages(token, patientId!),
    enabled: !!patientId,
  })

  const markReadMutation = useMutation({
    mutationFn: (messageId: string) => markMessageRead(token, patientId!, messageId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['messages', patientId] }),
  })

  useEffect(() => {
    if (!messages || !principal) return
    for (const message of messages) {
      if (!message.read_at && message.sender_id !== principal.id) {
        markReadMutation.mutate(message.id)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only re-run when the message list itself changes
  }, [messages, principal])

  const sendMutation = useMutation({
    mutationFn: () => sendMessage(token, patientId!, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages', patientId] })
      setBody('')
    },
    onError: (err) =>
      notifications.show({
        message: apiErrorMessage(err, 'Failed to send message'),
        color: 'red',
      }),
  })

  const patientOptions = useMemo(
    () => (patients ?? []).map((p) => ({ value: p.id, label: p.full_name })),
    [patients],
  )

  return (
    <Stack maw={600}>
      <Title order={2}>Messages</Title>

      {isStudent && (
        <Select
          label="Patient"
          placeholder="Choose a patient"
          data={patientOptions}
          value={selectedPatientId}
          onChange={setSelectedPatientId}
        />
      )}

      {!patientId ? (
        <Text c="dimmed">No patient selected.</Text>
      ) : (
        <>
          <Stack gap="xs">
            {messages?.length === 0 && <Text c="dimmed">No messages yet.</Text>}
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
                  <Text size="sm">{message.body}</Text>
                  <Text size="xs" c="dimmed">
                    {new Date(message.created_at).toLocaleString()}
                    {message.read_at ? ' · Read' : ''}
                  </Text>
                </Paper>
              )
            })}
          </Stack>

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
              onClick={() => sendMutation.mutate()}
            >
              Send
            </Button>
          </Group>
        </>
      )}
    </Stack>
  )
}
