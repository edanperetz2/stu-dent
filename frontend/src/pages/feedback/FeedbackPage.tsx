import { Accordion, Badge, Button, Card, Group, Modal, Stack, Text, Textarea, Title } from '@mantine/core'
import { useForm } from '@mantine/form'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  listFeedbackGiven,
  listFeedbackReceived,
  listPendingFeedback,
  submitFeedback,
  type FeedbackCreateInput,
} from '../../api/feedback'
import { apiErrorMessage } from '../../api/httpClient'
import type { Feedback, PendingFeedback } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { useAuthToken } from '../../auth/useAuthToken'
import { EmptyText, LoadingText } from '../../components/StateText'
import { formatDateTime } from '../../utils/dates'

interface GroupSpec {
  keyFn: (feedback: Feedback) => string
  labelFn: (feedback: Feedback) => string
}

function groupFeedback(feedback: Feedback[], group: GroupSpec) {
  const groups = new Map<string, { label: string; items: Feedback[] }>()
  for (const item of feedback) {
    const key = group.keyFn(item)
    if (!groups.has(key)) groups.set(key, { label: group.labelFn(item), items: [] })
    groups.get(key)!.items.push(item)
  }
  return [...groups.entries()]
    .map(([key, value]) => ({ key, ...value }))
    .sort((a, b) => a.label.localeCompare(b.label))
}

function FeedbackEntryCard({ feedback }: { feedback: Feedback }) {
  return (
    <Card withBorder padding="sm">
      <Text size="xs" c="dimmed">
        Appointment on {formatDateTime(feedback.appointment_start_time)}
      </Text>
      <Stack gap={4} mt="xs">
        <div>
          <Text size="sm" fw={600}>
            What went well?
          </Text>
          <Text size="sm">{feedback.went_well}</Text>
        </div>
        <div>
          <Text size="sm" fw={600}>
            What could be improved?
          </Text>
          <Text size="sm">{feedback.could_improve}</Text>
        </div>
        {feedback.additional_comments && (
          <div>
            <Text size="sm" fw={600}>
              Anything else?
            </Text>
            <Text size="sm">{feedback.additional_comments}</Text>
          </div>
        )}
      </Stack>
    </Card>
  )
}

/** Flat list when `group` is null (a patient only ever has one student, so
 * there's nothing meaningful to unite); grouped into an expandable
 * accordion otherwise (a student's many patients, an attending's many
 * students). */
function FeedbackList({
  feedback,
  group,
  emptyMessage,
}: {
  feedback: Feedback[]
  group: GroupSpec | null
  emptyMessage: string
}) {
  if (feedback.length === 0) return <EmptyText>{emptyMessage}</EmptyText>

  if (!group) {
    return (
      <Stack>
        {feedback.map((item) => (
          <FeedbackEntryCard key={item.id} feedback={item} />
        ))}
      </Stack>
    )
  }

  const groups = groupFeedback(feedback, group)
  return (
    <Accordion multiple defaultValue={groups.map((g) => g.key)}>
      {groups.map((groupEntry) => (
        <Accordion.Item key={groupEntry.key} value={groupEntry.key}>
          <Accordion.Control>
            <Group justify="space-between" pr="md" wrap="nowrap">
              <Text fw={600}>{groupEntry.label}</Text>
              <Badge variant="light">{groupEntry.items.length}</Badge>
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Stack>
              {groupEntry.items.map((item) => (
                <FeedbackEntryCard key={item.id} feedback={item} />
              ))}
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      ))}
    </Accordion>
  )
}

function PendingFeedbackSection({
  pending,
  onGive,
}: {
  pending: PendingFeedback[]
  onGive: (item: PendingFeedback) => void
}) {
  if (pending.length === 0) return <EmptyText>Nothing awaiting your feedback.</EmptyText>
  return (
    <Stack>
      {pending.map((item) => (
        <Card key={item.appointment_id} withBorder padding="sm">
          <Group justify="space-between" wrap="nowrap">
            <div>
              <Text fw={600}>{item.student_name}</Text>
              <Text size="xs" c="dimmed">
                {item.patient_name} &middot; {formatDateTime(item.appointment_start_time)}
              </Text>
            </div>
            <Button size="xs" onClick={() => onGive(item)}>
              Give feedback
            </Button>
          </Group>
        </Card>
      ))}
    </Stack>
  )
}

export function FeedbackPage() {
  const token = useAuthToken()
  const { principal } = useAuth()
  const queryClient = useQueryClient()
  const [modalOpened, { open: openModal, close: closeModal }] = useDisclosure(false)
  const [activeItem, setActiveItem] = useState<PendingFeedback | null>(null)

  const isStudent = principal?.role === 'student'
  const isAttending = principal?.role === 'attending'
  const canGiveFeedback = principal?.role === 'patient' || isAttending

  const { data: pending, isLoading: pendingLoading } = useQuery({
    queryKey: ['feedback', 'pending'],
    queryFn: () => listPendingFeedback(token),
    enabled: canGiveFeedback,
  })

  const { data: given, isLoading: givenLoading } = useQuery({
    queryKey: ['feedback', 'given'],
    queryFn: () => listFeedbackGiven(token),
    enabled: canGiveFeedback,
  })

  const { data: received, isLoading: receivedLoading } = useQuery({
    queryKey: ['feedback', 'received'],
    queryFn: () => listFeedbackReceived(token),
    enabled: isStudent,
  })

  const form = useForm<FeedbackCreateInput>({
    initialValues: { went_well: '', could_improve: '', additional_comments: '' },
    validate: {
      went_well: (value) => (value.trim().length > 0 ? null : 'Required'),
      could_improve: (value) => (value.trim().length > 0 ? null : 'Required'),
    },
  })

  const submitMutation = useMutation({
    mutationFn: (payload: FeedbackCreateInput) => {
      if (!activeItem) throw new Error('No appointment selected')
      return submitFeedback(token, activeItem.appointment_id, payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['feedback'] })
      notifications.show({ message: 'Feedback submitted', color: 'green' })
      closeModal()
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to submit feedback'),
        color: 'red',
      })
    },
  })

  function handleGive(item: PendingFeedback) {
    setActiveItem(item)
    form.reset()
    openModal()
  }

  function handleSubmit(values: FeedbackCreateInput) {
    submitMutation.mutate({
      went_well: values.went_well,
      could_improve: values.could_improve,
      additional_comments: values.additional_comments?.trim() ? values.additional_comments : null,
    })
  }

  if (isStudent) {
    return (
      <Stack>
        <Title order={2}>Feedback you&apos;ve received</Title>
        <Text size="sm" c="dimmed">
          Qualitative feedback from patients and attendings about your completed appointments,
          grouped by patient.
        </Text>
        {receivedLoading ? (
          <LoadingText />
        ) : (
          <FeedbackList
            feedback={received ?? []}
            group={{ keyFn: (f) => f.patient_id, labelFn: (f) => f.patient_name }}
            emptyMessage="No feedback yet."
          />
        )}
      </Stack>
    )
  }

  return (
    <Stack>
      <Title order={2}>Feedback</Title>

      <Stack gap="xs">
        <Title order={4}>Pending feedback</Title>
        {pendingLoading ? (
          <LoadingText />
        ) : (
          <PendingFeedbackSection pending={pending ?? []} onGive={handleGive} />
        )}
      </Stack>

      <Stack gap="xs">
        <Title order={4}>Feedback you&apos;ve given</Title>
        {givenLoading ? (
          <LoadingText />
        ) : (
          <FeedbackList
            feedback={given ?? []}
            group={
              isAttending ? { keyFn: (f) => f.student_id, labelFn: (f) => f.student_name } : null
            }
            emptyMessage="You haven't given any feedback yet."
          />
        )}
      </Stack>

      <Modal opened={modalOpened} onClose={closeModal} title="Give feedback" centered>
        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack>
            <Textarea
              label="What went well?"
              autosize
              minRows={2}
              {...form.getInputProps('went_well')}
            />
            <Textarea
              label="What could be improved?"
              autosize
              minRows={2}
              {...form.getInputProps('could_improve')}
            />
            <Textarea
              label="Anything else? (optional)"
              autosize
              minRows={2}
              {...form.getInputProps('additional_comments')}
            />
            <Button type="submit" loading={submitMutation.isPending}>
              Submit
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  )
}
