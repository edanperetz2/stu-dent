import { Group, Title } from '@mantine/core'
import type { ReactNode } from 'react'

/** The `<Group justify="space-between"><Title order={2}>...` + action
 * buttons block retyped by hand across every page's header. */
export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <Group justify="space-between">
      <Title order={2}>{title}</Title>
      {actions}
    </Group>
  )
}
