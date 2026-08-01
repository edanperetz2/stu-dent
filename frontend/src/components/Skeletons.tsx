import { Group, Paper, Skeleton, Stack, Table } from '@mantine/core'

/** Self-contained placeholder table, shaped like a real table's row/column
 * grid -- swapped in for the bare "Loading..." text every page used to
 * show, so a table page's layout doesn't jump once real rows arrive. */
export function TableSkeleton({ columns, rows = 6 }: { columns: number; rows?: number }) {
  return (
    <Table>
      <Table.Tbody>
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <Table.Tr key={rowIndex}>
            {Array.from({ length: columns }).map((__, colIndex) => (
              <Table.Td key={colIndex}>
                <Skeleton height={14} width={colIndex === 0 ? '75%' : '55%'} />
              </Table.Td>
            ))}
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  )
}

/** Placeholder for a vertical stack of bordered cards (notifications,
 * reports, feedback) -- each card gets a title-width bar, a body-width bar,
 * and a small trailing badge/button-shaped block. */
export function CardListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <Stack gap="xs">
      {Array.from({ length: count }).map((_, i) => (
        <Paper key={i} withBorder p="sm">
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Stack gap={6} flex={1}>
              <Skeleton height={16} width="30%" />
              <Skeleton height={12} width="85%" />
            </Stack>
            <Skeleton height={22} width={70} />
          </Group>
        </Paper>
      ))}
    </Stack>
  )
}

/** Placeholder for a plain list of nav-link-shaped rows (Messages sidebar). */
export function ListRowsSkeleton({ count = 5 }: { count?: number }) {
  return (
    <Stack gap="sm" p="xs">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} height={16} width={`${75 - (i % 3) * 12}%`} />
      ))}
    </Stack>
  )
}

/** Placeholder for a chat thread -- alternating left/right bubble shapes. */
export function ChatSkeleton({ count = 5 }: { count?: number }) {
  return (
    <Stack gap="xs">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton
          key={i}
          height={44}
          ml={i % 2 === 0 ? 0 : '20%'}
          mr={i % 2 === 0 ? '20%' : 0}
          radius="sm"
        />
      ))}
    </Stack>
  )
}

/** Placeholder for a short form -- N input-shaped bars plus a submit-button-
 * shaped bar. */
export function FormSkeleton({ fields = 2 }: { fields?: number }) {
  return (
    <Stack>
      {Array.from({ length: fields }).map((_, i) => (
        <Skeleton key={i} height={36} />
      ))}
      <Skeleton height={36} width={120} />
    </Stack>
  )
}
