import { Button, Group, Modal, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'

interface ConfirmButtonProps {
  label: string
  confirmLabel?: string
  message: string
  color?: string
  variant?: string
  size?: string
  onConfirm: () => void
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
              onConfirm()
              close()
            }}
          >
            {confirmLabel}
          </Button>
        </Group>
      </Modal>
    </>
  )
}
