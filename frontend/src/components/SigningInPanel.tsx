import { Stack, Text } from '@mantine/core'

export function SigningInPanel() {
  return (
    <Stack
      align="center"
      gap="md"
      py="xs"
      role="status"
      aria-live="polite"
      className="signing-in-panel"
    >
      <Stack align="center" gap={4}>
        <Text fw={650} size="lg">
          Signing you in
          <span className="signing-in-dots" aria-hidden="true">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
        </Text>
        <Text size="sm" c="dimmed" ta="center">
          Getting your workspace ready.
        </Text>
      </Stack>
    </Stack>
  )
}
