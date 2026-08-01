import { ActionIcon, Table } from '@mantine/core'
import { IconChevronDown, IconChevronUp } from '@tabler/icons-react'
import type { ReactNode } from 'react'

interface ClickableRowProps {
  onToggle: () => void
  expanded: boolean
  expandLabel: string
  children: ReactNode
}

/** A table row that expands on click, without the `role="button"` hack on
 * `<Table.Tr>` several pages used to reach for -- that override breaks the
 * row's implicit `row` semantics and, without an `href`/`tabIndex`, is
 * invisible to keyboard users entirely. Real keyboard/screen-reader access
 * comes from a genuine focusable control (an icon button) in its own cell;
 * the row's own `onClick` stays as a mouse-only convenience. */
export function ClickableRow({ onToggle, expanded, expandLabel, children }: ClickableRowProps) {
  return (
    <Table.Tr onClick={onToggle} className="list-item-enter cursor-pointer">
      {children}
      <Table.Td onClick={(event) => event.stopPropagation()}>
        <ActionIcon variant="subtle" color="gray" aria-label={expandLabel} aria-expanded={expanded} onClick={onToggle}>
          {expanded ? <IconChevronUp size={16} /> : <IconChevronDown size={16} />}
        </ActionIcon>
      </Table.Td>
    </Table.Tr>
  )
}
