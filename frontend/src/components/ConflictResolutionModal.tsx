import { Button, Group, List, Modal, Text } from '@mantine/core'
import type { ConflictReason } from '../api/types'

interface ConflictResolutionModalProps {
  opened: boolean
  onClose: () => void
  conflicts: ConflictReason[]
  onJoinWaitlist: () => void
  joining?: boolean
  // Set when this conflict came from editing/accepting an *existing*
  // appointment (not a fresh create) -- joining the waitlist in that case
  // cancels that appointment immediately, rather than leaving it active
  // while also waiting on a new one, so the user never silently ends up
  // holding two appointments at once. Must be surfaced up front, not
  // discovered after the fact.
  cancelsExistingAppointment?: boolean
}

function conflictMessage(conflict: ConflictReason): string {
  switch (conflict.resource_type) {
    case 'student':
      return 'You already have another appointment at this time.'
    case 'patient':
      return 'This patient already has another appointment at this time.'
    case 'attending':
      return `Attending ${conflict.resource_name} is already booked at this time.`
    case 'room':
      return `Room ${conflict.resource_name} is already booked at this time.`
    case 'equipment':
      return `Equipment ${conflict.resource_name} is already booked at this time.`
  }
}

/** Shown whenever a create/edit/accept attempt 409s with a structured
 * conflict list -- names exactly what's blocking the request and offers
 * either to go edit the still-open form, or join the waitlist with the
 * exact same request + these same causes recorded. */
export function ConflictResolutionModal({
  opened,
  onClose,
  conflicts,
  onJoinWaitlist,
  joining,
  cancelsExistingAppointment,
}: ConflictResolutionModalProps) {
  return (
    <Modal opened={opened} onClose={onClose} title="This request isn't available" centered>
      <Text size="sm" mb="xs">
        The requested time conflicts with an existing booking:
      </Text>
      <List size="sm" mb="md">
        {conflicts.map((conflict) => (
          <List.Item key={`${conflict.resource_type}:${conflict.resource_id}`}>
            {conflictMessage(conflict)}
          </List.Item>
        ))}
      </List>
      {cancelsExistingAppointment ? (
        <Text size="sm" c="dimmed" mb="md">
          Change the time, attending, room, or equipment and try again, or join the waitlist to be
          automatically booked once this exact request becomes available.{' '}
          <Text span fw={600} c="red">
            Joining the waitlist will cancel this appointment now
          </Text>{' '}
          -- you won't hold both while you wait.
        </Text>
      ) : (
        <Text size="sm" c="dimmed" mb="md">
          Change the time, attending, room, or equipment and try again, or join the waitlist to be
          automatically booked once this exact request becomes available.
        </Text>
      )}
      <Group justify="flex-end">
        <Button variant="default" onClick={onClose}>
          Let me change it
        </Button>
        <Button color={cancelsExistingAppointment ? 'red' : undefined} loading={joining} onClick={onJoinWaitlist}>
          {cancelsExistingAppointment ? 'Cancel & join waitlist' : 'Join waitlist'}
        </Button>
      </Group>
    </Modal>
  )
}
