import { Badge, Button, Group, Paper, Stack, Text, Textarea, Title } from '@mantine/core'
import { notifications } from '@mantine/notifications'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { askQuestion, generateReport, listReports } from '../../api/reports'
import { apiErrorMessage } from '../../api/httpClient'
import type { ReportPeriodType } from '../../api/types'
import { useAuthToken } from '../../auth/useAuthToken'
import { EmptyText, LoadingText } from '../../components/StateText'

const PERIOD_COLORS: Record<ReportPeriodType, string> = {
  weekly: 'blue',
  monthly: 'grape',
  ad_hoc: 'teal',
}

function periodLabel(periodType: ReportPeriodType): string {
  if (periodType === 'ad_hoc') return 'Q&A'
  return periodType[0].toUpperCase() + periodType.slice(1)
}

export function ReportsPage() {
  const token = useAuthToken()
  const queryClient = useQueryClient()
  const [question, setQuestion] = useState('')

  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => listReports(token),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['reports'] })

  const generateMutation = useMutation({
    mutationFn: () => generateReport(token),
    onSuccess: () => {
      invalidate()
      notifications.show({ message: 'Report generated', color: 'green' })
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to generate report'),
        color: 'red',
      })
    },
  })

  const askMutation = useMutation({
    mutationFn: (q: string) => askQuestion(token, q),
    onSuccess: () => {
      invalidate()
      setQuestion('')
    },
    onError: (err) => {
      notifications.show({
        message: apiErrorMessage(err, 'Failed to get an answer'),
        color: 'red',
      })
    },
  })

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Reports</Title>
        <Button onClick={() => generateMutation.mutate()} loading={generateMutation.isPending}>
          Generate report now
        </Button>
      </Group>

      <Stack gap="xs">
        <Textarea
          label="Ask a question"
          placeholder="e.g. which equipment is underused this month?"
          value={question}
          onChange={(event) => setQuestion(event.currentTarget.value)}
          autosize
          minRows={2}
        />
        <Button
          variant="light"
          onClick={() => askMutation.mutate(question)}
          loading={askMutation.isPending}
          disabled={!question.trim()}
        >
          Ask
        </Button>
      </Stack>

      {isLoading ? (
        <LoadingText />
      ) : reports?.length === 0 ? (
        <EmptyText>No reports yet.</EmptyText>
      ) : (
        <Stack gap="xs">
          {reports?.map((report) => (
            <Paper key={report.id} withBorder p="sm">
              <Stack gap={4}>
                <Group justify="space-between" wrap="nowrap">
                  <Badge size="sm" color={PERIOD_COLORS[report.period_type]}>
                    {periodLabel(report.period_type)}
                  </Badge>
                  <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                    {new Date(report.created_at).toLocaleString()}
                  </Text>
                </Group>
                <Text fw={600}>{report.title}</Text>
                <Text size="sm">{report.content}</Text>
              </Stack>
            </Paper>
          ))}
        </Stack>
      )}
    </Stack>
  )
}
