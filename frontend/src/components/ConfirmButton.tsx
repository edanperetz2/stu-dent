import { Button, Group, Modal, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'

interface ConfirmButtonProps {
  label: string
  confirmLabel?: string
  message: string
  color?: string
  variant?: string
  size?: string
  // `Promise<unknown>`, not `Promise<void>`: callers pass mutateAsync(...)
  // directly, which resolves with the mutation's real result -- this only
  // needs to know *when* it settles, never what it resolves to.
  onConfirm: () => void | Promise<unknown>
  loading?: boolean
}

export function ConfirmButton({
  label,
  confirmLabel = 'Confirm',
  message,
  color = 'red',
  variant = 'light',
  size = 'xs',
  onConfirm,
  loading,
}: ConfirmButtonProps) {
  const [opened, { open, close }] = useDisclosure(false)

  return (
    <>
      <Button color={color} variant={variant} size={size} onClick={open}>
        {label}
      </Button>
      <Modal opened={opened} onClose={close} title="Are you sure?" centered size="sm">
        <Text size="sm">{message}</Text>
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={close}>
            Cancel
          </Button>
          <Button
            color={color}
            loading={loading}
            onClick={() => {
              // Awaited (not fire-and-forget) so `loading` reflects the
              // real request duration -- closing synchronously in the same
              // handler that starts the mutation meant the spinner could
              // only ever flash for the Modal's own close transition
              // (~150-200ms), never the actual in-flight time. Errors are
              // swallowed here deliberately: every caller already has its
              // own onError handler for user-facing feedback, so this
              // await exists purely for timing, not error handling.
              Promise.resolve(onConfirm())
                .catch(() => {})
                .finally(close)
            }}
          >
            {confirmLabel}
          </Button>
        </Group>
      </Modal>
    </>
  )
}
