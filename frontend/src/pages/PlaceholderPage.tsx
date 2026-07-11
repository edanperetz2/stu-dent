import { Text, Title } from '@mantine/core'

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <>
      <Title order={2}>{title}</Title>
      <Text c="dimmed">Coming soon.</Text>
    </>
  )
}
