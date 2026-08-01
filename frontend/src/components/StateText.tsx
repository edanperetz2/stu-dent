import { Button, Group, Text } from '@mantine/core'
import type { ReactNode } from 'react'

/** The plain dimmed `<Text>{children}</Text>` shown by every page for its
 * empty state (e.g. "No notifications.") -- deduped the same way. */
export function EmptyText({ children }: { children: ReactNode }) {
  return <Text c="dimmed">{children}</Text>
}

/** A real query failure (401/500/network) shown distinctly from an empty
 * state -- several pages used to only check isLoading/data and rendered
 * their empty-state text for a failed request too, indistinguishable from
 * genuinely having no data. `onRetry`, when given, wires up a "Try again"
 * button to the query's own `refetch` instead of leaving the user stuck
 * until a manual page reload. */
export function ErrorText({ children, onRetry }: { children: ReactNode; onRetry?: () => void }) {
  return (
    <Group gap="xs">
      <Text c="red">{children}</Text>
      {onRetry && (
        <Button size="xs" variant="light" color="red" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Group>
  )
}
