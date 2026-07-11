import { Text } from '@mantine/core'
import type { ReactNode } from 'react'

/** The plain `<Text>Loading...</Text>` shown by every page while its
 * query is pending -- deduped to keep the string/styling in one place. */
export function LoadingText() {
  return <Text>Loading...</Text>
}

/** The plain dimmed `<Text>{children}</Text>` shown by every page for its
 * empty state (e.g. "No notifications.") -- deduped the same way. */
export function EmptyText({ children }: { children: ReactNode }) {
  return <Text c="dimmed">{children}</Text>
}
